import base64
import io
from datetime import date, timedelta
import openpyxl
from hijridate import Gregorian
from odoo import Command, fields
from odoo.tests import TransactionCase, tagged, Form
from odoo.exceptions import AccessError, UserError
from ..models.resident_import import HEADERS
from ..models.muqeem import MuqeemLine


@tagged('post_install', '-at_install')
class TestResident(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.hr = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Resident HR', 'login': 'resident_hr_test', 'email': 'resident@example.invalid',
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'group_ids': [Command.set([cls.env.ref('Saddad.group_resident_hr').id, cls.env.ref('Saddad.group_muqeem_user').id])]})
        cls.employee = cls.env['hr.employee'].create({'name': 'Resident Test', 'company_id': cls.company.id,
            'identification_id': '2000000999', 'saddad_iqama_expiry': date(2026, 12, 1)})
        cls.establishment = cls.env['saddad.establishment'].create({'name': 'Test Establishment', 'number': '7000000999', 'company_id': cls.company.id})
        cls.product = cls.env['product.product'].create({'name': 'Resident Iqama Renewal', 'type': 'service',
            'categ_id': cls.env.ref('Saddad.category_muqeem').id, 'standard_price': 100, 'supplier_taxes_id': [Command.clear()]})
        mapping = cls.env['saddad.service.mapping'].search([('company_id', '=', cls.company.id), ('service_type', '=', 'iqama'), ('period', '=', '3')])
        if mapping:
            mapping.product_id = cls.product
        else:
            cls.env['saddad.service.mapping'].create({'company_id': cls.company.id, 'service_type': 'iqama', 'period': '3', 'product_id': cls.product.id})

    def _batch(self, expiry=date(2026, 12, 1), duplicate=False, employer='7000000999'):
        book = openpyxl.Workbook()
        sheet = book.active
        sheet.append(HEADERS)
        row = ['2000000999', 'Resident Test', 'Male', 'Test nationality', 'Driver', 'TEST001',
               '2030-01-01', '2020-01-01', str(expiry), '1990-01-01', 'No',
               Gregorian(expiry.year, expiry.month, expiry.day).to_hijri().isoformat(), employer]
        sheet.append(row)
        if duplicate:
            sheet.append(row)
        stream = io.BytesIO()
        book.save(stream)
        return self.env['saddad.resident.import'].with_user(self.hr).create({'company_id': self.company.id,
            'filename': 'residents.xlsx', 'file': base64.b64encode(stream.getvalue()), 'snapshot_date': fields.Date.today()})

    def _profile(self):
        batch = self._batch()
        batch.action_preview()
        batch.action_apply()
        return self.env['saddad.resident'].with_user(self.hr).search([('employee_id', '=', self.employee.id)])

    def _renewal(self):
        profile = self._profile()
        expense = self.env['saddad.muqeem.expense'].with_user(self.hr).create({'line_ids': [Command.create({
            'employee_id': self.employee.id, 'product_id': self.product.id, 'period': '3'})]})
        # Payment workflow is covered by TestMuqeem. Set only its outcome for these tests.
        super(MuqeemLine, expense.line_ids).write({'paid': True})
        return self.env['saddad.renewal'].with_user(self.hr).create({'resident_id': profile.id,
            'expense_line_id': expense.line_ids.id, 'period': '3', 'evidence': 'Verified portal result'})

    def test_import_preview_apply_and_no_employee_overwrite(self):
        batch = self._batch(date(2027, 3, 1))
        batch.action_preview()
        self.assertEqual(batch.line_ids.status, 'ready')
        batch.action_apply()
        self.assertEqual(self.employee.saddad_iqama_expiry, date(2026, 12, 1))
        profile = self.env['saddad.resident'].search([('employee_id', '=', self.employee.id)])
        self.assertEqual(profile.reported_expiry, date(2027, 3, 1))
        with self.assertRaises(UserError):
            batch.action_apply()
        with self.assertRaises(AccessError):
            batch.line_ids.write({'status': 'ready'})
        for kind in ('list', 'form', 'search'):
            profile.with_user(self.hr).get_view(self.env.ref('Saddad.view_resident_' + kind).id, kind)

    def test_duplicate_and_wrong_employer_blocked(self):
        for batch in (self._batch(duplicate=True), self._batch(employer='999')):
            batch.action_preview()
            self.assertTrue(all(l.status == 'error' for l in batch.line_ids))
            with self.assertRaises(UserError):
                batch.action_apply()

    def test_stale_preview_blocked(self):
        a, b = self._batch(), self._batch(date(2027, 3, 1))
        a.action_preview()
        b.action_preview()
        a.action_apply()
        with self.assertRaises(UserError):
            b.action_apply()

    def test_confirm_renewal_once(self):
        renewal = self._renewal()
        renewal.action_confirm_renewal()
        self.assertEqual(self.employee.saddad_iqama_expiry, date(2027, 3, 1))
        self.assertEqual(renewal.state, 'done')
        with self.assertRaises(UserError):
            renewal.action_confirm_renewal()
        with self.assertRaises(AccessError):
            renewal.write({'state': 'pending'})

    def test_manual_update_already_applied(self):
        renewal = self._renewal()
        self.employee.saddad_iqama_expiry = renewal.new_expiry
        renewal.action_confirm_renewal()
        self.assertEqual(self.employee.saddad_iqama_expiry, date(2027, 3, 1))

    def test_conflict_and_unpaid_blocked(self):
        renewal = self._renewal()
        self.employee.saddad_iqama_expiry = date(2027, 1, 1)
        with self.assertRaises(UserError):
            renewal.action_confirm_renewal()
        self.employee.saddad_iqama_expiry = renewal.original_expiry
        super(MuqeemLine, renewal.expense_line_id).write({'paid': False})
        with self.assertRaises(UserError):
            renewal.action_confirm_renewal()

    def test_alerts_deduplicate_and_completion_closes(self):
        from ..models.resident import Renewal
        renewal = self._renewal()
        super(Renewal, renewal).write({'permit_confirmed_on': fields.Date.today() - timedelta(days=8), 'permit_renewal_date': fields.Date.today() - timedelta(days=8)})
        model = self.env['saddad.renewal']
        model._cron_alerts()
        self.assertTrue(renewal.pending_alerted)
        self.assertEqual(len(renewal.alert_activity_ids), 1)
        model._cron_alerts()
        self.assertEqual(len(renewal.alert_activity_ids), 1)
        renewal.action_confirm_renewal()
        self.assertFalse(renewal.alert_activity_ids)

    def test_expiry_review_stale_and_conflict(self):
        profile = self._profile()
        action = profile.action_review_expiry()
        wizard = self.env[action['res_model']].with_user(self.hr).browse(action['res_id'])
        wizard.verified = True
        self.employee.saddad_iqama_expiry = date(2027, 1, 1)
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_company_boundary(self):
        profile = self._profile()
        other = self.env['res.company'].create({'name': 'Resident Other'})
        with self.assertRaises(AccessError):
            self.env['saddad.resident'].with_user(self.hr).with_context(allowed_company_ids=[other.id]).search([])

    def test_form_prepares_verified_date(self):
        profile = self._profile()
        with Form(self.env['saddad.renewal'].with_user(self.hr)) as form:
            form.resident_id = profile
            self.assertEqual(form.new_expiry, date(2027, 3, 1))
        self.assertEqual(form.record.original_expiry, date(2026, 12, 1))

    def test_work_permit_confirmation_and_expiry_alert(self):
        from ..models.qiwa import QiwaBatch
        renewal = self._renewal()
        mapping = self.env['saddad.service.mapping'].search([('company_id', '=', self.company.id), ('service_type', '=', 'work_permit'), ('period', '=', '3')], limit=1)
        if not mapping:
            mapping = self.env['saddad.service.mapping'].create({'company_id': self.company.id, 'service_type': 'work_permit', 'period': '3', 'product_id': self.product.id})
        batch = self.env['saddad.qiwa.batch'].create({'reference': '123456789012', 'line_ids': [Command.create({
            'employee_id': self.employee.id, 'mapping_id': mapping.id, 'permit_valid_until': fields.Date.today() + timedelta(days=25)})]})
        renewal.write({'qiwa_line_id': batch.line_ids.id, 'permit_evidence': 'Confirmed on Qiwa'})
        with self.assertRaises(UserError):
            renewal.action_confirm_permit()
        super(QiwaBatch, batch).write({'state': 'confirmed'})
        renewal.action_confirm_permit()
        self.assertEqual(renewal.resident_id.latest_permit_valid_until, batch.line_ids.permit_valid_until)
        self.env['saddad.renewal']._cron_alerts()
        self.assertTrue(renewal.expiry_alerted)
        self.assertFalse(renewal.pending_alerted)
        self.assertEqual(len(renewal.alert_activity_ids), 1)
        with self.assertRaises(UserError):
            renewal.action_confirm_permit()

    def test_source_snapshot_survives_manual_change(self):
        renewal = self._renewal()
        self.assertEqual(renewal.expense_line_id.renewal_original_expiry, date(2026, 12, 1))
        self.employee.saddad_iqama_expiry = date(2027, 4, 1)
        with self.assertRaises(UserError):
            renewal.action_confirm_renewal()

    def test_old_report_cannot_shorten_employee_expiry(self):
        profile = self._profile()
        self.employee.saddad_iqama_expiry = date(2027, 3, 1)
        with self.assertRaises(UserError):
            profile.action_review_expiry()
        self.assertEqual(profile.expiry_comparison, 'older')
        self.assertEqual(self.employee.saddad_iqama_expiry, date(2027, 3, 1))

    def test_employee_profile_fields_and_grouped_menus(self):
        profile = self._profile()
        employee = self.employee.with_user(self.hr)
        self.assertEqual(employee.saddad_resident_id, profile)
        self.assertEqual(employee.saddad_muqeem_employer_number, '7000000999')
        self.assertEqual(employee.saddad_muqeem_reported_expiry, date(2026, 12, 1))
        self.assertEqual(employee.action_open_resident_profile()['res_id'], profile.id)
        from lxml import etree
        for lang in ('en_US', 'ar_001'):
            arch = employee.with_context(lang=lang).get_view(self.env.ref('hr.view_employee_form').id, 'form')['arch']
            page = etree.fromstring(arch).xpath('//page[@name="saddad_muqeem"]')[0]
            self.assertFalse(page.xpath('.//list'))
            self.assertTrue(page.xpath('.//field[@name="saddad_muqeem_employer_number"]'))
        for child in ('menu_muqeem', 'menu_muqeem_lines', 'menu_residents', 'menu_resident_import'):
            self.assertEqual(self.env.ref('Saddad.' + child).parent_id, self.env.ref('Saddad.menu_muqeem_group'))
        for child in ('menu_ptr', 'menu_renewal'):
            self.assertEqual(self.env.ref('Saddad.' + child).parent_id, self.env.ref('Saddad.menu_renewals'))

    def test_unauthorized_renewal_access(self):
        renewal = self._renewal()
        plain = self.env['res.users'].with_context(no_reset_password=True).create({'name': 'Plain resident', 'login': 'plain_resident',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            renewal.with_user(plain).action_confirm_renewal()

    def test_expense_shortcut_reuses_followup(self):
        renewal = self._renewal()
        action = renewal.expense_line_id.action_renewal_followup()
        self.assertEqual(action['res_id'], renewal.id)

    def test_legacy_missing_snapshot_blocked(self):
        from ..models.resident import MuqeemLine as ResidentLine
        profile = self._profile()
        expense = self.env['saddad.muqeem.expense'].with_user(self.hr).create({'line_ids': [Command.create({
            'employee_id': self.employee.id, 'product_id': self.product.id, 'period': '3'})]})
        self.env.cr.execute('UPDATE saddad_muqeem_line SET renewal_original_expiry = NULL WHERE id = %s', [expense.line_ids.id])
        expense.line_ids.invalidate_recordset()
        with self.assertRaises(UserError):
            expense.line_ids.action_renewal_followup()
