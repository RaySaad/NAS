import base64
import io
from datetime import timedelta
from psycopg2 import IntegrityError
from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from reportlab.pdfgen import canvas
from .test_ptr import TestSaddadPhaseOne
from ..models.qiwa_pdf import parse_qiwa_text


@tagged('post_install', '-at_install')
class TestQiwa(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other = cls.env['res.company'].create({'name': 'Qiwa Other'})
        cls.product = cls.env['product.product'].create({'name': 'Qiwa Test Fee', 'type': 'service', 'categ_id': cls.env.ref('Saddad.category_muqeem').id, 'standard_price': 2425})
        cls.env['saddad.service.mapping'].search([('company_id', '=', cls.company.id)]).unlink()
        cls.mapping = cls.env['saddad.service.mapping'].create({'company_id': cls.company.id, 'service_type': 'work_permit', 'period': '3', 'product_id': cls.product.id, 'default_for_ptr': True})
        cls.employee = cls.env['hr.employee'].create({'name': 'Qiwa Test Employee', 'identification_id': '2000000091', 'company_id': cls.company.id, 'saddad_iqama_expiry': fields.Date.today()})
        cls.employee2 = cls.env['hr.employee'].create({'name': 'Qiwa Second Employee', 'identification_id': '2000000092', 'company_id': cls.company.id, 'saddad_iqama_expiry': fields.Date.today()})
        cls.operator = cls._make_user('qiwa_operator', 'Saddad.group_user')
        cls.confirmer = cls._make_user('qiwa_confirmer', 'Saddad.group_confirmer')
        cls.plain = cls._make_user('qiwa_plain', 'base.group_user')
        cls.env['saddad.approval.rule'].search([]).write({'notify_email': False, 'notify_activity': False})
        cls.batch_model = cls.env['saddad.qiwa.batch'].with_user(cls.operator)

    @classmethod
    def _make_user(cls, login, group):
        return cls.env['res.users'].with_context(no_reset_password=True).create({'name': login, 'login': login, 'email': login+'@example.invalid', 'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)], 'group_ids': [Command.set([cls.env.ref(group).id])]})

    def _batch(self, **extra):
        vals = {'reference': ' 123456789012345 ', 'issue_date': fields.Date.today(), 'due_date': fields.Date.today() + timedelta(days=10), 'line_ids': [Command.create({'employee_id': self.employee.id, 'mapping_id': self.mapping.id})]}
        vals.update(extra)
        return self.batch_model.create(vals)

    def _ptr(self, employee=None, batch=None):
        vals = {'employee_id': (employee or self.employee).id}
        if batch:
            vals['qiwa_batch_id'] = batch.id
        ptr = self.env['saddad.ptr'].with_user(self.operator).create(vals)
        ptr.action_review()
        ptr.with_user(self.confirmer).action_confirm()
        return ptr

    def test_workflow_snapshot_and_lock(self):
        rec = self._batch()
        self.assertEqual(rec.total_amount, 2425)
        rec.action_review()
        self.product.standard_price = 3000
        rec.with_user(self.confirmer).action_confirm()
        self.assertEqual(rec.total_amount, 2425)
        self.assertEqual(rec.downstream_state, 'linked')
        with self.assertRaises(UserError):
            rec.line_ids.write({'amount_source': 'external', 'amount': 2500, 'external_reason': 'test'})
        with self.assertRaises(UserError):
            rec.write({'reference': 'CHANGED'})
        with self.assertRaises(UserError):
            rec.action_reset_draft()

    def test_permissions_and_direct_state(self):
        rec = self._batch()
        with self.assertRaises(AccessError):
            rec.write({'state': 'confirmed'})
        with self.assertRaises(AccessError):
            rec.with_user(self.plain).action_review()
        rec.action_review()
        with self.assertRaises(AccessError):
            rec.action_confirm()
        rec.action_reset_draft()
        self.assertEqual(rec.state, 'draft')

    def test_reference_uniqueness_and_arabic_digits(self):
        rec = self._batch(reference='١٢٣٤٥٦٧٨٩٠١٢٣٤٥')
        self.assertEqual(rec.reference, '123456789012345')
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self._batch()

    def test_duplicate_employee_and_bad_amount(self):
        rec = self._batch()
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            rec.write({'line_ids': [Command.create({'employee_id': self.employee.id, 'mapping_id': self.mapping.id})]})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.line_ids.write({'amount_source': 'external', 'amount': -1, 'external_reason': 'bad'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.line_ids.write({'amount_source': 'external', 'amount': 2500})
        rec.line_ids.write({'amount_source': 'external', 'amount': 2500, 'external_reason': 'Qiwa fee'})
        self.assertEqual(rec.total_amount, 2500)

    def test_dates_and_empty_lines(self):
        rec = self._batch(line_ids=[])
        with self.assertRaises(UserError):
            rec.action_review()
        rec.write({'line_ids': [Command.create({'employee_id': self.employee.id, 'mapping_id': self.mapping.id})], 'issue_date': fields.Date.today()-timedelta(days=20), 'due_date': fields.Date.today()-timedelta(days=1)})
        with self.assertRaises(UserError):
            rec.action_review()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.write({'due_date': rec.issue_date-timedelta(days=1)})

    def test_ptr_creation_and_consolidation(self):
        batch = self.batch_model.create({})
        first = self._ptr(batch=batch)
        second = self._ptr(self.employee2, batch)
        self.assertEqual(first.qiwa_handoff_state, 'linked')
        self.assertEqual(second.qiwa_batch_id, batch)
        self.assertEqual(len(batch.line_ids), 2)
        self.assertEqual(batch.total_amount, 4850)
        first.with_user(self.confirmer).action_prepare_qiwa()
        self.assertEqual(len(batch.line_ids), 2)
        with self.assertRaises(UserError):
            batch.line_ids[:1].unlink()
        with self.assertRaises(UserError):
            batch.line_ids[:1].write({'employee_id': self.employee2.id})

    def test_ptr_automatic_batch_and_company(self):
        ptr = self._ptr()
        self.assertTrue(ptr.qiwa_batch_id)
        self.assertEqual(ptr.qiwa_batch_id.line_ids.ptr_line_id, ptr.line_ids)
        with self.assertRaises(AccessError):
            self.batch_model.create({'company_id': self.other.id})
        other_batch = self.env['saddad.qiwa.batch'].with_company(self.other).create({})
        with self.assertRaises(AccessError):
            other_batch.with_user(self.operator).read(['name'])

    def test_bad_ptr_target_rolls_back(self):
        batch = self._batch()
        batch.action_review()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['saddad.ptr'].create({'employee_id': self.employee2.id, 'qiwa_batch_id': batch.id})

    def test_stale_identity(self):
        rec = self._batch()
        self.employee.identification_id = '2000000093'
        with self.assertRaises(ValidationError):
            rec.action_review()
        rec.line_ids.write({'employee_id': self.employee.id})
        rec.action_review()

    def test_configurable_qiwa_approval(self):
        self.env['saddad.approval.rule'].create({'name': 'Qiwa company override', 'company_id': self.company.id, 'transition': 'qiwa_review', 'group_id': self.env.ref('Saddad.group_confirmer').id})
        rec = self._batch()
        with self.assertRaises(AccessError):
            rec.action_review()
        rec.with_user(self.confirmer).action_review()

    def test_pdf_roundtrip_and_duplicate_apply(self):
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(40, 750, 'Qiwa employee 2000000091')
        pdf.save()
        batch = self.batch_model.create({})
        wizard = self.env['saddad.qiwa.import'].with_user(self.operator).create({'batch_id': batch.id, 'pdf_file': base64.b64encode(buffer.getvalue()), 'filename': 'test.pdf'})
        wizard.action_extract()
        self.assertEqual(wizard.line_ids.employee_id, self.employee)
        with self.assertRaises(UserError):
            wizard.action_apply()
        wizard.write({'reviewed': True, 'reference': '123456789012345', 'issue_date': fields.Date.today(), 'due_date': fields.Date.today()+timedelta(days=5)})
        wizard.action_apply()
        self.assertEqual(batch.line_ids.employee_id, self.employee)
        self.assertEqual(batch.state, 'draft')
        self.assertTrue(self.env['ir.attachment'].search([('res_model', '=', batch._name), ('res_id', '=', batch.id)]))

    def test_pdf_invalid_and_ambiguous_identity(self):
        batch = self.batch_model.create({})
        wizard = self.env['saddad.qiwa.import'].with_user(self.operator).create({'batch_id': batch.id, 'pdf_file': base64.b64encode(b'not pdf')})
        with self.assertRaises(UserError):
            wizard.action_extract()
        self.employee2.identification_id = self.employee.identification_id
        wizard._stage_text('Employee 2000000091 and unknown 2999999999')
        self.assertEqual(len(wizard.line_ids), 2)
        self.assertFalse(wizard.line_ids.employee_id)

    def test_sample_layout_parser(self):
        sample = '1148160200042129000\n29/09/2026\nTEST EMPLOYEE2000000091 months 330/12/20262,425.00\nTotal 2,425.00\nPayment Status Unpaid\n114816020004212\n13/10/2026\nExport Date 29/09/2026'
        parsed = parse_qiwa_text(sample)
        self.assertEqual(parsed['reference'], '114816020004212')
        self.assertEqual(parsed['invoice_number'], '1148160200042129000')
        self.assertEqual(str(parsed['due_date']), '2026-10-13')
        self.assertEqual(parsed['employees'][0]['amount'], 2425)
        self.assertEqual(parsed['period'], '3')
        self.assertFalse(parse_qiwa_text('Unknown layout 2000000091')['reference'])


    def test_pdf_updates_ptr_line_without_duplicate(self):
        ptr = self._ptr()
        batch = ptr.qiwa_batch_id
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(40, 750, 'Employee 2000000091')
        pdf.save()
        wizard = self.env['saddad.qiwa.import'].with_user(self.operator).create({'batch_id': batch.id, 'pdf_file': base64.b64encode(buffer.getvalue())})
        wizard.action_extract()
        wizard.line_ids.write({'amount_source': 'external', 'amount': 2450, 'external_reason': 'Document fee'})
        wizard.write({'reviewed': True, 'reference': '123456789012345', 'issue_date': fields.Date.today(), 'due_date': fields.Date.today()+timedelta(days=5)})
        wizard.action_apply()
        self.assertEqual(len(batch.line_ids), 1)
        self.assertEqual(batch.total_amount, 2450)
        self.assertEqual(batch.line_ids.ptr_line_id, ptr.line_ids)

    def test_notifications_and_completion(self):
        rule = self.env.ref('Saddad.approval_qiwa_confirm')
        rule.write({'notify_activity': True, 'notify_email': True})
        rec = self._batch()
        rec.action_review()
        self.assertIn(self.confirmer, rec.sudo().activity_ids.user_id)
        self.assertTrue(self.env['mail.mail'].search([('model', '=', rec._name), ('res_id', '=', rec.id)]))
        rec.with_user(self.confirmer).action_confirm()
        self.assertFalse(rec.sudo().activity_ids)

    def test_import_currency_and_changed_file(self):
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(40, 750, 'Employee 2000000091')
        pdf.save()
        batch = self.batch_model.create({})
        wizard = self.env['saddad.qiwa.import'].with_user(self.operator).create({'batch_id': batch.id, 'pdf_file': base64.b64encode(buffer.getvalue())})
        wizard.action_extract()
        wizard.write({'reviewed': True, 'reference': '123456789012345', 'issue_date': fields.Date.today(), 'due_date': fields.Date.today()+timedelta(days=5), 'document_digest': 'changed'})
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_mapping_drift_and_protected_links(self):
        rec = self._batch()
        with self.assertRaises(AccessError):
            rec.line_ids.write({'ptr_line_id': 123})
        self.mapping.product_id = self.env['product.product'].create({'name': 'Changed fee', 'type': 'service', 'standard_price': 2500})
        with self.assertRaises(ValidationError):
            rec.action_review()
        rec.line_ids.write({'mapping_id': self.mapping.id})
        rec.action_review()

    def test_legacy_confirmed_ptr_backfill(self):
        from ..models.ptr import PaymentTransferRequest
        ptr = self.env['saddad.ptr'].with_user(self.operator).create({'employee_id': self.employee.id})
        ptr.action_review()
        super(PaymentTransferRequest, ptr).write({'state': 'confirmed', 'qiwa_handoff_state': 'pending', 'confirmed_by': self.confirmer.id, 'confirmed_at': fields.Datetime.now()})
        ptr.with_user(self.confirmer).action_prepare_qiwa()
        self.assertEqual(ptr.qiwa_handoff_state, 'linked')
        self.assertEqual(ptr.qiwa_batch_id.line_ids.amount, ptr.amount)
        batch = ptr.qiwa_batch_id
        ptr.with_user(self.confirmer).action_prepare_qiwa()
        self.assertEqual(ptr.qiwa_batch_id, batch)

    def test_import_currency_mismatch_and_employee_mismatch(self):
        self.company.currency_id = self.env.ref('base.USD')
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(40, 750, 'Employee 2000000091')
        pdf.save()
        batch = self.batch_model.create({})
        wizard = self.env['saddad.qiwa.import'].with_user(self.operator).create({'batch_id': batch.id, 'pdf_file': base64.b64encode(buffer.getvalue())})
        wizard.action_extract()
        wizard.write({'reviewed': True, 'reference': '123456789012345', 'issue_date': fields.Date.today(), 'due_date': fields.Date.today()+timedelta(days=5), 'detected_currency': 'SAR'})
        with self.assertRaises(ValidationError):
            wizard.action_apply()
        wizard.detected_currency = False
        wizard.line_ids.employee_id = self.employee2
        with self.assertRaises(ValidationError):
            wizard.action_apply()
        self.assertFalse(batch.line_ids)

    def test_mixed_period_pdf_rows(self):
        parsed = parse_qiwa_text('2000000091 months 330/12/20262,425.00\n2000000092 months 630/03/20274,850.00')
        self.assertEqual(len(parsed['employees']), 2)
        self.assertEqual([r['period'] for r in parsed['employees']], ['3', '6'])
        self.assertFalse(parsed['period'])

    def test_native_form_line_entry(self):
        from odoo.tests import Form
        with Form(self.batch_model) as form:
            form.reference = '123456789012345'
            form.issue_date = fields.Date.today()
            form.due_date = fields.Date.today()+timedelta(days=5)
            with form.line_ids.new() as line:
                line.employee_id = self.employee
                line.mapping_id = self.mapping
        batch = form.record
        self.assertEqual(batch.total_amount, 2425)
        self.assertEqual(batch.line_ids.product_id, self.product)

    def test_paid_document_review_without_due_date(self):
        rec = self._batch(due_date=False, issue_date=fields.Date.today()-timedelta(days=20), document_payment_status='paid', document_payment_date=fields.Date.today()-timedelta(days=10))
        rec.action_review()
        rec.with_user(self.confirmer).action_confirm()
        self.assertFalse(rec.due_date)
        self.assertEqual(rec.state, 'confirmed')
        self.assertEqual(rec.downstream_state, 'linked')
        with self.assertRaises(UserError):
            rec.write({'document_payment_status': 'unpaid'})

    def test_paid_document_requires_valid_payment_date(self):
        rec = self._batch(due_date=False, document_payment_status='paid')
        with self.assertRaises(UserError):
            rec.action_review()
        rec.document_payment_date = fields.Date.today()+timedelta(days=1)
        with self.assertRaises(UserError):
            rec.action_review()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.document_payment_date = fields.Date.today()-timedelta(days=1)

    def test_print_footer_and_paid_export_dates(self):
        text = '1234567890123459000\n13/09/2026\nEmployee 2000000091 months 3 30/12/2026 2,425.0010/8/26, 2:53 PM Qiwa\nTotal 2,425.00\nPayment Status Paid\n12345678901234510/8/26, 2:53 PM Qiwa\nhttps://working-permits.qiwa.sa 1/2\nPayment Date 19/09/2026\nExport Date 08/10/202610/8/26, 2:53 PM Qiwa'
        result = parse_qiwa_text(text)
        self.assertEqual(result['reference'], '123456789012345')
        self.assertEqual(result['invoice_number'], '1234567890123459000')
        self.assertEqual(result['payment_status'], 'paid')
        self.assertEqual(str(result['issue_date']), '2026-09-13')
        self.assertEqual(str(result['payment_date']), '2026-09-19')
        self.assertEqual(str(result['export_date']), '2026-10-08')
        self.assertFalse(result['due_date'])
        self.assertEqual(result['document_total'], 2425)
        self.assertEqual(result['employees'][0]['amount'], 2425)

    def test_unknown_payment_status_does_not_invent_dates(self):
        result = parse_qiwa_text('1234567890123459000\n13/09/2026\nEmployee 2000000091 months 3 30/12/2026 2,425.00\n123456789012345\n19/09/2026\nExport Date 08/10/2026')
        self.assertEqual(result['payment_status'], 'unknown')
        self.assertFalse(result['due_date'])
        self.assertFalse(result['payment_date'])
        self.assertEqual(str(result['issue_date']), '2026-09-13')

    def test_visual_order_employee_row(self):
        result = parse_qiwa_text('2000000091 2,425.00 30/12/2026 3 months')
        self.assertEqual(result['employees'][0]['amount'], 2425)
        self.assertEqual(result['period'], '3')

    def test_pdf_total_mismatch_blocks_application(self):
        import hashlib
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(40,750,'Employee 2000000091')
        pdf.save()
        batch = self.batch_model.create({})
        wizard = self.env['saddad.qiwa.import'].with_user(self.operator).create({'batch_id':batch.id,'pdf_file':base64.b64encode(buffer.getvalue())})
        wizard.action_extract()
        wizard.write({'reference':'123456789012345','issue_date':fields.Date.today(),'due_date':fields.Date.today()+timedelta(days=5),'reviewed':True,'has_document_total':True,'document_total':9700})
        with self.assertRaises(ValidationError):
            wizard.action_apply()
        self.assertFalse(batch.line_ids)
        wizard.document_total = 2425
        wizard.action_apply()
        self.assertEqual(batch.total_amount,2425)
    def _iqama_ptr(self, mixed=False):
        mapping = self.env['saddad.service.mapping'].create({'company_id': self.company.id,
            'service_type': 'iqama', 'period': '3', 'product_id': self.product.id})
        lines = [Command.create({'mapping_id': mapping.id})]
        if mixed:
            lines.append(Command.create({'mapping_id': self.mapping.id}))
        ptr = self.env['saddad.ptr'].with_user(self.operator).create({'employee_id': self.employee.id, 'line_ids': lines})
        ptr.action_review()
        return ptr

    def test_iqama_ptr_direct_muqeem_snapshot_and_links(self):
        ptr = self._iqama_ptr()
        self.product.standard_price = 9999
        ptr.with_user(self.confirmer).action_confirm()
        expense = ptr.direct_muqeem_ids
        self.assertEqual(len(expense), 1)
        self.assertEqual(expense.state, 'draft')
        self.assertEqual(expense.ptr_id, ptr)
        self.assertFalse(expense.qiwa_batch_id)
        self.assertFalse(ptr.qiwa_batch_id)
        self.assertEqual(ptr.qiwa_route_state, 'not_applicable')
        self.assertEqual(expense.line_ids.ptr_line_id, ptr.line_ids)
        self.assertEqual(expense.line_ids.employee_id, ptr.employee_id)
        self.assertEqual(expense.line_ids.product_id, ptr.line_ids.product_id)
        self.assertEqual(expense.line_ids.amount, 2425)
        self.assertEqual(expense.line_ids.period, '3')
        self.assertEqual(expense.line_ids.defer_start, ptr.expiry_date)
        self.assertFalse(expense.line_ids.paid)
        self.assertFalse(expense.move_id)
        self.assertEqual(ptr.action_open_muqeem()['res_id'], expense.id)
        ptr.with_user(self.confirmer).action_prepare_muqeem()
        self.assertEqual(ptr.direct_muqeem_ids, expense)

    def test_iqama_backfill_uses_confirmed_snapshot(self):
        from ..models.ptr import PaymentTransferRequest
        ptr = self._iqama_ptr()
        super(PaymentTransferRequest, ptr).write({'state': 'confirmed'})
        self.assertTrue(ptr.with_user(self.confirmer).can_prepare_muqeem)
        self.assertEqual(ptr.qiwa_route_state, 'not_applicable')
        old_expiry = ptr.expiry_date
        self.employee.saddad_iqama_expiry = old_expiry + timedelta(days=90)
        ptr.with_user(self.confirmer).action_prepare_muqeem()
        self.assertEqual(ptr.direct_muqeem_ids.line_ids.defer_start, old_expiry)
        self.assertFalse(ptr.with_user(self.confirmer).can_prepare_muqeem)

    def test_iqama_backfill_authorization_and_state(self):
        ptr = self._iqama_ptr()
        with self.assertRaises(UserError):
            ptr.with_user(self.confirmer).action_prepare_muqeem()
        ptr.with_user(self.confirmer).action_confirm()
        with self.assertRaises(AccessError):
            ptr.with_user(self.operator).action_prepare_muqeem()
        with self.assertRaises(AccessError):
            ptr.with_user(self.plain).action_prepare_muqeem()

    def test_iqama_source_links_and_values_protected(self):
        ptr = self._iqama_ptr()
        ptr.with_user(self.confirmer).action_confirm()
        expense = ptr.direct_muqeem_ids.sudo()
        with self.assertRaises(AccessError): expense.write({'ptr_id': False})
        with self.assertRaises(AccessError): expense.line_ids.write({'ptr_line_id': False})
        with self.assertRaises(UserError): expense.line_ids.write({'amount': 1})
        with self.assertRaises(UserError): expense.line_ids.unlink()
        with self.assertRaises(UserError): expense.unlink()
        with self.assertRaises(AccessError): self.env['saddad.muqeem.expense'].create({'ptr_id': ptr.id})
        with self.assertRaises(AccessError): self.env['saddad.muqeem.line'].create({'expense_id': expense.id, 'ptr_line_id': ptr.line_ids.id, 'employee_id': self.employee.id, 'product_id': self.product.id})

    def test_mixed_ptr_splits_iqama_and_work_permit(self):
        ptr = self._iqama_ptr(mixed=True)
        ptr.with_user(self.confirmer).action_confirm()
        expense = ptr.direct_muqeem_ids
        self.assertEqual(len(expense.line_ids), 1)
        self.assertEqual(expense.line_ids.ptr_line_id.service_type, 'iqama')
        batch = ptr.qiwa_batch_id
        self.assertEqual(len(batch.line_ids), 1)
        self.assertEqual(batch.line_ids.ptr_line_id.service_type, 'work_permit')
        batch.write({'reference': 'DIRECT-MIXED-1', 'issue_date': fields.Date.today(), 'due_date': fields.Date.today()+timedelta(days=10)})
        batch.action_review()
        batch.with_user(self.confirmer).action_confirm()
        self.assertEqual(len(ptr.muqeem_expense_ids), 2)
        self.assertEqual(len(batch.muqeem_ids.line_ids), 1)
        ptr.with_user(self.confirmer).action_prepare_muqeem()
        self.assertEqual(ptr.direct_muqeem_ids, expense)

    def test_direct_handoff_rolls_back_confirmation(self):
        from unittest.mock import patch
        ptr = self._iqama_ptr(mixed=True)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            with patch.object(type(self.env['saddad.muqeem.expense']), '_validate_lines', side_effect=ValidationError('Deliberate failure')):
                ptr.with_user(self.confirmer).action_confirm()
        self.assertEqual(ptr.state, 'reviewed')
        self.assertFalse(ptr.direct_muqeem_ids)
        self.assertFalse(ptr.qiwa_batch_id)

    def test_work_permit_only_no_direct_expense(self):
        ptr = self._ptr()
        self.assertFalse(ptr.direct_muqeem_ids)
        self.assertEqual(ptr.qiwa_route_state, 'linked')
        with self.assertRaises(UserError): ptr.with_user(self.confirmer).action_prepare_muqeem()

    def test_muqeem_role_reads_source_without_ptr_confirmation(self):
        ptr = self._iqama_ptr()
        ptr.with_user(self.confirmer).action_confirm()
        hr = self._make_user('direct_muqeem_hr', 'Saddad.group_muqeem_hr')
        self.assertEqual(ptr.direct_muqeem_ids.with_user(hr).ptr_id.read(['name'])[0]['name'], ptr.name)
        with self.assertRaises(AccessError): ptr.with_user(hr).action_prepare_muqeem()
