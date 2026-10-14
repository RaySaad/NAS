"""Run through odoo-bin shell on an isolated nas_odoo19_verify_* database.

All fixture changes are rolled back. Never run against a production database.
"""
import base64
import io
import json
from pathlib import Path
import traceback
import zipfile

from odoo.fields import Command
import openpyxl

assert env.cr.dbname.startswith('nas_odoo19_verify_'), 'Refusing a non-test database'
results = []


def check(name, function):
    try:
        with env.cr.savepoint():
            detail = function()
        results.append({'check': name, 'status': 'PASS', 'detail': detail})
        print('PASS', name, detail, flush=True)
    except Exception:
        detail = traceback.format_exc()
        results.append({'check': name, 'status': 'FAIL', 'detail': detail})
        print('FAIL', name, detail, flush=True)


try:
    modules = [p.parent.name for p in Path.cwd().glob('*/__manifest__.py')]
    installed = env['ir.module.module'].search([('name', 'in', modules), ('state', '=', 'installed')])
    assert set(installed.mapped('name')) == set(modules), 'Some custom modules are not installed'
    print('Installed custom modules:', len(installed), flush=True)
    # Never let the PDF renderer connect to a live server on the default port.
    env['ir.config_parameter'].sudo().set_param('report.url', 'http://127.0.0.1:18069')
    env['ir.config_parameter'].sudo().set_param('web.base.url', 'http://127.0.0.1:18069')
    company = env.company
    partner = env['res.partner'].create({'name': 'NAS Runtime Test Partner', 'customer_code': 'NAS-SMOKE-C1', 'mobile': '12345'})
    contract = env['partner.subscription'].create({'name': 'NAS-SMOKE-CONTRACT', 'partner_id': partner.id, 'contract_type': 'Smoke'})
    ou = env['operating.unit'].create({'name': 'NAS Runtime Test OU', 'code': 'NAS-SMOKE', 'partner_id': partner.id, 'company_id': company.id})
    employee = env['hr.employee'].create({'name': 'NAS Runtime Test Employee', 'employee_code': 'NAS-SMOKE-E1',
                                         'customer_account': contract.id, 'operating_unit_id': ou.id, 'gender': 'male', 'company_id': company.id})
    account1 = env['account.account'].create({'name': 'NAS Runtime Expense', 'code': 'NAS19001', 'account_type': 'expense', 'company_ids': [Command.set([company.id])]})
    account2 = env['account.account'].create({'name': 'NAS Runtime Clearing', 'code': 'NAS19002', 'account_type': 'asset_current', 'company_ids': [Command.set([company.id])]})
    journal = env['account.journal'].create({'name': 'NAS Runtime Journal', 'code': 'NAS19', 'type': 'general', 'company_id': company.id})
    plan1 = env['account.analytic.plan'].create({'name': 'NAS Runtime Department'})
    plan2 = env['account.analytic.plan'].create({'name': 'NAS Runtime Cost'})
    analytic1 = env['account.analytic.account'].create({'name': 'NAS Runtime Department Account', 'plan_id': plan1.id, 'company_id': company.id})
    analytic2 = env['account.analytic.account'].create({'name': 'NAS Runtime Cost Account', 'plan_id': plan2.id, 'company_id': company.id})
    distribution = {f'{analytic1.id},{analytic2.id}': 100}
    move = env['account.move'].create({'journal_id': journal.id, 'date': '2026-10-01', 'company_id': company.id,
                                     'partner_id': partner.id, 'customer_account': contract.id,
                                     'line_ids': [Command.create({'name': 'NAS debit', 'account_id': account1.id, 'debit': 100,
                                                                 'employee_id': employee.id, 'operating_unit_id': ou.id,
                                                                 'analytic_distribution': distribution}),
                                                  Command.create({'name': 'NAS credit', 'account_id': account2.id, 'credit': 100,
                                                                 'employee_id': employee.id, 'operating_unit_id': ou.id})]})
    check('journal posting and custom dimensions', lambda: (move.action_post(), move.state, move.line_ids.mapped('employee_code')))
    assert move.state == 'posted'
    check('employee domain keyword search', lambda: env['hr.employee'].name_search('NAS-SMOKE-E1', domain=[('id', '=', employee.id)]))
    check('legacy employee gender alias', lambda: (employee.gender, employee.sex))

    def prepaid_expenses():
        cash = env['account.account'].create({'name': 'NAS Smoke Cash', 'code': 'NAS19003', 'account_type': 'asset_cash'})
        payment_journal = env['account.journal'].create({'name': 'NAS Smoke Cash', 'code': 'NSC19', 'type': 'cash', 'default_account_id': cash.id})
        created = []
        for mode in ('each_line', 'all_line'):
            transaction = env['account.expense.transaction'].create({
                'date': '2026-10-01', 'reference': 'NAS expense ' + mode,
                'expense_nature': 'prepaid', 'amortization_method': 'monthly',
                'payment_type': 'bank_cash', 'payment_journal_id': payment_journal.id,
                'bank_account_id': cash.id, 'journal_id': journal.id, 'type_jv': mode,
                'expense_detail_ids': [Command.create({
                    'description': 'NAS prepaid ' + str(amount), 'prepaid_expense_account_id': account2.id,
                    'expense_account_id': account1.id, 'start_date': '2026-10-01', 'end_date': '2026-10-31',
                    'quantity': 1, 'price_unit': amount, 'operating_unit_id': ou.id,
                    'employee_id': employee.id, 'partner_id': partner.id, 'customer_account': contract.id,
                }) for amount in (30, 70)],
            })
            transaction.action_review()
            transaction.action_confirm()
            transaction.action_final_approval()
            moves = env['account.move'].search([('ref', '=', transaction.reference)])
            assert len(moves) == (2 if mode == 'each_line' else 1)
            assert all(m.state == 'posted' for m in moves)
            assert sum(moves.line_ids.mapped('debit')) == 100
            assert transaction.state == 'final_approval' and transaction.amortization_board_ids
            created.append({'mode': mode, 'moves': len(moves), 'amortization_lines': len(transaction.amortization_board_ids)})
        return created
    check('prepaid expense approvals and journal modes', prepaid_expenses)

    petty_records = []
    def petty_cash():
        tax = env['account.tax'].create({'name': 'NAS Smoke Purchase VAT', 'amount': 15, 'type_tax_use': 'purchase'})
        for tax_on in (False, True):
            sheet = env['petty.cash.purchase'].create({
                'employee_journal_id': journal.id, 'account_id': account2.id,
                'expenses_line_ids': [Command.create({'name': 'NAS petty expense', 'account_id': account1.id,
                    'quantity': 2, 'price_unit': 50, 'employee_id': employee.id,
                    'operating_unit_id': ou.id, 'customer_account': contract.id,
                    'tax_ids': [Command.set(tax.ids if tax_on else [])]})],
            })
            sheet.submit()
            sheet.approve()
            sheet.post()
            assert sheet.state == 'post' and sheet.move_id
            assert sheet.total_amount == (115 if tax_on else 100)
            assert sum(sheet.move_id.line_ids.mapped('debit')) == sheet.total_amount
            sheet.move_id.action_post()
            assert sheet.move_id.state == 'posted'
            petty_records.append(sheet)
        return [{'tax': s.total_tax_amount, 'total': s.total_amount} for s in petty_records]
    check('petty cash approval and tax posting', petty_cash)

    full = env['full.employee.statement.wizard'].create({'account_ids': [Command.set([account1.id])], 'date_from': '2026-01-01', 'date_to': '2026-12-31'})
    check('full employee statement aggregation', lambda: (full.action_generate_statement(), full.total_debit, full.total_balance))
    expected_debit = sum(env['account.move.line'].search([
        ('account_id', '=', account1.id), ('parent_state', '=', 'posted'),
        ('company_id', '=', company.id), ('date', '>=', '2026-01-01'), ('date', '<=', '2026-12-31'),
    ]).mapped('debit'))
    assert full.total_debit == expected_debit and full.total_balance == expected_debit
    single = env['employee.statement.wizard'].create({'employee_id': employee.id, 'linking_method': 'employee',
                                                     'date_from': '2026-01-01', 'date_to': '2026-12-31'})
    check('individual employee statement', lambda: (single.action_generate_statement(), len(single.line_ids)))

    def workbook_export(action):
        result = action()
        attachment_id = int(result['url'].split('/web/content/')[1].split('?')[0])
        content = base64.b64decode(env['ir.attachment'].browse(attachment_id).datas)
        book = openpyxl.load_workbook(io.BytesIO(content))
        detail = {'bytes': len(content), 'sheets': book.sheetnames}
        book.close()
        return detail
    for name, action in [('journal voucher Excel', move.export_voucher_excel),
                         ('large journal voucher Excel', move.export_large_voucher_excel),
                         ('full employee statement Excel', full.action_export_excel),
                         ('employee statement Excel', single.action_export_excel)]:
        check(name, lambda action=action: workbook_export(action))

    def render(ref, record):
        report = env.ref(ref)
        content, kind = report._render_qweb_pdf(report.id, res_ids=record.ids)
        assert content.startswith(b'%PDF'), 'Invalid PDF content'
        assert len(content) > 1000, 'Suspiciously small PDF'
        return {'bytes': len(content), 'format': kind}
    for ref, record in [('bi_print_journal_entries.journal_entry_report_id', move),
                        ('journal_entry_print.action_report_journal_entry', move),
                        ('journal_voucher_print_export.action_report_journal_entry_voucher', move),
                        ('customer_statement_enhanced.action_report_customer_statement_enhanced', partner),
                        ('employee_financial_statement.action_report_employee_statement', single),
                        ('account_ext.action_full_employee_statement_pdf', full)]:
        check('PDF ' + ref, lambda ref=ref, record=record: render(ref, record))
    if petty_records:
        check('PDF petty cash', lambda: render('pcp_report.pcp_report_temp_id', petty_records[-1]))
    def bulk_pdf():
        second = move.copy({'date': '2026-10-01'})
        second.action_post()
        action = env['account.move.print.separate.pdf.wizard'].action_print_separate((move | second).ids)
        wizard = env['account.move.print.separate.pdf.wizard'].browse(int(action['url'].split('/')[4]))
        content = base64.b64decode(wizard.pdf_file)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            assert len(archive.namelist()) == 2
            assert all(archive.read(name).startswith(b'%PDF') for name in archive.namelist())
        return {'bytes': len(content), 'pdf_count': 2}
    check('separate journal PDFs ZIP', bulk_pdf)
    print('RUNTIME_SMOKE_RESULTS', json.dumps(results, default=str), flush=True)
    assert all(r['status'] == 'PASS' for r in results), 'Runtime smoke failures remain'
finally:
    env.cr.rollback()
    print('Test fixture transaction rolled back.', flush=True)
