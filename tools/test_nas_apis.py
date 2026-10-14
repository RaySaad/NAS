"""HTTP regression tests for NAS APIs. No writes unless --write is explicit."""
import argparse
import ast
import copy
from datetime import date
import getpass
import json
import os
from pathlib import Path
import secrets
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = 'naass_test_19.0_2026_10_06_16_05'
JV_TYPES = ('invoice', 'invoice_refund', 'payment', 'clearance',
            'insurance_payment', 'cost_invoice', 'payroll', 'multi-invoice', 'multi-payment')


def discover_routes():
    routes = {}
    for relative in ('contacts_ext/controllers/contact_api.py',
                     'employees_ext/controllers/api.py', 'account_ext/controllers/jv_api.py'):
        for node in ast.walk(ast.parse((ROOT / relative).read_bytes())):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != 'route':
                continue
            path = ast.literal_eval(node.args[0])
            options = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
            routes[path] = {'method': options.get('methods', ['GET'])[0], 'type': options['type']}
    return routes


def unwrap(payload):
    if isinstance(payload, dict) and payload.get('jsonrpc'):
        if 'error' in payload:
            raise AssertionError('Server RPC error: ' + str(payload['error'].get('message')))
        return payload.get('result')
    return payload


def assert_result(result, success, message=None):
    items = result if isinstance(result, list) else [result]
    assert items and all(isinstance(item, dict) for item in items), 'Unexpected API result schema'
    for item in items:
        assert item.get('success') is success, str(item.get('message', item))
        assert item.get('error') is (not success), 'success/error flags disagree'
        if message:
            assert message.lower() in str(item.get('message', '')).lower(), str(item.get('message'))
    return result


def build_jv(kind, cfg, prefix):
    def line(side, account):
        result = {'name': prefix + ' ' + kind, 'account_id': account, 'amount': 10,
                  'type': side, 'operating_unit_id': cfg['operating_unit_code'],
                  'customer_account': cfg['customer_contract'], 'employee_code': cfg['employee_code']}
        for key in ('department', 'cost_center', 'branch', 'tax_id'):
            if cfg.get(key):
                result[key] = cfg[key]
        return result
    lines = [line('debit', cfg['debit_account_code'])]
    if kind not in ('payment', 'insurance_payment'):
        lines.append(line('credit', cfg['credit_account_code']))
    return {'type': kind, 'crm_number': prefix + '-' + kind,
            'ref_number': prefix + '-' + kind, 'date': date.today().isoformat(),
            'customer_account': cfg['customer_contract'], 'operating_unit_id': cfg['operating_unit_code'],
            'bank_id': cfg['bank_journal_code'], 'line_ids': lines}


