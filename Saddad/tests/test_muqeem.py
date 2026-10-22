from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from odoo import Command, fields
from odoo.tests import TransactionCase, tagged, Form
from odoo.exceptions import AccessError, UserError, ValidationError


@tagged('post_install', '-at_install')
class TestMuqeem(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.currency_id = cls.env.ref('base.SAR')
        cls.company.account_fiscal_country_id = cls.env.ref('base.sa')
        cls.other = cls.env['res.company'].create({'name': 'Muqeem Other Company'})
        cls.expense_account = cls.env['account.account'].create({'name': 'Muqeem Test Expense', 'code': 'MUQ600', 'account_type': 'expense', 'company_ids': [Command.set(cls.company.ids)]})
        cls.bank_account = cls.env['account.account'].create({'name': 'Muqeem Test Bank', 'code': 'MUQ100', 'account_type': 'asset_cash', 'company_ids': [Command.set(cls.company.ids)]})
        cls.loan_account = cls.env['account.account'].create({'name': 'Muqeem Employee Loan', 'code': 'MUQ110', 'account_type': 'asset_current', 'company_ids': [Command.set(cls.company.ids)]})
        cls.deferred_account = cls.env['account.account'].create({'name': 'Muqeem Deferred', 'code': 'MUQ120', 'account_type': 'asset_current', 'company_ids': [Command.set(cls.company.ids)]})
        cls.bank = cls.env['account.journal'].create({'name': 'Muqeem Bank', 'code': 'MQBK', 'type': 'bank', 'company_id': cls.company.id, 'default_account_id': cls.bank_account.id})
        cls.general = cls.env['account.journal'].create({'name': 'Muqeem Deferral', 'code': 'MQDF', 'type': 'general', 'company_id': cls.company.id})
        cls.company.write({'saddad_bank_journal_id': cls.bank.id, 'saddad_employee_loan_account_id': cls.loan_account.id,
                           'deferred_expense_account_id': cls.deferred_account.id, 'deferred_expense_journal_id': cls.general.id,
                           'deferred_expense_amount_computation_method': 'day'})
        cls.product = cls.env['product.product'].create({'name': 'Muqeem Service', 'type': 'service', 'categ_id': cls.env.ref('Saddad.category_muqeem').id, 'standard_price': 300, 'property_account_expense_id': cls.expense_account.id, 'supplier_taxes_id': [Command.clear()]})
        cls.employee = cls.env['hr.employee'].create({'name': 'Muqeem Employee', 'company_id': cls.company.id, 'identification_id': '2000000221', 'saddad_iqama_expiry': fields.Date.today()})
        cls.employee2 = cls.env['hr.employee'].create({'name': 'Muqeem Second', 'company_id': cls.company.id, 'identification_id': '2000000222', 'saddad_iqama_expiry': fields.Date.today()})
        cls.users = {}
        for key, group in [('user','muqeem_user'), ('hr','muqeem_hr'), ('finance','muqeem_finance'), ('gm','muqeem_gm'), ('payment','payment'), ('post','muqeem_post'), ('plain',False)]:
            cls.users[key] = cls.env['res.users'].with_context(no_reset_password=True).create({'name': 'Muqeem '+key, 'login': 'muqeem_'+key,
                'email': key+'@example.invalid', 'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
                'group_ids': [Command.set([cls.env.ref('Saddad.group_'+group if group else 'base.group_user').id])]})
        cls.env['saddad.approval.rule'].search([]).write({'notify_email': False, 'notify_activity': False})

    def _expense(self, count=1, **line_values):
        values = {'employee_id': self.employee.id, 'product_id': self.product.id}
        values.update(line_values)
        lines = [Command.create(values)]
        if count == 2:
            lines.append(Command.create(dict(values, employee_id=self.employee2.id)))
        return self.env['saddad.muqeem.expense'].with_user(self.users['user']).create({'line_ids': lines})

    def _payment(self, rec):
        for user in ['user', 'user', 'hr', 'finance', 'gm']:
            rec.with_user(self.users[user]).action_approve()
        self.assertEqual(rec.state, 'payment')

    def _post(self, rec):
        self._payment(rec)
        rec.line_ids.with_user(self.users['payment']).action_mark_paid()
        rec.with_user(self.users['post']).action_post()
        return rec.sudo().move_id

    def test_expense_line_reporting_and_navigation(self):
        rec = self._expense(2)
        lines = self.env['saddad.muqeem.line'].with_user(self.users['user'])
        domain = [('expense_id', '=', rec.id)]
        groups = lines._read_group(domain, ['employee_id'], ['amount:sum'])
        self.assertEqual({employee.id: amount for employee, amount in groups},
                         {self.employee.id: 300, self.employee2.id: 300})
        groups = lines._read_group(domain, ['product_id'], ['amount:sum'])
        self.assertEqual([(product.id, amount) for product, amount in groups], [(self.product.id, 600)])
        for kind in ('list', 'search'):
            lines.get_view(self.env.ref('Saddad.view_muqeem_line_' + kind).id, kind)
        action = rec.line_ids[:1].action_open_expense()
        self.assertEqual(action['res_id'], rec.id)
        self.assertEqual(action['res_model'], 'saddad.muqeem.expense')
        with self.assertRaises(AccessError):
            rec.line_ids[:1].with_user(self.users['plain']).action_open_expense()

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
        rec.action_approve()
        with self.assertRaises(AccessError):
            rec.action_approve()
        with self.assertRaises(UserError):
            rec.line_ids.write({'amount': 999})

    def test_rejection_reason_and_reset(self):
        rec = self._expense()
        rec.action_approve()
        wizard = self.env['saddad.muqeem.reject'].with_user(self.users['user']).create({'expense_id': rec.id, 'reason': 'Missing supporting document'})
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
        group = self.env['account.tax.group'].create({'name':'Muqeem VAT Group','company_id':self.company.id})
        tax = self.env['account.tax'].create({'tax_group_id':group.id,'name': 'Muqeem VAT', 'amount': 15, 'type_tax_use': 'purchase', 'company_id': self.company.id})
        tax.invoice_repartition_line_ids.filtered(lambda l: l.repartition_type == 'tax').account_id = self.loan_account
        rec = self._expense(tax_ids=[Command.set(tax.ids)])
        self.assertEqual(rec.total_amount, 345)
        move = self._post(rec)
        self.assertEqual(move.line_ids.filtered('tax_repartition_line_id').debit, 45)
        self.assertEqual(sum(move.line_ids.mapped('balance')), 0)

    def test_deferred_native_schedule(self):
        start = fields.Date.today() + relativedelta(months=1, day=1)
        rec = self._expense(defer_expense=True, defer_start=start, defer_end=start+relativedelta(months=3))
        self.assertFalse(rec.sudo().move_id)
        move = self._post(rec)
        self.assertTrue(move.deferred_move_ids)
        self.assertEqual(rec.state, 'posted')
        self.assertEqual(move.line_ids.filtered(lambda l: l.account_id == self.expense_account).deferred_start_date, start)
        schedule = move.deferred_move_ids
        self.assertTrue(schedule.filtered(lambda m: m.state == 'draft' and m.auto_post == 'at_date'))
        amounts = schedule.line_ids.filtered(lambda l: l.account_id == self.expense_account)
        self.assertAlmostEqual(sum(amounts.mapped('balance')), 0, places=2)
        self.assertEqual(sum(amounts.mapped('debit')), 300)
        with self.assertRaises(UserError):
            rec.sudo()._generate_deferrals()

    def test_deferred_prepayments_native_schedule(self):
        self.deferred_account.account_type = 'asset_prepayments'
        self.test_deferred_native_schedule()
        holding_lines = self.env['account.move.line'].search([
            ('account_id', '=', self.deferred_account.id),
        ])
        self.assertEqual(sum(holding_lines.mapped('debit')), 300)
        self.assertEqual(sum(holding_lines.mapped('credit')), 300)

    def test_deferral_invalid_account_type_rolls_back(self):
        self.company.deferred_expense_account_id = self.expense_account
        rec = self._expense(defer_expense=True)
        self._payment(rec)
        rec.line_ids.with_user(self.users['payment']).action_mark_paid()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.with_user(self.users['post']).action_post()
        self.assertFalse(rec.sudo().move_id)
        self.assertEqual(rec.state, 'done')

    def test_deferral_missing_config_rolls_back(self):
        rec = self._expense(defer_expense=True)
        self._payment(rec)
        rec.line_ids.with_user(self.users['payment']).action_mark_paid()
        self.company.deferred_expense_account_id = False
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.with_user(self.users['post']).action_post()
        self.assertFalse(rec.sudo().move_id)
        self.assertEqual(rec.state, 'done')

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
            self.env['saddad.muqeem.expense'].with_user(self.users['user']).create({'company_id': self.other.id})

    def test_journal_payment_only(self):
        rec = self._expense()
        with self.assertRaises(AccessError): rec.write({'journal_id': self.bank.id})
        rec.with_user(self.users['payment']).write({'journal_id': self.bank.id})
        self._payment(rec)
        rec.line_ids.with_user(self.users['payment']).action_mark_paid()
        with self.assertRaises(UserError): rec.with_user(self.users['payment']).write({'journal_id': self.bank.id})

    def test_native_form(self):
        with Form(self.env['saddad.muqeem.expense'].with_user(self.users['user'])) as form:
            with form.line_ids.new() as line:
                line.employee_id = self.employee
                line.product_id = self.product
        self.assertEqual(form.record.total_amount, 300)
        self.assertEqual(form.record.line_ids.defer_start, self.employee.saddad_iqama_expiry)

    def test_notifications(self):
        rule = self.env.ref('Saddad.approval_muqeem_hr')
        rule.write({'notify_email': True, 'notify_activity': True})
        rec = self._expense()
        rec.action_approve()
        rec.action_approve()
        self.assertIn(self.users['hr'], rec.sudo().activity_ids.user_id)
        self.assertTrue(self.env['mail.mail'].search_count([('model','=','saddad.muqeem.expense'),('res_id','=',rec.id)]))
        rec.with_user(self.users['hr']).action_approve()
        self.assertFalse(rec.sudo().activity_ids)
    def test_qiwa_consolidation_and_idempotence(self):
        mapping = self.env['saddad.service.mapping'].search([('company_id','=',self.company.id),('service_type','=','work_permit'),('period','=','3')],limit=1)
        batch = self.env['saddad.qiwa.batch'].create({'reference':'MUQEEM-QA-1','issue_date':fields.Date.today(),'due_date':fields.Date.today()+timedelta(days=10),
            'line_ids':[Command.create({'employee_id':e.id,'mapping_id':mapping.id}) for e in self.employee|self.employee2]})
        batch.action_review()
        batch.action_confirm()
        self.assertEqual(len(batch.muqeem_ids),1)
        expense=batch.muqeem_ids
        self.assertEqual(len(expense.line_ids),2)
        self.assertEqual(expense.total_amount,batch.total_amount)
        self.assertFalse(any(expense.line_ids.mapped('paid')))
        batch.action_prepare_muqeem()
        self.assertEqual(batch.muqeem_ids,expense)
        with self.assertRaises(UserError): expense.line_ids[:1].unlink()
        with self.assertRaises(UserError): expense.line_ids[:1].write({'amount':1})

    def test_configured_company_approval_override(self):
        rule=self.env['saddad.approval.rule'].create({'name':'Custom HR','company_id':self.company.id,'transition':'muqeem_hr','group_id':self.env.ref('Saddad.group_muqeem_finance').id,'notify_email':False,'notify_activity':False})
        rec=self._expense()
        rec.action_approve()
        rec.action_approve()
        with self.assertRaises(AccessError): rec.with_user(self.users['hr']).action_approve()
        rec.with_user(self.users['finance']).action_approve()
        self.assertEqual(rec.state,'finance')

    def test_deferred_rounding_month_methods(self):
        for method in ['month','full_months']:
            with self.subTest(method=method):
                self.company.deferred_expense_amount_computation_method=method
                start=fields.Date.today()+relativedelta(months=1,day=15)
                rec=self._expense(amount=100.01,defer_expense=True,defer_start=start,defer_end=start+relativedelta(months=3))
                move=self._post(rec)
                expense_lines=move.deferred_move_ids.line_ids.filtered(lambda l:l.account_id==self.expense_account)
                self.assertAlmostEqual(sum(expense_lines.mapped('debit')),100.01,places=2)
                self.assertAlmostEqual(sum(expense_lines.mapped('balance')),0,places=2)

    def test_future_deferrals_can_auto_post(self):
        start=fields.Date.today()+relativedelta(months=1,day=1)
        move=self._post(self._expense(defer_expense=True,defer_start=start,defer_end=start+relativedelta(months=3)))
        future=move.deferred_move_ids.filtered(lambda m:m.state=='draft')[:1]
        self.assertTrue(future)
        from unittest.mock import patch
        with patch.object(fields.Date, 'context_today', return_value=future.date):
            future._post(soft=False)
        self.assertEqual(future.state,'posted')
    def test_direct_ptr_expense_can_complete_payment_and_posting(self):
        mapping = self.env['saddad.service.mapping'].search([('company_id', '=', self.company.id), ('service_type', '=', 'iqama'), ('period', '=', '3')], limit=1)
        mapping.product_id = self.product
        ptr = self.env['saddad.ptr'].create({'employee_id': self.employee.id, 'line_ids': [Command.create({'mapping_id': mapping.id})]})
        ptr.action_review()
        ptr.action_confirm()
        expense = ptr.direct_muqeem_ids
        move = self._post(expense)
        self.assertEqual(expense.state, 'posted')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(expense.line_ids.ptr_line_id, ptr.line_ids)
        ptr.action_prepare_muqeem()
        self.assertEqual(ptr.direct_muqeem_ids, expense)
        self.assertEqual(len(ptr.direct_muqeem_ids), 1)

    def test_inclusive_deferral_defaults(self):
        for start, period, expected in [
            (date(2026, 12, 1), '3', date(2027, 2, 28)),
            (date(2026, 12, 15), '3', date(2027, 3, 14)),
            (date(2023, 12, 1), '3', date(2024, 2, 29)),
            (date(2026, 1, 31), '3', date(2026, 4, 29)),
            (date(2026, 12, 1), '6', date(2027, 5, 31)),
            (date(2026, 12, 1), '9', date(2027, 8, 31)),
            (date(2026, 12, 1), '12', date(2027, 11, 30)),
        ]:
            with self.subTest(start=start, period=period):
                rec = self._expense(defer_start=start, period=period)
                self.assertEqual(rec.line_ids.defer_end, expected)
                preview = self.env['saddad.muqeem.line'].new({'defer_start': start, 'period': period})
                preview._onchange_start()
                self.assertEqual(preview.defer_end, expected)
        override = self._expense(defer_start=date(2026, 12, 1), defer_end=date(2027, 3, 10))
        self.assertEqual(override.line_ids.defer_end, date(2027, 3, 10))

    def test_three_month_default_schedule(self):
        self.company.deferred_expense_amount_computation_method = 'month'
        rec = self._expense(defer_expense=True, defer_start=date(2026, 12, 1), period='3')
        move = self._post(rec)
        self.assertEqual(len(move.deferred_move_ids), 4)
        recognition = move.deferred_move_ids.filtered(lambda m: m.date >= date(2026, 12, 1))
        self.assertEqual(set(recognition.mapped('date')), {date(2026, 12, 31), date(2027, 1, 31), date(2027, 2, 28)})
        self.assertEqual(sum(recognition.line_ids.filtered(lambda l: l.account_id == self.expense_account).mapped('debit')), 300)

    def test_optional_product_deferred_accounts(self):
        if 'property_deferred_expense_account_id' not in self.product.product_tmpl_id._fields:
            self.skipTest('Optional product deferral addon not installed')
        parent = self.env['product.category'].create({'name': 'Deferred Parent', 'parent_id': self.env.ref('Saddad.category_muqeem').id})
        category = self.env['product.category'].create({'name': 'Deferred Child', 'parent_id': parent.id})
        self.product.categ_id = category
        product_account = self.env['account.account'].create({'name': 'Product Deferred', 'code': 'MUQ121', 'account_type': 'asset_non_current', 'company_ids': [Command.set(self.company.ids)]})
        category_account = self.env['account.account'].create({'name': 'Category Deferred', 'code': 'MUQ122', 'account_type': 'asset_prepayments', 'company_ids': [Command.set(self.company.ids)]})
        template = self.product.product_tmpl_id.with_company(self.company)
        parent = parent.with_company(self.company)
        category = category.with_company(self.company)
        parent.property_deferred_expense_account_categ_id = category_account
        for mode, expected in [('product', product_account), ('parent', category_account), ('category', product_account), ('company', self.deferred_account)]:
            with self.subTest(mode=mode):
                template.property_deferred_expense_account_id = product_account if mode == 'product' else False
                category.property_deferred_expense_account_categ_id = product_account if mode == 'category' else False
                if mode == 'company':
                    parent.property_deferred_expense_account_categ_id = False
                # Product/category configurations work without a company fallback.
                self.company.deferred_expense_account_id = self.deferred_account if mode == 'company' else False
                rec = self._expense(defer_expense=True, defer_start=date(2027, 1, 1))
                move = self._post(rec)
                legs = move.deferred_move_ids.line_ids.filtered(lambda l: l.account_id != self.expense_account)
                self.assertEqual(legs.account_id, expected)
                self.assertEqual(sum(legs.mapped('debit')), 300)
                self.assertEqual(sum(legs.mapped('credit')), 300)
                with self.assertRaises(UserError):
                    rec.line_ids.move_line_id.write({'deferred_expense_account_override_id': expected.id})

    def test_optional_invalid_product_account_atomic(self):
        if 'property_deferred_expense_account_id' not in self.product.product_tmpl_id._fields:
            self.skipTest('Optional product deferral addon not installed')
        self.product.product_tmpl_id.with_company(self.company).property_deferred_expense_account_id = self.expense_account
        rec = self._expense(defer_expense=True)
        self._payment(rec)
        rec.line_ids.with_user(self.users['payment']).action_mark_paid()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.with_user(self.users['post']).action_post()
        self.assertFalse(rec.sudo().move_id)
        self.assertEqual(rec.state, 'done')

    def test_optional_two_products_separate_accounts(self):
        if 'property_deferred_expense_account_id' not in self.product.product_tmpl_id._fields:
            self.skipTest('Optional product deferral addon not installed')
        other_product = self.env['product.product'].create({'name': 'Other Deferred Service', 'type': 'service', 'categ_id': self.env.ref('Saddad.category_muqeem').id, 'standard_price': 300, 'property_account_expense_id': self.expense_account.id, 'supplier_taxes_id': [Command.clear()]})
        account = self.env['account.account'].create({'name': 'Other Prepaid', 'code': 'MUQ123', 'account_type': 'asset_prepayments', 'company_ids': [Command.set(self.company.ids)]})
        other_product.product_tmpl_id.with_company(self.company).property_deferred_expense_account_id = account
        rec = self._expense(defer_expense=True, defer_start=date(2027, 1, 1))
        rec.write({'line_ids': [Command.create({'employee_id': self.employee2.id, 'product_id': other_product.id, 'defer_expense': True, 'defer_start': date(2027, 1, 1)})]})
        move = self._post(rec)
        for expected in (account, self.deferred_account):
            legs = move.deferred_move_ids.line_ids.filtered(lambda l: l.account_id == expected)
            self.assertEqual(sum(legs.mapped('debit')), 300)
            self.assertEqual(sum(legs.mapped('credit')), 300)

    def test_optional_cross_company_account_rejected(self):
        if 'property_deferred_expense_account_id' not in self.product.product_tmpl_id._fields:
            self.skipTest('Optional product deferral addon not installed')
        foreign = self.env['account.account'].create({'name': 'Foreign Prepaid', 'code': 'MUQ124', 'account_type': 'asset_prepayments', 'company_ids': [Command.set(self.other.ids)]})
        self.product.product_tmpl_id.with_company(self.company).property_deferred_expense_account_id = foreign
        rec = self._expense(defer_expense=True)
        self._payment(rec)
        rec.line_ids.with_user(self.users['payment']).action_mark_paid()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.with_user(self.users['post']).action_post()
        self.assertFalse(rec.sudo().move_id)

    def test_configurable_muqeem_category(self):
        self.env.user.group_ids = [Command.link(self.env.ref('Saddad.group_manager').id)]
        root = self.env['product.category'].create({'name': 'Custom Muqeem'})
        child = self.env['product.category'].create({'name': 'Child', 'parent_id': root.id})
        settings = self.env['saddad.settings'].create({'company_id': self.company.id, 'muqeem_category_id': root.id})
        settings.action_save()
        self.assertEqual(self.company.saddad_muqeem_category_id, root)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._expense()
        self.product.categ_id = child
        rec = self._expense()
        self.assertEqual(rec.line_ids.muqeem_category_id, root)
        root.name = 'Renamed Category'
        rec.line_ids.write({'amount': 301})
        unrelated = self.env['product.category'].create({'name': 'Unrelated'})
        self.company.saddad_muqeem_category_id = unrelated
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.line_ids.write({'amount': 302})
        self.assertEqual(rec.line_ids.amount, 301)
        self.assertNotEqual(self.other.saddad_muqeem_category_id, unrelated)
        settings.company_id = self.other
        settings._onchange_company()
        self.assertEqual(settings.muqeem_category_id, self.other.saddad_muqeem_category_id)

    def test_category_domain_and_legacy_posted(self):
        rec = self._expense()
        move = self._post(rec)
        self.company.saddad_muqeem_category_id = self.env['product.category'].create({'name': 'New Policy'})
        self.assertEqual(rec.state, 'posted')
        self.assertEqual(rec.move_id, move)
        self.assertTrue(self.env['saddad.muqeem.expense'].get_view(view_type='form'))
        domain = self.env['saddad.muqeem.line']._fields['product_id'].domain
        self.assertIn('child_of', domain)
        self.assertIn('company_id', domain)
