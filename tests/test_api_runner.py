"""Offline harness checks; never call an Odoo instance."""
import importlib.util
import contextlib
import io
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('nas_api_runner', ROOT / 'tools/test_nas_apis.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TestApiRunner(unittest.TestCase):
    def test_discovers_every_current_route(self):
        routes = runner.discover_routes()
        self.assertEqual(len(routes), 24)
        self.assertEqual(routes['/api/jv/create'], {'method': 'POST', 'type': 'http'})
        self.assertEqual(routes['/api/tax/read']['type'], 'jsonrpc')
        self.assertEqual(routes['/api/employee/sections/read']['method'], 'GET')

    def test_response_flags_not_just_http_status(self):
        with self.assertRaises(AssertionError):
            runner.assert_result({'success': False, 'error': True, 'message': 'Bad account'}, True)
        with self.assertRaises(AssertionError):
            runner.unwrap({'jsonrpc': '2.0', 'error': {'message': 'Traceback'}})
        with self.assertRaises(AssertionError):
            runner.assert_result({}, True)
        self.assertEqual(runner.unwrap({'jsonrpc': '2.0', 'result': [1, 2]}), [1, 2])

    def test_jv_templates_all_nine_types(self):
        cfg = {'operating_unit_code': 'TESTOU', 'customer_contract': 'TESTCONTRACT',
               'employee_code': 'TESTEMP', 'debit_account_code': '001000',
               'credit_account_code': '002000', 'bank_journal_code': 'TESTBANK'}
        self.assertEqual(len(set(runner.JV_TYPES)), 9)
        for kind in runner.JV_TYPES:
            data = runner.build_jv(kind, cfg, 'TEST')
            self.assertEqual(data['type'], kind)
            self.assertEqual(data['line_ids'][0]['account_id'], '001000')
            if kind in ('payment', 'insurance_payment'):
                self.assertEqual(len(data['line_ids']), 1)
            else:
                self.assertEqual(sum((1 if l['type'] == 'debit' else -1) * l['amount']
                                     for l in data['line_ids']), 0)

    def test_transport_preserves_account_http_flat_body(self):
        suite = runner.Suite(SimpleNamespace(fixtures=None, url='http://localhost:8069'), 'TESTTOKEN')
        calls = []
        class FakeSession:
            def request(self, *args, **kwargs):
                calls.append((args, kwargs))
                return SimpleNamespace(status_code=200, json=lambda:
                    {'jsonrpc': '2.0', 'result': {'success': False, 'error': True}})
        suite.session = FakeSession()
        body = [{'type': 'invoice', 'line_ids': []}]
        suite.api('/api/jv/create', body)
        self.assertEqual(calls[-1][1]['json'], body)
        suite.api('/api/employee/read', {'employee_code': 'TEST'})
        self.assertEqual(calls[-1][1]['json']['params'], {'employee_code': 'TEST'})
        suite.api('/api/countries/read')
        self.assertIsNone(calls[-1][1]['json'])

    def test_write_mode_refuses_missing_confirmation_before_network(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/test_nas_apis.py'), '--write'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('--confirm-db', result.stderr)

    def test_validation_cases_do_not_send_empty_delete_requests(self):
        suite = runner.Suite(SimpleNamespace(fixtures=None, url='http://localhost:8069'), 'TESTTOKEN')
        calls = []
        def api(path, payload=None, **kwargs):
            calls.append((path, payload))
            if path.endswith('/read'):
                return {'success': True, 'error': False, 'data': []}
            return {'success': False, 'error': True, 'message':
                    'Type Related Action Not Found' if payload == {'type': 'NAS_UNSUPPORTED'} else 'Field required'}
        suite.api = api
        with contextlib.redirect_stdout(io.StringIO()):
            suite.safe_reads()
        self.assertTrue(all(not path.endswith(('/delete', '/update')) for path, payload in calls))


if __name__ == '__main__':
    unittest.main()
