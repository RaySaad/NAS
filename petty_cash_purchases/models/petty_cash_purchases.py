from odoo import api, fields, Command, models, _
from odoo.exceptions import AccessError, UserError, ValidationError, RedirectWarning
import json

class PettyCashPurchase(models.Model):
	_name = "petty.cash.purchase"
	_inherit = ['mail.thread.main.attachment', 'mail.activity.mixin']
	_description = "Petty Cash Purchase"
	_check_company_auto = True

	@api.depends('state')
	def _compute_can_edit(self):
		for rec in self:
			rec.can_edit = True if rec.state == 'draft' else False

	can_edit = fields.Boolean(compute='_compute_can_edit')
	name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')

	expenses_line_ids = fields.One2many(
		comodel_name='expense.lines', inverse_name='sheet_id',
		string="Expense Lines",
		copy=True,
	)
	state = fields.Selection(
		selection=[
			('draft', 'To Submit'),
			('submit', 'Submitted'),
			('approve', 'Approved'),
			('post', 'Posted'),
			('done', 'Done'),
			('cancel', 'Refused')
		],
		string="Status",
		index=True,
		default='draft',
		tracking=True,
		copy=False,
	)

	pcp_type = fields.Selection(
		selection=[
			('normal', 'Post Through Approvals'),
			('immediate', 'Post Immediately'),
		],
		string="Type",
		default='normal',
		tracking=True,
		copy=False,
	)

	company_id = fields.Many2one(
		comodel_name='res.company',
		string="Company",
		required=True,
		readonly=True,
		default=lambda self: self.env.company,
	)
	employee_id = fields.Many2one(
		comodel_name='res.partner',
		string="Employee",
		check_company=True,
		tracking=True,
	)

	def _default_account_id(self):
		property_field = self.env['product.category']._fields['property_account_expense_categ_id']
		for _expense in self:
			expense = _expense.with_company(_expense.company_id)
			expense.account_id = property_field.get_company_dependent_fallback(self.env['product.category'])

	account_id = fields.Many2one(
		comodel_name='account.account',
		string="Account C",
		check_company=True,
		tracking=True,
		default=_default_account_id
	)

	total_amount = fields.Monetary(
		string="Total",
		currency_field='company_currency_id',
		compute='_compute_amount', store=True, readonly=True,
		tracking=True,
	)
	untaxed_amount = fields.Monetary(
		string="Untaxed Amount",
		currency_field='company_currency_id',
		compute='_compute_amount', store=True, readonly=True,
	)
	total_tax_amount = fields.Monetary(
		string="Taxes",
		currency_field='company_currency_id',
		compute='_compute_amount', store=True, readonly=True,
	)

	company_currency_id = fields.Many2one(
		comodel_name='res.currency',
		related='company_id.currency_id',
		string="Report Company Currency"
	)

	employee_journal_id = fields.Many2one(
		comodel_name='account.journal',
		string="Journal",
		check_company=True,
		help="The journal used when the expense is paid by employee.",
	)
	
	move_id = fields.Many2one('account.move', copy=False)
	move_line = fields.One2many('account.move', 'petty_id', copy=False)
	jv_count = fields.Integer(compute='_compute_jv')

	# @api.onchange('employee_id')
	# def get_employee_payable(self):
	# 	for x in self:
	# 		if x.employee_id and x.employee_id.property_account_payable_id:
	# 			x.account_id = x.employee_id.property_account_payable_id.id
	# 		else:
	# 			x.account_id = False

	def action_view_journal_entries(self):
		return {
			'type': 'ir.actions.act_window',
			'name': _("Journal Entry"),
			'res_model': 'account.move',
			'view_mode': 'list,form',
			'domain': [('id', 'in', self.move_line.ids)],
			'views': [(self.env.ref('account.view_move_tree').id, 'list'), (False, 'form')],
		}

	def _compute_jv(self):
		for rec in self:
			rec.jv_count = len(self.move_line)

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if vals.get('name', 'New') == 'New':
				vals['name'] = self.env['ir.sequence'].next_by_code('petty.cash.purchase') or 'New'
			return super(PettyCashPurchase, self).create(vals)

	@api.depends('expenses_line_ids.total_amount', 'expenses_line_ids.tax_amount')
	def _compute_amount(self):
		for sheet in self:
			sheet.total_amount = sum(sheet.expenses_line_ids.mapped('total_amount'))
			sheet.total_tax_amount = sum(sheet.expenses_line_ids.mapped('tax_amount'))
			sheet.untaxed_amount = sheet.total_amount - sheet.total_tax_amount

	def submit(self):
		if len(self.expenses_line_ids) < 1:
			raise ValidationError(_('Can not submit if there is no expense.'))
		if self.pcp_type != 'normal':
			self.write({'state': 'submit'})
			self.write({'state': 'approve'})
		else:
			self.write({'state': 'submit'})

	def approve(self):
		if len(self.expenses_line_ids) < 1:
			raise ValidationError(_('Can not approve if there is no expense.'))
		self.write({'state': 'approve'})

	def post(self):
		if len(self.expenses_line_ids) < 1:
			raise ValidationError(_('Can not post if there is no expense.'))

		line_ids = []
		amount_credit = 0
		for rec in self.expenses_line_ids:

			tax_results = rec.tax_ids.compute_all(
				price_unit=rec.price_unit,
				currency=rec.company_currency_id,
				quantity=rec.quantity,
				product=False,
				# partner=rec.sheet_id.employee_id,
				is_refund=False,
			)
			base_tags = []
			if rec.tax_ids and 'base_tags' in tax_results:
				base_tags = tax_results.get('base_tags',[])
			line_ids.append((0, 0, {
				'name': rec.name,
				'analytic_distribution': rec.analytic_distribution,
				'account_id': rec.account_id.id,
				'operating_unit_id': rec.operating_unit_id.id,
				'vehicle_id': rec.vehicle_id.id if rec.vehicle_id else False,
				'partner_id': rec.vendor_id.id if rec.vendor_id else False,
				'employee_id': rec.employee_id.id if rec.employee_id else False,
				'customer_account': rec.customer_account.id if rec.customer_account else False,
				'debit': rec.sub_total,
				'customer_code': rec.customer_code,
				'contract_type': rec.contract_type,
				'employee_code': rec.employee_code,
				'tax_ids': rec.tax_ids.ids,
				'tax_tag_ids': [(6,0,base_tags)] if base_tags else False,
			}))
			amount_credit += rec.sub_total
			for tax_line in tax_results['taxes']:
				if not tax_line['amount']:
					continue
				inside_tags = []
				if rec.tax_ids and 'tag_ids' in tax_line:
					inside_tags = tax_line.get('tag_ids',[])
				tax = self.env['account.tax'].browse(tax_line['id'])
				repartition_lines = tax.invoice_repartition_line_ids.filtered(lambda r: r.repartition_type == 'tax')
				for repartition in repartition_lines:
					if not repartition.account_id:
						continue
					line_ids.append((0, 0, {
						'name': tax.name,
						'account_id': repartition.account_id.id,
						'analytic_distribution': rec.analytic_distribution,
						'operating_unit_id': rec.operating_unit_id.id,
						'vehicle_id': rec.vehicle_id.id,
						'partner_id': rec.vendor_id.id or False,
						'employee_id': rec.employee_id.id or False,
						'customer_account': rec.customer_account.id or False,
						'customer_code': rec.customer_code,
						'contract_type': rec.contract_type,
						'employee_code': rec.employee_code,
						'debit': abs(tax_line['amount']) if tax_line['amount'] > 0 else 0.0,
						'credit': abs(tax_line['amount']) if tax_line['amount'] < 0 else 0.0,
						'tax_line_id': tax.id,
						'tax_repartition_line_id': repartition.id,
						'tax_tag_ids': [(6,0,inside_tags)] if inside_tags else False,
					}))
					amount_credit += tax_line['amount']
		
		line_ids.append((0, 0, {
			'analytic_distribution': rec.analytic_distribution,
			'account_id': self.account_id.id,
			'credit': amount_credit,
			'partner_id': rec.vendor_id.id if rec.vendor_id else False,
			'employee_id': rec.employee_id.id if rec.employee_id else False,
			'customer_account': rec.customer_account.id if rec.customer_account else False,
			'customer_code': rec.customer_code,
			'employee_code': rec.employee_code,
			'contract_type': rec.contract_type,
		}))

		jv = self.env['account.move'].create({
			# 'partner_id': self.employee_id.id,
			'move_type': 'entry',
			'ref': self.name,
			'journal_id': self.employee_journal_id.id,
			'operating_unit_id': self.expenses_line_ids.filtered(lambda m: m.operating_unit_id)[0].operating_unit_id.id if self.expenses_line_ids.filtered(lambda m: m.operating_unit_id) else False,
			'date': fields.Datetime.now(),
			'petty_id': self.id,
			'line_ids': line_ids
		})
		self.move_id = jv.id
		self.write({'state': 'post'})

	def done(self):
		if len(self.expenses_line_ids) < 1:
			raise ValidationError(_('Can not done if there is no expense.'))
		self.write({'state': 'done'})

	def cancel(self):
		for rec in self:
			if rec.move_id and rec.move_id.state != 'cancel':
				rec.move_id.button_cancel()
		self.write({'state': 'cancel'})

	def draft(self):
		self.write({'state': 'draft'})

