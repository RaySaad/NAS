from datetime import date, timedelta
from odoo import Command, fields
from odoo.tests import TransactionCase, tagged, Form
from odoo.exceptions import AccessError, UserError, ValidationError
from psycopg2 import IntegrityError

@tagged("post_install", "-at_install")
class TestMorro(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.currency_id = cls.env.ref('base.SAR')
        cls.company.account_fiscal_country_id = cls.env.ref('base.sa')
        cls.other = cls.env['res.company'].create({'name': 'Morro Other Company'})
        cls.expense_account = cls.env['account.account'].create({'name': 'Morro Test Expense', 'code': 'MUQ600', 'account_type': 'expense', 'company_ids': [Command.set(cls.company.ids)]})
        cls.bank_account = cls.env['account.account'].create({'name': 'Morro Test Bank', 'code': 'MUQ100', 'account_type': 'asset_cash', 'company_ids': [Command.set(cls.company.ids)]})
        cls.loan_account = cls.env['account.account'].create({'name': 'Morro Employee Loan', 'code': 'MUQ110', 'account_type': 'asset_current', 'company_ids': [Command.set(cls.company.ids)]})
        cls.deferred_account = cls.env['account.account'].create({'name': 'Morro Deferred', 'code': 'MUQ120', 'account_type': 'asset_current', 'company_ids': [Command.set(cls.company.ids)]})
        cls.bank = cls.env['account.journal'].create({'name': 'Morro Bank', 'code': 'MQBK', 'type': 'bank', 'company_id': cls.company.id, 'default_account_id': cls.bank_account.id})
        cls.general = cls.env['account.journal'].create({'name': 'Morro Deferral', 'code': 'MQDF', 'type': 'general', 'company_id': cls.company.id})
        cls.company.write({'saddad_bank_journal_id': cls.bank.id, 'saddad_employee_loan_account_id': cls.loan_account.id,
                           'deferred_expense_account_id': cls.deferred_account.id, 'deferred_expense_journal_id': cls.general.id,
                           'deferred_expense_amount_computation_method': 'day'})
        cls.product = cls.env['product.product'].create({'name': 'Morro Service', 'type': 'service', 'categ_id': cls.env.ref('Saddad.category_morro').id, 'standard_price': 300, 'property_account_expense_id': cls.expense_account.id, 'supplier_taxes_id': [Command.clear()]})
        cls.employee = cls.env['hr.employee'].create({'name': 'Morro Employee', 'company_id': cls.company.id, 'identification_id': '2000000221', 'saddad_iqama_expiry': fields.Date.today()})
        cls.employee2 = cls.env['hr.employee'].create({'name': 'Morro Second', 'company_id': cls.company.id, 'identification_id': '2000000222', 'saddad_iqama_expiry': fields.Date.today()})
        cls.users = {}
        for key, group in [('user','morro_user'), ('fleet','morro_fleet'), ('finance','morro_finance'), ('gm','morro_gm'), ('payment','payment'), ('post','morro_post'), ('plain',False)]:
            cls.users[key] = cls.env['res.users'].with_context(no_reset_password=True).create({'name': 'Morro '+key, 'login': 'morro_'+key,
                'email': key+'@example.invalid', 'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
                'group_ids': [Command.set([cls.env.ref('Saddad.group_'+group if group else 'base.group_user').id])]})
        cls.env['saddad.approval.rule'].search([]).write({'notify_email': False, 'notify_activity': False})

    def _expense(self, count=1, **line_values):
        values = {'employee_id': self.employee.id, 'product_id': self.product.id, 'paid_for': 'company', 'violation_number': str(self.env['ir.sequence'].next_by_code('saddad.morro')), 'violation_date': fields.Date.today()}
        values.update(line_values)
        lines = [Command.create(values)]
        if count == 2:
            lines.append(Command.create(dict(values, employee_id=self.employee2.id, violation_number=values['violation_number']+'-2')))
        return self.env['saddad.morro'].with_user(self.users['user']).create({'line_ids': lines})

    def _payment(self, rec):
        for user in ['user', 'fleet', 'finance', 'gm']:
            rec.with_user(self.users[user]).action_approve()
        self.assertEqual(rec.state, 'payment')

    def _post(self, rec):
        self._payment(rec)
        rec.line_ids.with_user(self.users['payment']).action_mark_paid()
        rec.with_user(self.users['post']).action_post()
        return rec.sudo().move_id

    def test_full_workflow_consolidated_entry(self):
        rec = self._expense(2)
        move = self._post(rec)
        self.assertEqual(rec.state, 'posted')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.move_type, 'entry')
        self.assertEqual(sum(move.line_ids.mapped('debit')), 600)
        self.assertEqual(sum(move.line_ids.mapped('balance')), 0)
        self.assertEqual(move.line_ids.filtered(lambda l: l.account_id == self.bank_account).credit, 600)
        self.assertEqual(len(rec.line_ids.mapped('move_line_id')), 2)
        with self.assertRaises(UserError):
            rec.with_user(self.users['post']).action_post()
        with self.assertRaises(UserError):
            rec.line_ids.with_user(self.users['payment']).action_unmark_paid()

    def test_payment_partial_and_reversal(self):
        rec = self._expense(2)
        self._payment(rec)
        rec.line_ids[:1].with_user(self.users['payment']).action_mark_paid()
        self.assertEqual(rec.state, 'payment')
        self.assertEqual(rec.paid_amount, 300)
        self.assertFalse(rec.sudo().move_id)
        with self.assertRaises(UserError):
            rec.with_user(self.users['post']).action_post()
        rec.line_ids[1:].with_user(self.users['payment']).action_mark_paid()
        self.assertEqual(rec.state, 'done')
        rec.line_ids[:1].with_user(self.users['payment']).action_unmark_paid()
        self.assertEqual(rec.state, 'payment')
        self.assertFalse(rec.line_ids[:1].paid)

    def test_role_boundaries_and_rpc_guards(self):
        rec = self._expense()
        with self.assertRaises(AccessError):
            rec.with_user(self.users['plain']).action_approve()
        with self.assertRaises(AccessError):
            rec.write({'state': 'posted'})
        with self.assertRaises(AccessError):
            rec.line_ids.write({'paid': True})
        with self.assertRaises(AccessError):
            rec.write({'move_id': False})
        rec.action_approve()
        rec.with_user(self.users['fleet']).action_approve()
        with self.assertRaises(AccessError):
            rec.action_approve()
        with self.assertRaises(UserError):
            rec.line_ids.write({'amount': 999})

    def test_rejection_reason_and_reset(self):
        rec = self._expense()
        rec.action_approve()
        wizard = self.env['saddad.morro.reject'].with_user(self.users['fleet']).create({'expense_id': rec.id, 'reason': 'Missing supporting document'})
        wizard.action_apply()
        self.assertEqual(rec.state, 'rejected')
        self.assertEqual(rec.rejection_reason, 'Missing supporting document')
        rec.action_reset()
        self.assertEqual(rec.state, 'draft')
        self.assertTrue(rec.action_at)

    def test_accounts_required_atomic_post(self):
        rec = self._expense()
        self._payment(rec)
        rec.line_ids.with_user(self.users['payment']).action_mark_paid()
        self.product.property_account_expense_id = False
        self.product.categ_id.property_account_expense_categ_id = False
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.with_user(self.users['post']).action_post()
        self.assertEqual(rec.state, 'done')
        self.assertFalse(rec.sudo().move_id)

    def test_employee_loan_account(self):
        move = self._post(self._expense(paid_for='employee'))
        self.assertEqual(move.line_ids.filtered(lambda l: l.account_id == self.loan_account).debit, 300)

    def test_vat_direct_journal(self):
        group = self.env['account.tax.group'].create({'name':'Morro VAT Group','company_id':self.company.id})
        tax = self.env['account.tax'].create({'tax_group_id':group.id,'name': 'Morro VAT', 'amount': 15, 'type_tax_use': 'purchase', 'company_id': self.company.id})
        tax.invoice_repartition_line_ids.filtered(lambda l: l.repartition_type == 'tax').account_id = self.loan_account
        rec = self._expense(tax_ids=[Command.set(tax.ids)])
        self.assertEqual(rec.total_amount, 345)
        move = self._post(rec)
        self.assertEqual(move.line_ids.filtered('tax_repartition_line_id').debit, 45)
        self.assertEqual(sum(move.line_ids.mapped('balance')), 0)

    def test_posted_accounting_locked(self):
        rec = self._expense()
        move = self._post(rec)
        with self.assertRaises(UserError): move.button_draft()
        with self.assertRaises(UserError): move.unlink()
        with self.assertRaises(UserError): move.line_ids[:1].write({'account_id': self.loan_account.id})
        with self.assertRaises(UserError): move._reverse_moves()
        with self.assertRaises(UserError): move.copy()
        with self.assertRaises(UserError): move.write({'deferred_move_ids':[Command.clear()]})

    def test_company_isolation(self):
        rec = self._expense()
        other_employee = self.env['hr.employee'].create({'name': 'Other Employee', 'company_id': self.other.id})
        with self.assertRaises(UserError), self.cr.savepoint():
            rec.line_ids.write({'employee_id': other_employee.id})
        with self.assertRaises(AccessError):
            self.env['saddad.morro'].with_user(self.users['user']).create({'company_id': self.other.id})

    def test_journal_payment_only(self):
        rec = self._expense()
        with self.assertRaises(AccessError): rec.write({'journal_id': self.bank.id})
        rec.with_user(self.users['payment']).write({'journal_id': self.bank.id})
        self._payment(rec)
        rec.line_ids.with_user(self.users['payment']).action_mark_paid()
        with self.assertRaises(UserError): rec.with_user(self.users['payment']).write({'journal_id': self.bank.id})

    def test_configurable_morro_category(self):
        self.env.user.group_ids = [Command.link(self.env.ref('Saddad.group_manager').id)]
        root = self.env['product.category'].create({'name': 'Custom Morro'})
        child = self.env['product.category'].create({'name': 'Child', 'parent_id': root.id})
        settings = self.env['saddad.settings'].create({'company_id': self.company.id, 'morro_category_id': root.id})
        settings.action_save()
        self.assertEqual(self.company.saddad_morro_category_id, root)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._expense()
        self.product.categ_id = child
        rec = self._expense()
        self.assertEqual(rec.line_ids.morro_category_id, root)
        root.name = 'Renamed Category'
        rec.line_ids.write({'amount': 301})
        unrelated = self.env['product.category'].create({'name': 'Unrelated'})
        self.company.saddad_morro_category_id = unrelated
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.line_ids.write({'amount': 302})
        self.assertEqual(rec.line_ids.amount, 301)
        self.assertNotEqual(self.other.saddad_morro_category_id, unrelated)
        settings.company_id = self.other
        settings._onchange_company()
        self.assertEqual(settings.morro_category_id, self.other.saddad_morro_category_id)

    def test_category_domain_and_legacy_posted(self):
        rec = self._expense()
        move = self._post(rec)
        self.company.saddad_morro_category_id = self.env['product.category'].create({'name': 'New Policy'})
        self.assertEqual(rec.state, 'posted')
        self.assertEqual(rec.move_id, move)
        self.assertTrue(self.env['saddad.morro'].get_view(view_type='form'))
        domain = self.env['saddad.morro.line']._fields['product_id'].domain
        self.assertIn('child_of', domain)
        self.assertIn('company_id', domain)

    def test_forecast_stage_membership(self):
        rec = self._expense(count=2)
        self.assertEqual(rec.forecast_amount, 0)
        for user, state in [('user', 'fleet'), ('fleet', 'finance'), ('finance', 'gm'), ('gm', 'payment')]:
            rec.with_user(self.users[user]).action_approve()
            self.assertEqual(rec.state, state)
            self.assertEqual(rec.forecast_amount, 600)
        rec.line_ids[:1].with_user(self.users['payment']).action_mark_paid()
        self.assertEqual(rec.forecast_amount, 600)
        rec.line_ids[1:].with_user(self.users['payment']).action_mark_paid()
        self.assertEqual(rec.forecast_amount, 0)
        rec.with_user(self.users['post']).action_post()
        self.assertEqual(rec.forecast_amount, 0)

    def test_rejected_forecast_and_other_types(self):
        rec = self._expense()
        rec.action_approve()
        wizard = self.env['saddad.morro.reject'].with_user(self.users['fleet']).create({'expense_id': rec.id, 'reason': 'Incorrect violation'})
        wizard.action_apply()
        self.assertEqual(rec.forecast_amount, 0)
        rec.action_reset()
        rec.write({'expense_type': 'driving_licence'})
        rec.action_approve()
        self.assertEqual(rec.forecast_amount, 0)

    def test_duplicate_violation_normalization(self):
        rec = self._expense(violation_number=' \u0661\u0662\u0663\u0664\u0665 ')
        self.assertEqual(rec.line_ids.violation_key, '12345')
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self._expense(violation_number='12345')
        another = self._expense(violation_number='67890')
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            another.line_ids.write({'violation_number': '12345'})
        with self.assertRaises(AccessError):
            rec.line_ids.write({'violation_key': 'override'})

    def test_violation_details_required(self):
        for vals in ({'violation_number': False}, {'violation_date': False}, {'violation_date': fields.Date.today()+timedelta(days=1)}):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self._expense(**vals)

    def test_native_form(self):
        with Form(self.env['saddad.morro'].with_user(self.users['user'])) as form:
            with form.line_ids.new() as line:
                line.employee_id = self.employee
                line.product_id = self.product
                line.violation_number = 'FORM-123'
                line.violation_date = fields.Date.today()
        self.assertEqual(form.record.total_amount, 300)
        self.assertEqual(form.record.line_ids.paid_for, 'employee')

    def test_fleet_to_finance_notification(self):
        rule = self.env.ref('Saddad.approval_morro_finance')
        rule.write({'notify_email': True, 'notify_activity': True})
        rec = self._expense()
        rec.action_approve()
        rec.with_user(self.users['fleet']).action_approve()
        self.assertIn(self.users['finance'], rec.sudo().activity_ids.user_id)
        self.assertNotIn(self.users['gm'], rec.sudo().activity_ids.user_id)
        mail = self.env['mail.mail'].search([('model','=','saddad.morro'),('res_id','=',rec.id)])
        self.assertTrue(mail)
        expected = rec.with_context(lang=self.users['finance'].lang)._stage_label()
        self.assertTrue(any(expected in body for body in mail.mapped('body_html')), mail.mapped('body_html'))
        rec.with_user(self.users['finance']).action_approve()
        self.assertFalse(rec.sudo().activity_ids)

    def test_configurable_fleet_approval(self):
        self.env['saddad.approval.rule'].create({'name':'Custom Fleet','company_id':self.company.id,'transition':'morro_fleet','group_id':self.env.ref('Saddad.group_morro_finance').id,'notify_email':False,'notify_activity':False})
        rec=self._expense()
        rec.action_approve()
        with self.assertRaises(AccessError): rec.with_user(self.users['fleet']).action_approve()
        rec.with_user(self.users['finance']).action_approve()
        self.assertEqual(rec.state,'finance')

    def test_vehicle_and_analytic_account(self):
        brand = self.env['fleet.vehicle.model.brand'].create({'name':'Test Brand'})
        model = self.env['fleet.vehicle.model'].create({'name':'Test Car', 'brand_id':brand.id})
        vehicle = self.env['fleet.vehicle'].create({'model_id': model.id, 'license_plate':'MOR-123', 'company_id':self.company.id})
        plan = self.env['account.analytic.plan'].create({'name':'Morro Cost Plan'})
        analytic = self.env['account.analytic.account'].create({'name':'Morro Cost', 'plan_id':plan.id, 'company_id':self.company.id})
        rec = self._expense(vehicle_id=vehicle.id, analytic_account_id=analytic.id)
        self.assertEqual(rec.line_ids.license_plate,'MOR-123')
        move = self._post(rec)
        self.assertEqual(move.line_ids.filtered(lambda l:l.account_id==self.expense_account).analytic_distribution, {str(analytic.id):100})
        foreign = self.env['fleet.vehicle'].create({'model_id':model.id,'company_id':self.other.id})
        with self.assertRaises(UserError), self.cr.savepoint():
            self._expense(vehicle_id=foreign.id)

    def test_empty_request_and_protected_fields(self):
        rec = self.env['saddad.morro'].with_user(self.users['user']).create({})
        with self.assertRaises(ValidationError):rec.action_approve()
        with self.assertRaises(AccessError):rec.write({'forecast_amount':10})
        with self.assertRaises(AccessError):
            self.env['saddad.morro'].with_user(self.users['user']).create({'state':'posted'})
        with self.assertRaises(UserError):rec.copy()

    def test_arabic_views_and_stage_labels(self):
        if not self.env['res.lang'].search_count([('code','=','ar_001'),('active','=',True)]):
            self.skipTest('Arabic language is not active')
        rec = self._expense()
        rec.action_approve()
        label = rec.with_context(lang='ar_001')._stage_label()
        self.assertTrue(any('\u0600' <= c <= '\u06ff' for c in label))
        view = self.env['saddad.morro'].with_context(lang='ar_001').get_view(view_type='form')
        self.assertIn('statusbar', view['arch'])
        self.assertNotIn('<tree', view['arch'])
        translated = self.env['saddad.settings'].with_context(lang='ar_001').fields_get(['morro_category_id'])
        self.assertNotEqual(translated['morro_category_id']['string'], 'Morro Product Category')
