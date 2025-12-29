# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ExpenseType(models.Model):
	_name = "account.expense.type"
	_inherit = ['mail.thread', 'mail.activity.mixin']

	_description = "Account Expense Type Configuration"

	name = fields.Char(required=True, index=True)
	arabic_name = fields.Char()
	state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed')],
							 string='Status', required=True, readonly=True,
							 copy=False, default='draft')
	expense_nature = fields.Selection([('prepaid', 'Prepaid'), ('accrual', 'Accrual')],
									  string='Expense Nature', required=True)
	description = fields.Html()
	#For Prepaid Expense
	prepaid_amortization_method = fields.Selection([('monthly', 'Monthly'), ('on_time', 'On Time')],
												   string='Amortization Method',
												   help="""If you choice Monthly, you can distribute expenses Monthly.
												   If your choice On Time, you can’t distribute expenses Monthly""")
	prepaid_expense_account_id = fields.Many2one("account.account", string="Prepaid/Accrual Expense account",
												 domain="[('account_type', '=', 'expense'),('company_ids','in',[company_id])]")
	expense_account_id = fields.Many2one("account.account", string="Expense account",
										 domain="[('account_type', '=', 'expense')]")
	company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)

	@api.onchange("expense_nature")
	def _onchange_expense_nature(self):
		"""Reset all fields when expense_nature is changed."""
		for rec in self:
			rec.prepaid_amortization_method = False
			rec.prepaid_expense_account_id = False
			rec.expense_account_id = False

	def action_confirm(self):
		for rec in self:
			rec.state = "confirmed"

	def action_draft(self):
		for rec in self:
			rec.state = "draft"