class ExpenseLines(models.Model):
	_name = "expense.lines"
	_inherit = ["analytic.mixin", 'mail.thread']
	_description = "Expense Lines"

	@api.depends('category_id', 'company_id')
	def _compute_account_id(self):
		property_field = self.env['product.category']._fields['property_account_expense_categ_id']
		for _expense in self:
			expense = _expense.with_company(_expense.company_id)
			if not expense.category_id:
				expense.account_id = property_field.get_company_dependent_fallback(self.env['product.category'])
				continue
			account = expense.category_id.property_account_expense_categ_id
			if account:
				expense.account_id = account.id

	sheet_id = fields.Many2one('petty.cash.purchase')
	vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle')
	company_currency_id = fields.Many2one(
		comodel_name='res.currency',
		related='company_id.currency_id',
		string="Report Company Currency"
	)

	date = fields.Date(string="Expense Date", default=fields.Date.context_today)

	category_id = fields.Many2one(
		comodel_name='product.category',
		string="Category",
		tracking=True,
		ondelete='restrict',
	)

	operating_unit_id = fields.Many2one(
		check_company=True,
		comodel_name="operating.unit",
		help="Operating Unit that will be used in payments, "
			 "when this journal is used.",
	)

	name = fields.Char(
		string="Description",
		store=True, readonly=False,
		required=True,
		copy=True,
	)

	description = fields.Text(string="Reference")

	account_id = fields.Many2one(
		comodel_name='account.account',
		string="Account",
		compute='_compute_account_id', precompute=True, store=True, readonly=False,
		check_company=True,
		domain="[('account_type', 'not in', ('asset_receivable', 'liability_payable', 'asset_cash', 'liability_credit_card'))]",
		help="An expense account is expected",
	)
	company_id = fields.Many2one(
		comodel_name='res.company',
		string="Company",
		required=True,
		readonly=True,
		default=lambda self: self.env.company,
	)
	
	price_unit = fields.Float(
		string="Unit Price",
		copy=True,
		store=True,
		readonly=False,
		digits='Product Price',
	)

	quantity = fields.Float(required=True, digits='Product Unit of Measure', default=1)
	
	tax_ids = fields.Many2many(
		comodel_name='account.tax',
		relation='petty_expense_tax',
		column1='petty_expense_id',
		column2='tax_id',
		string="Included taxes",
		store=True, readonly=False,
		domain="[('type_tax_use', '=', 'purchase')]",
		check_company=True,
		help="Both price-included and price-excluded taxes will behave as price-included taxes for expenses.",
	)

	sub_total = fields.Monetary(
		string="Sub Total",
		currency_field='company_currency_id',
		compute='_compute_amount',
		store=True,
		tracking=True,
	)
	
	tax_amount = fields.Monetary(
		string="Tax Total",
		currency_field='company_currency_id',
		compute='_compute_amount',
		store=True,
		tracking=True,
	)
	
	total_amount = fields.Monetary(
		string="Total",
		currency_field='company_currency_id',
		compute='_compute_amount',
		tracking=True,
	)

	vendor_vat = fields.Char(string='Vendor Vat', store=True)
	vendor_id = fields.Many2one('res.partner', string='Vendor', store=True, tracking=True)
	employee_id = fields.Many2one('hr.employee', string='Employee', store=True, tracking=True)
	employee_code = fields.Char(string="Employee Code", tracking=True)
	customer_code = fields.Char(string='Vendor Code', store=True)
	customer_account_domain = fields.Char(compute="_compute_customer_account_domain", readonly=True, store=False)
	customer_account = fields.Many2one('partner.subscription', string='Vendor Account', store=True)
	contract_type = fields.Char("Contract Type", tracking=True)

	@api.depends('vendor_id')
	def _compute_customer_account_domain(self):
		for rec in self:
			if rec.vendor_id:
				rec.customer_account_domain = json.dumps([('id', 'in', rec.vendor_id.subscription_id.ids)])
			else:
				rec.customer_account_domain = json.dumps(['id', 'in', []])

	@api.onchange('vendor_id')
	def _get_partner_info(self):
		for rec in self:
			rec.customer_code = rec.vendor_id.customer_code if rec.vendor_id else ''
			rec.vendor_vat = rec.vendor_id.vat if rec.vendor_id else ''
			rec.customer_account = False

	@api.onchange('customer_code')
	def _get_customer_code_info(self):
		for rec in self:
			if rec.customer_code:
				partner = self.env['res.partner'].search([("customer_code", "=", rec.customer_code)], limit=1)
				rec.vendor_id = partner.id if partner else False
				rec.vendor_vat = partner.vat if partner else False
				rec.customer_account = False

	@api.onchange('employee_id')
	def get_employee_code(self):
		for rec in self:
			rec.employee_code = rec.employee_id.employee_code if rec.employee_id else ''

	@api.onchange('customer_account')
	def _get_customer_account_info(self):
		for rec in self:
			rec.contract_type = rec.customer_account.contract_type if rec.customer_account else ''

	@api.model_create_multi
	def create(self, vals_list):
		moves = super().create(vals_list)
		for line in moves:
			line.get_employee_code()
		return moves

	def write(self, vals):
		res = super().write(vals)
		if not self:
			return res
		for line in self:
			if 'employee_id' in vals:
				line.get_employee_code()
		return res

	def _prepare_base_line_for_taxes_computation(self):
		self.ensure_one()
		return self.env['account.tax']._prepare_base_line_for_taxes_computation(
			self,
			tax_ids=self.tax_ids,
			quantity=self.quantity,
			# partner_id=self.sheet_id.employee_id,
			currency_id=self.sheet_id.company_currency_id
		)

	@api.depends('quantity', 'price_unit', 'tax_ids')
	def _compute_amount(self):
		for line in self:
			base_line = line._prepare_base_line_for_taxes_computation()
			self.env['account.tax']._add_tax_details_in_base_line(base_line, line.company_id)
			line.sub_total = base_line['tax_details']['raw_total_excluded_currency']
			line.total_amount = base_line['tax_details']['raw_total_included_currency']
			line.tax_amount = line.total_amount - line.sub_total

class AccountMove(models.Model):
	_inherit = 'account.move'

	petty_id = fields.Many2one('petty.cash.purchase')