class Suite:
    def __init__(self, args, token):
        self.args, self.token = args, token
        self.session = requests.Session()
        self.routes = discover_routes()
        self.results = []
        self.prefix = 'NASAPI-' + secrets.token_hex(6)
        self.cfg = json.loads(args.fixtures.read_text()) if args.fixtures else {}

    def post(self, path, body):
        response = self.session.post(self.args.url.rstrip('/') + path, json=body, timeout=60,
                                     allow_redirects=False)
        assert response.status_code == 200, f'HTTP {response.status_code} at {path}'
        return unwrap(response.json())

    def login(self):
        password = os.environ.get('NAS_TEST_PASSWORD') or getpass.getpass('Odoo login password: ')
        info = self.post('/web/session/authenticate', {'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {'db': self.args.db, 'login': self.args.login, 'password': password}})
        assert info and info.get('uid'), 'Login failed'
        info = self.post('/web/session/get_session_info', {'jsonrpc': '2.0', 'method': 'call', 'id': 2, 'params': {}})
        assert info.get('db') == self.args.db, 'Session database mismatch; refusing API calls'
        assert str(info.get('server_version', '')).startswith('19.'), 'Expected Odoo 19'
        self.company_id = info.get('user_companies', {}).get('current_company')
        if self.args.write:
            assert self.company_id == self.cfg['company_id'], 'Login active company differs from fixture company'
        print('Verified database:', self.args.db, 'Company:', self.company_id, flush=True)

    def rpc(self, model, method, args=None, kwargs=None):
        return self.post(f'/web/dataset/call_kw/{model}/{method}', {
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {'model': model, 'method': method, 'args': args or [], 'kwargs': kwargs or {}},
        })

    def search(self, model, domain, fields):
        return self.rpc(model, 'search_read', [domain], {'fields': fields, 'limit': 10})

    def api(self, path, payload=None, auth='valid', flat=False):
        route = self.routes[path]
        headers = {}
        if auth != 'missing':
            headers['Authorization'] = 'Bearer ' + (self.token if auth == 'valid' else 'INVALID-' + self.prefix)
        body = payload if payload is not None else {}
        if route['type'] == 'jsonrpc' and not flat:
            body = {'jsonrpc': '2.0', 'method': 'call', 'params': body, 'id': 1}
        # The retained /api/jv/create HTTP controller requires flat JSON,
        # including flat lists for batches. Never wrap it in JSON-RPC params.
        method = route['method']
        response = self.session.request(method, self.args.url.rstrip('/') + path, headers=headers,
            json=body if method != 'GET' else None, timeout=60, allow_redirects=False)
        assert response.status_code == 200, f'HTTP {response.status_code} at {path}'
        return unwrap(response.json())

    def case(self, name, function):
        try:
            result = function()
            self.results.append({'test': name, 'status': 'PASS'})
            print('PASS', name, flush=True)
            return result
        except Exception as error:
            # Do not dump request headers, passwords, tokens or entire record data.
            message = str(error).replace(self.token, '[REDACTED]') if self.token else str(error)
            self.results.append({'test': name, 'status': 'FAIL', 'message': message})
            print('FAIL', name, message, flush=True)
            return None

    def positive(self, path, payload=None, flat=False):
        return assert_result(self.api(path, payload, flat=flat), True)

    def authorization(self):
        for path in sorted(self.routes):
            for auth in ('missing', 'invalid'):
                self.case(f'{path}: {auth} token', lambda p=path, a=auth:
                    assert_result(self.api(p, auth=a), False, 'Unauthorized'))

    def safe_reads(self):
        self.case('countries/read', lambda: self.positive('/api/countries/read'))
        self.case('states/read', lambda: self.positive('/api/states/read',
                  {'country_code': self.cfg.get('country_code', 'US')}))
        self.case('tax/read', lambda: self.positive('/api/tax/read'))
        # Validation cases below stop before creating/deleting records. Do not
        # send empty authenticated company/delete: its legacy lookup is unsafe.
        for path in ('/api/contact/create', '/api/company/create', '/api/employee/create',
                     '/api/department/create', '/api/employee/sections/create'):
            self.case(path + ': required field validation', lambda p=path:
                assert_result(self.api(p, {}), False, 'required'))
        for kind in JV_TYPES:
            self.case('JV ' + kind + ': required field validation', lambda k=kind:
                assert_result(self.api('/api/jv/create', {'type': k}), False, 'required'))
        self.case('JV invalid type', lambda:
            assert_result(self.api('/api/jv/create', {'type': 'NAS_UNSUPPORTED'}), False, 'Not Found'))

    def crud(self):
        p = self.prefix
        contact = {'name': p + ' Contact', 'customer_code': p + '-C', 'identification_number': p + '-ID',
                   'country_code': self.cfg.get('country_code', 'US'), 'mobile': '5550100', 'gender': 1}
        company = {'name': p + ' Company', 'customer_code': p + '-CO', 'customer_account': p + '-CONTRACT',
                   'contract_name': p, 'contract_type': 'API Test', 'email': 'nas-api-test@example.invalid',
                   'currency': 'SAR', 'lock_sale_currency': 0, 'forecast_invoice_frequency': 0}
        department = {'name': p + ' Department', 'crm_id': p + '-D', 'user_name': 'NAS API regression'}
        section_result = self.case('section/create', lambda:
            self.positive('/api/employee/sections/create', {'name': p + ' Section'}))
        section_id = section_result['data']['section_id'] if section_result else None
        self.case('sections/read', lambda: self.positive('/api/employee/sections/read'))
        owned = []
        for entity, payload, key in (('contact', contact, 'identification_number'),
                                     ('company', company, 'customer_code'),
                                     ('department', department, 'crm_id')):
            created = self.case(entity + '/create', lambda e=entity, v=payload:
                self.positive('/api/' + e + '/create', v))
            if created:
                owned.append((entity, {key: payload[key]}))
                if entity in ('contact', 'company'):
                    self.case(entity + ': duplicate rejected', lambda e=entity, v=payload:
                        assert_result(self.api('/api/' + e + '/create', v), False, 'already exists'))
                self.case(entity + '/read', lambda e=entity, v=payload, k=key:
                    self.positive('/api/' + e + '/read', {k: v[k]}))
                self.case(entity + '/update', lambda e=entity, v=payload, k=key:
                    self.positive('/api/' + e + '/update', {k: v[k], 'name': v['name'] + ' Updated'}))
                self.case(entity + ': updated name persisted', lambda e=entity, v=payload, k=key:
                    self.verify_name('/api/' + e + '/read', {k: v[k]}, v['name'] + ' Updated'))
        if section_id:
            self.case('section/update', lambda: self.positive('/api/employee/sections/update',
                {'section_id': section_id, 'name': p + ' Section Updated'}))
            self.case('section updated name persisted', lambda:
                self.verify_section(section_id, p + ' Section Updated'))
        employee = {'name': p + ' Employee', 'employee_code': p + '-E', 'crm_id': p + '-EMPCRM',
                    'user_name': 'NAS API regression', 'department_id': department['crm_id'],
                    'operating_unit_id': self.cfg['operating_unit_code'], 'employee_section': section_id or False,
                    'employee_type': '2', 'gender': 1, 'marital': 1,
                    'identification_no': p + '-IQAMA', 'job_title': 'API regression',
                    'birthday': '1990-01-01', 'arrival_date': '2026-01-01'}
        created = self.case('employee/create', lambda: self.positive('/api/employee/create', employee))
        if created:
            owned.append(('employee', {'employee_code': employee['employee_code']}))
            self.case('employee duplicate code rejected', lambda:
                assert_result(self.api('/api/employee/create', employee), False, 'already exists'))
            self.case('employee/read', lambda: self.positive('/api/employee/read', {'employee_code': employee['employee_code']}))
            self.case('employee/read legacy flat JSON', lambda:
                self.positive('/api/employee/read', {'employee_code': employee['employee_code']}, flat=True))
            self.case('employee/update', lambda: self.positive('/api/employee/update',
                {'employee_code': employee['employee_code'], 'name': p + ' Employee Updated', 'identification_id': p + '-IQAMA-UPDATED'}))
            self.case('employee updated fields persisted', lambda:
                self.verify_employee(employee['employee_code'], p + ' Employee Updated', p + '-IQAMA-UPDATED'))
        # Delete only successful creations bearing this run's unique keys.
        # Employee first, then its department/section; never delete fixture data.
        for entity, identity in reversed(owned):
            if entity == 'company':
                self.case('test company subscription cleanup', lambda:
                    self.cleanup_company_contract(company['customer_account'], company['customer_code']))
            self.case(entity + '/delete owned test record', lambda e=entity, v=identity:
                self.positive('/api/' + e + '/delete', v))
            self.case(entity + ': deleted record absent', lambda e=entity, v=identity:
                assert_result(self.api('/api/' + e + '/read', v), False))
        if section_id:
            self.case('section/delete owned test record', lambda: self.positive('/api/employee/sections/delete', {'section_id': section_id}))
            self.case('section deleted record absent', lambda:
                self.verify_section(section_id, absent=True))

    def verify_name(self, path, payload, name):
        result = self.positive(path, payload)
        data = result['data']
        if isinstance(data, list):
            data = data[0]
        assert data['name'] == name, 'Updated name was not persisted'

    def verify_employee(self, code, name, iqama):
        data = self.positive('/api/employee/read', {'employee_code': code})['data']
        assert data['name'] == name and data['identification_id'] == iqama, 'Employee update did not persist'
        assert data['employee_type'] == '2', 'Employee Sector changed unexpectedly'

    def verify_section(self, section_id, name=None, absent=False):
        result = self.api('/api/employee/sections/read')
        if result.get('success') is False and absent:
            assert result.get('message') == 'Section not found', str(result.get('message'))
            return
        assert_result(result, True)
        matched = [r for r in result['data'] if r['id'] == section_id]
        assert (not matched) if absent else (matched and matched[0]['name'] == name)

    def cleanup_company_contract(self, contract, customer_code):
        # Company/create also creates a subscription, but there is no subscription
        # delete API. Remove ONLY the exact owned test contract before company/delete.
        assert contract.startswith(self.prefix + '-'), 'Refusing cleanup of existing data'
        records = self.search('partner.subscription', [('name', '=', contract)], ['id', 'partner_id'])
        partner = self.search('res.partner', [('customer_code', '=', customer_code)], ['id'])
        assert len(records) == len(partner) == 1 and records[0]['partner_id'][0] == partner[0]['id']
        assert self.rpc('partner.subscription', 'unlink', [[records[0]['id']]])

    def preflight(self):
        cfg = self.cfg
        for model, field, value in (
            ('operating.unit', 'code', cfg['operating_unit_code']),
            ('partner.subscription', 'name', cfg['customer_contract']),
            ('hr.employee', 'employee_code', cfg['employee_code']),
            ('account.account', 'code', cfg['debit_account_code']),
            ('account.account', 'code', cfg['credit_account_code']),
        ):
            assert len(self.search(model, [(field, '=', value)], ['id'])) == 1, f'Missing/ambiguous {model} {field}={value}'
        for name in ('1_sale', '1_general'):
            refs = self.search('ir.model.data', [('module', '=', 'account'), ('name', '=', name)], ['res_id', 'model'])
            assert len(refs) == 1 and refs[0]['model'] == 'account.journal', 'Missing account.' + name
            journal = self.rpc('account.journal', 'read', [[refs[0]['res_id']]], {'fields': ['company_id']})[0]
            assert journal['company_id'][0] == cfg['company_id'], 'Hardcoded journal belongs to a different company'
        bank = self.search('account.journal', [('code', '=', cfg['bank_journal_code'])],
                           ['default_account_id', 'company_id', 'type'])
        assert len(bank) == 1 and bank[0]['default_account_id'], 'Bank journal missing/ambiguous or lacks default account'
        assert bank[0]['company_id'][0] == cfg['company_id'] and bank[0]['type'] in ('cash', 'bank')
        assert self.search('res.users', [('id', '=', 6), ('active', '=', True)], ['id']), 'Multi APIs require active user ID 6'
        payroll = self.search('account.journal', [('name', 'ilike', 'Payroll'), ('active', '=', True)], ['default_account_id'])
        assert payroll and payroll[0]['default_account_id'], 'Payroll journal missing or lacks default account'
        return True

    def verify_move(self, result, kind, expected_moves=1):
        assert_result(result, True)
        rows = result if isinstance(result, list) else [result]
        assert len(rows) == expected_moves, 'Wrong batch response count'
        ids = []
        for row in rows:
            data = row['data']
            move_id = data.get('jv_id') or data.get('contact_id')
            assert isinstance(move_id, int), 'Missing created journal entry ID'
            move = self.rpc('account.move', 'read', [[move_id]], {'fields': ['state', 'jv_type', 'line_ids', 'company_id', 'crm_number']})[0]
            assert move['jv_type'] == kind and move['company_id'][0] == self.cfg['company_id']
            lines = self.rpc('account.move.line', 'read', [move['line_ids']], {'fields': ['debit', 'credit']})
            assert lines and abs(sum(r['debit'] - r['credit'] for r in lines)) < 0.01, 'Saved journal is unbalanced'
            assert abs(sum(r['debit'] for r in lines) - 10) < 0.01, 'Saved amount differs from test amount'
            assert move['state'] == 'draft', 'Unexpected auto-posting: legacy API creates draft entries'
            ids.append(move_id)
        self.results.append({'test': 'created JV IDs ' + kind, 'status': 'INFO', 'ids': ids})
        return ids

    def jvs(self):
        if not self.case('JV configuration preflight', self.preflight):
            for kind in JV_TYPES:
                self.results.append({'test': 'JV ' + kind, 'status': 'SKIP', 'message': 'Preflight failed'})
            return
        invoice_created = False
        for kind in JV_TYPES:
            payload = build_jv(kind, self.cfg, self.prefix)
            result = self.case('JV ' + kind + ': create and verify saved balance', lambda p=payload, k=kind:
                self.verify_move(self.api('/api/jv/create', p), k))
            if kind == 'invoice':
                invoice_created = bool(result)
        if invoice_created:
            self.case('JV duplicate invoice CRM rejected', lambda:
                assert_result(self.api('/api/jv/create', build_jv('invoice', self.cfg, self.prefix)),
                              False, 'CRM Number already exists'))
        payloads = [build_jv('invoice', self.cfg, self.prefix + '-BATCH' + str(i)) for i in range(2)]
        self.case('JV invoice batch: two saved moves', lambda:
            self.verify_move(self.api('/api/jv/create', payloads), 'invoice', 2))
        self.case('JV missing customer contract', lambda:
            assert_result(self.api('/api/jv/create', dict(build_jv('invoice', self.cfg, self.prefix + '-MISSING'),
                customer_account=self.prefix + '-DOES-NOT-EXIST')), False, 'does not exist'))
        self.case('JV invalid operating unit', lambda:
            assert_result(self.api('/api/jv/create', dict(build_jv('invoice', self.cfg, self.prefix + '-BADOU'),
                operating_unit_id=self.prefix + '-DOES-NOT-EXIST')), False, 'Wrong code'))
        invalid_account = build_jv('invoice', self.cfg, self.prefix + '-BADACCOUNT')
        invalid_account['line_ids'][0]['account_id'] = self.prefix + '-DOES-NOT-EXIST'
        self.case('JV invalid account code', lambda:
            assert_result(self.api('/api/jv/create', invalid_account), False, 'does not exist'))

    def run(self):
        self.login()
        self.authorization()
        if self.token:
            self.safe_reads()
        if self.args.write:
            self.crud()
            self.jvs()
        statuses = {name: sum(r['status'] == name for r in self.results) for name in ('PASS', 'FAIL', 'SKIP')}
        summary = {'database': self.args.db, 'route_count': len(self.routes), 'write_tests': self.args.write,
                   'run_prefix': self.prefix, 'counts': statuses, 'results': self.results}
        self.args.report.write_text(json.dumps(summary, indent=2) + '\n')
        print('Summary:', statuses, 'Report:', self.args.report)
        if not self.args.write:
            print('NOT a full run: CRUD and positive JV tests were not executed. Use --write on the test DB.')
        else:
            print('Accounting test JVs remain in the test database; created IDs are in the report. No JVs are deleted or posted.')
        return 1 if statuses['FAIL'] or statuses['SKIP'] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8069')
    parser.add_argument('--db', default=DEFAULT_DB)
    parser.add_argument('--login', default='admin')
    parser.add_argument('--fixtures', type=Path)
    parser.add_argument('--write', action='store_true', help='Create/update/delete owned CRUD fixtures and create draft test JVs')
    parser.add_argument('--confirm-db', help='Must exactly match --db for write tests')
    parser.add_argument('--auth-only', action='store_true', help='Only missing/invalid-token checks; no API token needed')
    parser.add_argument('--report', type=Path, default=Path('nas_api_test_results.json'))
    args = parser.parse_args()
    if args.write:
        if args.auth_only or args.confirm_db != args.db or not args.db.startswith('naass_test_'):
            parser.error('--write requires --confirm-db matching a naass_test_* database and cannot use --auth-only')
        if not args.fixtures:
            parser.error('--write requires --fixtures tools/nas_api_fixtures.json with your actual master-data codes')
        cfg = json.loads(args.fixtures.read_text())
        required = ('company_id', 'operating_unit_code', 'customer_contract', 'employee_code',
                    'debit_account_code', 'credit_account_code', 'bank_journal_code')
        if any(not cfg.get(key) or str(cfg[key]).startswith('REPLACE_') for key in required):
            parser.error('Replace all required fixture placeholders with real codes/IDs before --write')
    token = '' if args.auth_only else (os.environ.get('NAS_API_TOKEN') or getpass.getpass('HR API token (General Settings): '))
    if not args.auth_only and not token:
        parser.error('API token cannot be empty')
    try:
        return Suite(args, token).run()
    except Exception as error:
        print('STOP:', str(error).replace(token, '[REDACTED]') if token else str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
