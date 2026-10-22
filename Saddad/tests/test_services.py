from datetime import date
from odoo import Command, fields
from odoo.tests import TransactionCase, tagged, Form
from odoo.exceptions import AccessError, UserError, ValidationError
from psycopg2 import IntegrityError

@tagged("post_install", "-at_install")
class TestServices(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.currency_id = cls.env.ref('base.SAR')
        cls.company.account_fiscal_country_id = cls.env.ref('base.sa')
        cls.other = cls.env['res.company'].create({'name': 'Service Other Company'})
        cls.expense_account = cls.env['account.account'].create({'name': 'Service Test Expense', 'code': 'MUQ600', 'account_type': 'expense', 'company_ids': [Command.set(cls.company.ids)]})
        cls.bank_account = cls.env['account.account'].create({'name': 'Service Test Bank', 'code': 'MUQ100', 'account_type': 'asset_cash', 'company_ids': [Command.set(cls.company.ids)]})
        cls.loan_account = cls.env['account.account'].create({'name': 'Service Employee Loan', 'code': 'MUQ110', 'account_type': 'asset_current', 'company_ids': [Command.set(cls.company.ids)]})
        cls.deferred_account = cls.env['account.account'].create({'name': 'Service Deferred', 'code': 'MUQ120', 'account_type': 'asset_current', 'company_ids': [Command.set(cls.company.ids)]})
        cls.bank = cls.env['account.journal'].create({'name': 'Service Bank', 'code': 'MQBK', 'type': 'bank', 'company_id': cls.company.id, 'default_account_id': cls.bank_account.id})
        cls.general = cls.env['account.journal'].create({'name': 'Service Deferral', 'code': 'MQDF', 'type': 'general', 'company_id': cls.company.id})
        cls.company.write({'saddad_bank_journal_id': cls.bank.id, 'saddad_employee_loan_account_id': cls.loan_account.id,
                           'deferred_expense_account_id': cls.deferred_account.id, 'deferred_expense_journal_id': cls.general.id,
                           'deferred_expense_amount_computation_method': 'day'})
        cls.product = cls.env['product.product'].create({'name': 'Service Service', 'type': 'service', 'categ_id': cls.env.ref('Saddad.category_services').id, 'standard_price': 300, 'property_account_expense_id': cls.expense_account.id, 'supplier_taxes_id': [Command.clear()]})
        cls.partner = cls.env['res.partner'].create({'name':'Service Biller Partner'})
        cls.biller = cls.env['saddad.biller'].create({'name':'Test Biller','code':'TEST','partner_id':cls.partner.id,'company_id':cls.company.id})
        cls.users = {}
        for key, group in [('user','services_user'), ('finance','services_finance'), ('gm','services_gm'), ('payment','payment'), ('post','services_post'), ('plain',False)]:
            cls.users[key] = cls.env['res.users'].with_context(no_reset_password=True).create({'name': 'Service '+key, 'login': 'services_'+key,
                'email': key+'@example.invalid', 'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
                'group_ids': [Command.set([cls.env.ref('Saddad.group_'+group if group else 'base.group_user').id])]})
        cls.env['saddad.approval.rule'].search([]).write({'notify_email': False, 'notify_activity': False})

    def _expense(self, count=1, **line_values):
        values = {'product_id': self.product.id, 'invoice_number': 'INV-123'}
        values.update(line_values)
        lines = [Command.create(values)]
        if count == 2:
            lines.append(Command.create(dict(values, invoice_number='INV-124')))
        return self.env['saddad.service.request'].with_user(self.users['user']).create({'description':'Service Test', 'biller_id': self.biller.id, 'line_ids': lines})

    def _payment(self, rec):
        for user in ['user', 'user', 'finance', 'gm']:
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
        rec.with_user(self.users['user']).action_approve()
        with self.assertRaises(AccessError):
            rec.action_approve()
        with self.assertRaises(UserError):
            rec.line_ids.write({'amount': 999})

    def test_rejection_reason_and_reset(self):
        rec = self._expense()
        rec.action_approve()
        rec.action_approve()
        wizard = self.env['saddad.service.reject'].with_user(self.users['finance']).create({'expense_id': rec.id, 'reason': 'Missing supporting document'})
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

    def test_vat_direct_journal(self):
        group = self.env['account.tax.group'].create({'name':'Service VAT Group','company_id':self.company.id})
        tax = self.env['account.tax'].create({'tax_group_id':group.id,'name': 'Service VAT', 'amount': 15, 'type_tax_use': 'purchase', 'company_id': self.company.id})
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

    def test_journal_payment_only(self):
        rec = self._expense()
        with self.assertRaises(AccessError): rec.write({'journal_id': self.bank.id})
        rec.with_user(self.users['payment']).write({'journal_id': self.bank.id})
        self._payment(rec)
        rec.line_ids.with_user(self.users['payment']).action_mark_paid()
        with self.assertRaises(UserError): rec.with_user(self.users['payment']).write({'journal_id': self.bank.id})

    def test_configurable_services_category(self):
        self.env.user.group_ids = [Command.link(self.env.ref('Saddad.group_manager').id)]
        root = self.env['product.category'].create({'name': 'Custom Service'})
        child = self.env['product.category'].create({'name': 'Child', 'parent_id': root.id})
        settings = self.env['saddad.settings'].create({'company_id': self.company.id, 'services_category_id': root.id})
        settings.action_save()
        self.assertEqual(self.company.saddad_services_category_id, root)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._expense()
        self.product.categ_id = child
        rec = self._expense()
        self.assertEqual(rec.line_ids.services_category_id, root)
        root.name = 'Renamed Category'
        rec.line_ids.write({'amount': 301})
        unrelated = self.env['product.category'].create({'name': 'Unrelated'})
        self.company.saddad_services_category_id = unrelated
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.line_ids.write({'amount': 302})
        self.assertEqual(rec.line_ids.amount, 301)
        self.assertNotEqual(self.other.saddad_services_category_id, unrelated)
        settings.company_id = self.other
        settings._onchange_company()
        self.assertEqual(settings.services_category_id, self.other.saddad_services_category_id)

    def test_category_domain_and_legacy_posted(self):
        rec = self._expense()
        move = self._post(rec)
        self.company.saddad_services_category_id = self.env['product.category'].create({'name': 'New Policy'})
        self.assertEqual(rec.state, 'posted')
        self.assertEqual(rec.move_id, move)
        self.assertTrue(self.env['saddad.service.request'].get_view(view_type='form'))
        domain = self.env['saddad.service.line']._fields['product_id'].domain
        self.assertIn('child_of', domain)
        self.assertIn('company_id', domain)

    def test_arabic_views_and_stage_labels(self):
        if not self.env['res.lang'].search_count([('code','=','ar_001'),('active','=',True)]):
            self.skipTest('Arabic language is not active')
        rec = self._expense()
        rec.action_approve()
        label = rec.with_context(lang='ar_001')._stage_label()
        self.assertTrue(any('\u0600' <= c <= '\u06ff' for c in label))
        view = self.env['saddad.service.request'].with_context(lang='ar_001').get_view(view_type='form')
        self.assertIn('statusbar', view['arch'])
        self.assertNotIn('<tree', view['arch'])
        translated = self.env['saddad.settings'].with_context(lang='ar_001').fields_get(['services_category_id'])
        self.assertNotEqual(translated['services_category_id']['string'], 'Saddad Services Product Category')

    def test_native_form(self):
        with Form(self.env['saddad.service.request'].with_user(self.users['user'])) as form:
            form.description = 'Government service invoice'
            form.biller_id = self.biller
            with form.line_ids.new() as line:
                line.product_id = self.product
                line.invoice_number = 'INV-FORM'
        self.assertEqual(form.record.total_amount, 300)
        self.assertEqual(form.record.untaxed_amount, 300)
        self.assertEqual(form.record.tax_amount, 0)

    def test_biller_permissions_company_and_duplicates(self):
        values = {'name':'Another','code':'TEST','partner_id':self.partner.id,'company_id':self.company.id}
        with self.assertRaises(AccessError):
            self.env['saddad.biller'].with_user(self.users['user']).create(values)
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env['saddad.biller'].create(values)
        other = self.env['saddad.biller'].create(dict(values,company_id=self.other.id))
        with self.assertRaises(UserError), self.cr.savepoint():
            self.env['saddad.service.request'].with_user(self.users['user']).create({'description':'Wrong company','biller_id':other.id})
        rec = self._expense()
        self.biller.active = False
        with self.assertRaises(ValidationError):rec.action_approve()

    def test_vat_included_and_biller_partner(self):
        group = self.env['account.tax.group'].create({'name':'Service VAT Group','company_id':self.company.id})
        tax = self.env['account.tax'].create({'tax_group_id':group.id,'name':'Inclusive VAT','amount':15,'type_tax_use':'purchase','company_id':self.company.id,'price_include_override':'tax_included'})
        tax.invoice_repartition_line_ids.filtered(lambda l:l.repartition_type=='tax').account_id = self.loan_account
        rec = self._expense(amount=115, tax_ids=[Command.set(tax.ids)])
        self.assertEqual(rec.untaxed_amount, 100)
        self.assertEqual(rec.tax_amount, 15)
        self.assertEqual(rec.total_amount, 115)
        move = self._post(rec)
        debit = move.line_ids.filtered(lambda l:l.account_id==self.expense_account)
        self.assertEqual(debit.debit,100)
        self.assertEqual(debit.partner_id,self.partner)
        self.assertEqual(move.line_ids.filtered(lambda l:l.account_id==self.bank_account).credit,115)

    def test_analytic_and_attachment(self):
        plan = self.env['account.analytic.plan'].create({'name':'Service Cost Plan'})
        analytic = self.env['account.analytic.account'].create({'name':'Service Cost','plan_id':plan.id,'company_id':self.company.id})
        rec = self._expense(analytic_account_id=analytic.id, attachment='dGVzdA==', attachment_filename='test.txt')
        self.assertTrue(rec.line_ids.attachment)
        move = self._post(rec)
        self.assertEqual(move.line_ids.filtered(lambda l:l.account_id==self.expense_account).analytic_distribution,{str(analytic.id):100})
        with self.assertRaises(UserError):move.line_ids.write({'analytic_distribution':False})

    def test_review_notification_to_finance(self):
        self.env.ref('Saddad.approval_services_finance').write({'notify_email':True,'notify_activity':True})
        rec = self._expense()
        rec.action_approve()
        self.assertEqual(rec.state,'reviewed')
        rec.action_approve()
        self.assertEqual(rec.state,'finance')
        self.assertIn(self.users['finance'],rec.sudo().activity_ids.user_id)
        mail = self.env['mail.mail'].search([('model','=','saddad.service.request'),('res_id','=',rec.id)])
        expected = rec.with_context(lang=self.users['finance'].lang)._stage_label()
        self.assertTrue(any(expected in body for body in mail.mapped('body_html')))
        rec.with_user(self.users['finance']).action_approve()
        self.assertFalse(rec.sudo().activity_ids)

    def test_configurable_review_rule(self):
        self.env['saddad.approval.rule'].create({'name':'Custom Review','company_id':self.company.id,'transition':'services_reviewed','group_id':self.env.ref('Saddad.group_services_finance').id,'notify_email':False,'notify_activity':False})
        rec=self._expense()
        rec.action_approve()
        with self.assertRaises(AccessError):rec.action_approve()
        rec.with_user(self.users['finance']).action_approve()
        self.assertEqual(rec.state,'finance')

    def test_empty_and_protected_request(self):
        rec=self.env['saddad.service.request'].with_user(self.users['user']).create({'description':'Empty','biller_id':self.biller.id})
        with self.assertRaises(ValidationError):rec.action_approve()
        with self.assertRaises(AccessError):rec.write({'tax_amount':1})
        with self.assertRaises(UserError):rec.copy()
        other = self._expense()
        with self.assertRaises(AccessError):other.line_ids.write({'tax_amount':1})
        self._payment(other)
        with self.assertRaises(UserError):other.line_ids.write({'invoice_number':'CHANGED'})
