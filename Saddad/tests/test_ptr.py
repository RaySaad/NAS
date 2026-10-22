from datetime import timedelta

from psycopg2 import IntegrityError
from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaddadPhaseOne(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other = cls.env['res.company'].create({'name': 'Saddad Other Company'})
        cls.company.write({'saddad_ptr_threshold': 30, 'saddad_ptr_automation': True})
        cls.product = cls.env['product.product'].create({'name': 'Test Work Permit', 'type': 'service',
                                                       'standard_price': 125, 'list_price': 900})
        cls.env['saddad.service.mapping'].search([('company_id', '=', cls.company.id)]).unlink()
        cls.mapping = cls.env['saddad.service.mapping'].create({
            'company_id': cls.company.id, 'service_type': 'work_permit', 'period': '3', 'product_id': cls.product.id, 'default_for_ptr': True})
        cls.employee = cls.env['hr.employee'].create({'name': 'Saddad Employee', 'identification_id': '2000000001', 'company_id': cls.company.id,
            'saddad_iqama_expiry': fields.Date.today() + timedelta(days=30), 'saddad_ptr_eligible': True})
        cls.ptr = cls.env['saddad.ptr']
        cls.user = cls._user('saddad_operator', 'Saddad.group_user')
        cls.reviewer = cls._user('saddad_reviewer', 'Saddad.group_reviewer')
        cls.confirmer = cls._user('saddad_confirmer', 'Saddad.group_confirmer')
        cls.plain = cls._user('saddad_plain', 'base.group_user')
        cls.manager = cls._user('saddad_manager', 'Saddad.group_manager')
        # Disable outbound mail in tests unless testing the queue explicitly.
        cls.env['saddad.approval.rule'].search([]).write({'notify_email': False, 'notify_activity': True})

    @classmethod
    def _user(cls, login, group):
        return cls.env['res.users'].with_context(no_reset_password=True).create({'name': login, 'login': login,
            'email': login + '@example.invalid', 'company_id': cls.company.id,
            'company_ids': [Command.set(cls.company.ids)], 'group_ids': [Command.set([cls.env.ref(group).id])]})

    def _request(self):
        return self.ptr.with_user(self.user).create({'employee_id': self.employee.id})

    def test_manual_form_employee_snapshot_before_save(self):
        from odoo.tests import Form
        department = self.env['hr.department'].create({'name': 'PTR Preview Department', 'company_id': self.company.id})
        self.employee.department_id = department
        with Form(self.ptr.with_user(self.user)) as form:
            form.employee_id = self.employee
            self.assertEqual(form.iqama_number, self.employee.identification_id)
            self.assertEqual(form.expiry_date, self.employee.saddad_iqama_expiry)
            self.assertEqual(form.remaining_days, 30)
            self.assertEqual(form.department_id, department)
        self.assertEqual(form.record.iqama_number, self.employee.identification_id)
        self.assertEqual(form.record.expiry_date, self.employee.saddad_iqama_expiry)

    def test_manual_form_switch_and_clear_employee(self):
        from odoo.tests import Form
        second = self.env['hr.employee'].create({'name': 'PTR Other Employee', 'company_id': self.company.id,
            'identification_id': '2000000087', 'saddad_iqama_expiry': fields.Date.today() - timedelta(days=5)})
        form = Form(self.ptr.with_user(self.user))
        form.employee_id = self.employee
        form.employee_id = second
        self.assertEqual(form.iqama_number, second.identification_id)
        self.assertEqual(form.expiry_date, second.saddad_iqama_expiry)
        self.assertEqual(form.remaining_days, -5)
        form.employee_id = self.env['hr.employee']
        self.assertFalse(form.iqama_number)
        self.assertFalse(form.expiry_date)
        self.assertEqual(form.remaining_days, 0)
        second.write({'identification_id': False, 'saddad_iqama_expiry': False})
        form.employee_id = second
        self.assertFalse(form.iqama_number)
        self.assertFalse(form.expiry_date)

    def test_workflow_and_cost_snapshot(self):
        rec = self._request()
        self.assertEqual(rec.amount, 125)
        self.assertEqual(rec.state, 'draft')
        self.product.standard_price = 150
        rec.with_user(self.reviewer).action_review()
        self.assertEqual(rec.amount, 150)
        self.product.standard_price = 175
        rec.with_user(self.confirmer).action_confirm()
        self.assertEqual(rec.amount, 150)
        self.assertEqual(rec.confirmed_by, self.confirmer)
        self.assertEqual(rec.qiwa_handoff_state, 'linked')

    def test_server_side_permissions(self):
        rec = self._request()
        with self.assertRaises(AccessError):
            rec.with_user(self.plain).action_review()
        with self.assertRaises(AccessError):
            rec.write({'state': 'confirmed'})
        with self.assertRaises(AccessError):
            self.ptr.create({'employee_id': self.employee.id, 'amount': 1})
        with self.assertRaises(UserError):
            rec.with_user(self.confirmer).action_confirm()
        rec.with_user(self.reviewer).action_review()
        with self.assertRaises(UserError):
            rec.write({'period': '6'})
        with self.assertRaises(UserError):
            rec.with_user(self.manager).unlink()

    def test_duplicates_and_copy(self):
        rec = self._request()
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self._request()
        with self.assertRaises(UserError):
            rec.copy()

    def test_stale_expiry_rejected(self):
        rec = self._request()
        self.employee.saddad_iqama_expiry += timedelta(days=1)
        with self.assertRaises(UserError):
            rec.with_user(self.reviewer).action_review()

    def test_company_boundary(self):
        outsider = self.env['hr.employee'].create({'name': 'Other Employee', 'identification_id': '2000000003', 'company_id': self.other.id,
                                                  'saddad_iqama_expiry': self.employee.saddad_iqama_expiry})
        with self.assertRaises(AccessError):
            self.ptr.with_user(self.user).create({'employee_id': outsider.id, 'company_id': self.other.id})
        with self.assertRaises(ValidationError):
            self.ptr.create({'employee_id': outsider.id, 'company_id': self.company.id})

    def test_company_dependent_product_cost(self):
        self.product.with_company(self.other).standard_price = 800
        self.assertEqual(self._request().amount, 125)

    def test_configurable_approval(self):
        self.env['saddad.approval.rule'].create({'name': 'Company override', 'company_id': self.company.id,
            'transition': 'review', 'group_id': self.env.ref('Saddad.group_confirmer').id, 'notify_email': False})
        rec = self._request()
        with self.assertRaises(AccessError):
            rec.with_user(self.reviewer).action_review()
        rec.with_user(self.confirmer).action_review()
        self.assertEqual(rec.state, 'reviewed')

    def test_hijri_and_remaining_days(self):
        self.employee.saddad_iqama_expiry = '2025-03-01'
        self.assertEqual(self.employee.saddad_iqama_hijri, '1446-09-01')
        self.assertEqual(self.employee.saddad_iqama_remaining_days,
                         (fields.Date.to_date('2025-03-01') - fields.Date.context_today(self.employee)).days)
        self.employee.saddad_iqama_expiry = False
        self.assertFalse(self.employee.saddad_iqama_hijri)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.employee.saddad_iqama_expiry = '2200-01-01'

    def test_active_default_mapping_required(self):
        self.mapping.active = False
        with self.assertRaises(UserError):
            self._request()
        self.mapping.active = True
        rec = self._request()
        self.assertEqual(rec.product_id, self.product)
        with self.assertRaises(UserError):
            rec.write({'period': '6'})

    def test_cron_threshold_idempotency_and_cleanup(self):
        self.ptr._cron_create_ptrs()
        rec = self.ptr.search([('employee_id', '=', self.employee.id)])
        self.assertEqual(len(rec), 1)
        self.assertTrue(rec.auto_generated)
        self.ptr._cron_create_ptrs()
        self.assertEqual(self.ptr.search_count([('employee_id', '=', self.employee.id)]), 1)
        self.employee.saddad_iqama_expiry += timedelta(days=1)
        self.ptr._cron_cleanup_drafts()
        self.assertFalse(rec.exists())
        self.ptr._cron_create_ptrs()
        self.assertEqual(self.ptr.search_count([('employee_id', '=', self.employee.id)]), 0)

    def test_cleanup_removes_manual_drafts_but_preserves_reviewed(self):
        manual = self._request()
        self.employee.active = False
        self.ptr._cron_cleanup_drafts()
        self.assertFalse(manual.exists())
        self.employee.active = True
        self.ptr._cron_create_ptrs()
        reviewed = self.ptr.search([('employee_id', '=', self.employee.id)])
        reviewed.with_user(self.reviewer).action_review()
        self.employee.active = False
        self.ptr._cron_cleanup_drafts()
        self.assertTrue(reviewed.exists())

    def test_notifications_and_completion(self):
        self.env.ref('Saddad.approval_review_default').notify_email = True
        rec = self._request()
        self.assertIn(self.reviewer, rec.sudo().activity_ids.user_id)
        mails = self.env['mail.mail'].search([('model', '=', 'saddad.ptr'), ('res_id', '=', rec.id)])
        self.assertTrue(mails)
        rec.with_user(self.reviewer).action_review()
        self.assertIn(self.confirmer, rec.sudo().activity_ids.user_id)
        self.assertNotIn(self.reviewer, rec.sudo().activity_ids.user_id)
        rec.with_user(self.confirmer).action_confirm()
        self.assertFalse(rec.sudo().activity_ids)

    def test_negative_threshold_and_shared_rule_security(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.company.saddad_ptr_threshold = -1
        with self.assertRaises(AccessError):
            self.env.ref('Saddad.approval_review_default').with_user(self.manager).write({'name': 'Changed'})

    def test_all_periods_and_service_validation(self):
        for period in ['6', '9', '12']:
            product = self.env['product.product'].create({'name': 'Period ' + period,
                'type': 'service', 'standard_price': int(period) * 50})
            self.env['saddad.service.mapping'].create({'company_id': self.company.id,
                'service_type': 'work_permit', 'period': period, 'product_id': product.id})
        rec = self._request()
        for period in ['6', '9', '12']:
            rec.write({'period': period})
            self.assertEqual(rec.amount, int(period) * 50)
        goods = self.env['product.product'].create({'name': 'Not a service', 'type': 'consu'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.mapping.product_id = goods

    def test_cron_overdue_opt_out_and_no_starvation(self):
        self.employee.saddad_iqama_expiry = fields.Date.today() - timedelta(days=1)
        self.ptr._cron_create_ptrs(batch_size=1)
        second = self.env['hr.employee'].create({'name': 'Second Eligible', 'identification_id': '2000000004', 'company_id': self.company.id,
            'saddad_iqama_expiry': self.employee.saddad_iqama_expiry, 'saddad_ptr_eligible': True})
        self.ptr._cron_create_ptrs(batch_size=1)
        self.assertEqual(self.ptr.search_count([('employee_id', 'in', (self.employee | second).ids)]), 2)
        opted_out = self.env['hr.employee'].create({'name': 'Opted Out', 'identification_id': '2000000005', 'company_id': self.company.id,
            'saddad_iqama_expiry': self.employee.saddad_iqama_expiry, 'saddad_ptr_eligible': False})
        self.ptr._cron_create_ptrs()
        self.assertFalse(self.ptr.search([('employee_id', '=', opted_out.id)]))

    def test_record_isolation(self):
        self.env['saddad.service.mapping'].create({'company_id': self.other.id, 'product_id': self.product.id, 'period': '3', 'service_type': 'work_permit', 'default_for_ptr': True})
        employee = self.env['hr.employee'].create({'name': 'Other Company Employee', 'identification_id': '2000000002', 'company_id': self.other.id,
            'saddad_iqama_expiry': fields.Date.today()})
        foreign = self.ptr.with_company(self.other).create({'employee_id': employee.id})
        with self.assertRaises(AccessError):
            foreign.with_user(self.user).read(['name'])
        self.assertNotIn(foreign.id, self.ptr.with_user(self.user).search([]).ids)

    def test_bulk_transition_and_invalid_reentry(self):
        employee = self.env['hr.employee'].create({'name': 'Second PTR Employee', 'identification_id': '2000000006', 'company_id': self.company.id,
            'saddad_iqama_expiry': self.employee.saddad_iqama_expiry})
        recs = self._request() | self.ptr.with_user(self.user).create({'employee_id': employee.id})
        recs.with_user(self.reviewer).action_review()
        self.assertEqual(set(recs.mapped('state')), {'reviewed'})
        recs.with_user(self.confirmer).action_confirm()
        self.assertEqual(set(recs.mapped('state')), {'confirmed'})
        with self.assertRaises(UserError):
            recs.with_user(self.confirmer).action_confirm()

    def test_arabic_catalog_and_views(self):
        lang = self.env['res.lang'].search([('code', '=', 'ar_001'), ('active', '=', True)])
        if not lang:
            self.skipTest('Activate Arabic to run translated-view checks.')
        model = self.ptr.with_user(self.user).with_context(lang='ar_001')
        states = dict(model.fields_get(['state'])['state']['selection'])
        self.assertEqual(states['draft'], 'مسودة')
        view = model.get_view(view_id=self.env.ref('Saddad.view_ptr_form').id, view_type='form')
        self.assertIn('statusbar', view['arch'])
        self.assertIn('مراجعة', view['arch'])
        self.assertEqual(lang.direction, 'rtl')

    def test_service_lines_and_locked_line_rpc(self):
        rec = self._request()
        second = self.env['product.product'].create({'name': 'Other service', 'type': 'service', 'standard_price': 50})
        rec.write({'line_ids': [Command.create({'product_id': second.id})]})
        self.assertEqual(rec.amount, 175)
        rec.with_user(self.user).action_review()
        for line in rec.line_ids:
            with self.assertRaises(UserError):
                line.write({'product_id': second.id})
            with self.assertRaises(UserError):
                line.unlink()
        with self.assertRaises(AccessError):
            rec.line_ids.write({'amount': 1})
        with self.assertRaises(UserError):
            rec.write({'line_ids': [Command.create({'product_id': second.id})]})
        rec.with_user(self.user).action_reset_draft()
        rec.line_ids[-1].unlink()
        self.assertEqual(rec.amount, 125)

    def test_empty_lines_rejected_and_reset_stale_review(self):
        rec = self._request()
        rec.line_ids.unlink()
        with self.assertRaises(UserError):
            rec.action_review()
        rec.write({'line_ids': [Command.create({'mapping_id': self.mapping.id})]})
        rec.action_review()
        self.employee.saddad_iqama_expiry += timedelta(days=1)
        rec.action_reset_draft()
        self.assertEqual(rec.expiry_date, self.employee.saddad_iqama_expiry)
        self.assertEqual(rec.reset_by, self.user)

    def test_cron_requires_identification(self):
        self.employee.identification_id = False
        self.ptr._cron_create_ptrs()
        self.assertFalse(self.ptr.search([('employee_id', '=', self.employee.id)]))
        with self.assertRaises(ValidationError):
            self._request()

    def test_only_one_default_mapping(self):
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env['saddad.service.mapping'].create({'company_id': self.company.id, 'service_type': 'iqama',
                'period': '3', 'product_id': self.product.id, 'default_for_ptr': True})

    def test_remaining_days_search(self):
        rec = self._request()
        self.assertIn(rec.id, self.ptr.search([('remaining_days', '<=', 30)]).ids)
        self.assertIn(self.employee.id, self.env['hr.employee'].search([('saddad_iqama_remaining_days', '=', 30)]).ids)

    def test_admin_settings_without_system_access(self):
        wizard = self.env['saddad.settings'].with_user(self.manager).create({
            'company_id': self.company.id, 'threshold': 45, 'automation': False})
        wizard.action_save()
        self.assertEqual(self.company.saddad_ptr_threshold, 45)
        with self.assertRaises(AccessError):
            wizard.with_user(self.user).action_save()


@tagged('post_install', '-at_install')
class TestSaddadCatalog(TransactionCase):
    def test_seed_catalog_and_mappings(self):
        import json
        from odoo.tools import file_open
        with file_open('Saddad/data/product_catalog.json', 'r') as source:
            catalog = json.load(source)
        self.assertEqual(len(catalog), 196)
        for row in catalog:
            product = self.env.ref(row['xmlid'])
            self.assertEqual(product.with_context(lang='en_US').name, row['name'])
            self.assertEqual(product.standard_price, row['cost'])
            self.assertEqual(product.type, 'service')
            self.assertEqual(product.categ_id.with_context(lang='en_US').name, row['category'])
            self.assertEqual(product.uom_id, self.env.ref('uom.product_uom_unit'))
            if self.env['res.lang'].search_count([('code', '=', 'ar_001'), ('active', '=', True)]):
                self.assertEqual(product.with_context(lang='ar_001').name, row['arabic'])
        mappings = self.env['saddad.service.mapping'].search([('company_id', '=', self.env.ref('base.main_company').id)])
        self.assertEqual(len(mappings), 8)
        default = mappings.filtered('default_for_ptr')
        self.assertEqual((default.service_type, default.period), ('work_permit', '3'))
        from odoo.addons.Saddad.hooks import seed_mappings
        seed_mappings(self.env)
        self.assertEqual(self.env['saddad.service.mapping'].search_count([('company_id', '=', self.env.company.id)]), 8)

