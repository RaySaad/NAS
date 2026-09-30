# -*- coding: utf-8 -*-

import logging
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
import json

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
	_inherit = ('account.move')

	@api.depends('partner_id')
	def _compute_customer_account_domain(self):
		for rec in self:
			if rec.partner_id:
				rec.customer_account_domain = json.dumps([('id', 'in', rec.partner_id.subscription_id.ids)])
			else:
				rec.customer_account_domain = json.dumps([('id', 'in', [])])

	customer_code = fields.Char(string='Customer Code', tracking=True)
	customer_account_domain = fields.Char(compute="_compute_customer_account_domain", readonly=True, store=False)
	customer_account = fields.Many2one('partner.subscription',string='Customer Contract', tracking=True)
	project_group_id = fields.Char(string='Project Group ID', tracking=True)
	invoice_project_id = fields.Char(string='Project ID', tracking=True)
	crm_number = fields.Char("CRM Number")
	journal_id = fields.Many2one(
		'account.journal',
		string='Journal',
		compute='_compute_journal_id', inverse='_inverse_journal_id', store=True, readonly=False, precompute=True,
		required=True,
		check_company=True,
        domain=[]
	)

	jv_type = fields.Selection(
		[
			('invoice', 'Invoice'),
			('multi-invoice', 'MultiInvoice'),
			('multi-payment', 'MultiPayment'),
			('invoice_refund', 'Invoice Refund'),
			('payment', 'Payment'),
			('clearance', 'Clearance'),
			('insurance_payment', 'Insurance Payment'),
			('cost_invoice', 'Cost Invoice'),
			('payroll', 'Payroll')
		],
		string="CRM JV Type",
	)

	ref_no = fields.Char("Ref No", compute="_compute_ref")

	@api.depends('crm_number')
	def _compute_ref(self):
		for rec in self:
			rec.ref_no = f"Journal Document {rec.crm_number}" if rec.crm_number else ''

	@api.onchange('partner_id')
	def _get_partner_info(self):
		for rec in self:
			if rec.partner_id:
				partner_id = rec.partner_id
				rec.customer_code = partner_id.customer_code
				rec.project_group_id = partner_id.project_group_id
				rec.invoice_project_id = partner_id.invoice_project_id
				rec.customer_account = False

	@api.onchange('customer_code')
	def _get_customer_code_info(self):
		for rec in self:
			if rec.customer_code:
				partner_id = self.env['res.partner'].search([("customer_code", "=", rec.customer_code)])
				if partner_id:
					rec.partner_id = partner_id.id
					rec.project_group_id = partner_id.project_group_id
					rec.invoice_project_id = partner_id.invoice_project_id

# added customer_code and customer_account for whatever we select in account.move will also store in account.move.line

class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	@api.depends('partner_id')
	def _compute_customer_account_domain(self):
		for rec in self:
			if rec.partner_id:
				rec.customer_account_domain = json.dumps([('id', 'in', rec.partner_id.subscription_id.ids)])
			else:
				rec.customer_account_domain = json.dumps([('id', 'in', [])])

	customer_code = fields.Char(string='Customer Code', store=True)
	customer_account_domain = fields.Char(compute="_compute_customer_account_domain", readonly=True, store=False)
	customer_account = fields.Many2one('partner.subscription', string='Customer Contract', store=True)
	employee_id = fields.Many2one('hr.employee', string='Employee', store=True, tracking=True)
	employee_code = fields.Char(string="Employee Code", tracking=True)
	contract_type = fields.Char("Contract Type", tracking=True)

	project_group_id = fields.Char(string='Project Group ID', tracking=True,related='move_id.project_group_id')
	invoice_project_id = fields.Char(string='Project ID', tracking=True,related='move_id.invoice_project_id')
	crm_number = fields.Char("CRM Number",related='move_id.crm_number')


	@api.onchange('partner_id')
	def _get_partner_info(self):
		for rec in self:
			rec.customer_code = rec.partner_id.customer_code if rec.partner_id else ''
			rec.customer_account = False

	@api.onchange('customer_account')
	def _get_customer_account_info(self):
		for rec in self:
			rec.contract_type = rec.customer_account.contract_type if rec.customer_account else ''

	@api.onchange('customer_code')
	def _get_customer_code_info(self):
		for rec in self:
			if rec.customer_code:
				partner = self.env['res.partner'].search([("customer_code", "=", rec.customer_code)], limit=1)
				rec.partner_id = partner.id if partner else False

	@api.onchange('employee_id')
	def get_employee_code(self):
		for rec in self:
			rec.employee_code = rec.employee_id.employee_code if rec.employee_id else ''

	@api.model
	def _get_tax_vals_from_tag(self, tag_id, debit, credit):
		"""Return the line values linking a tax tag to its tax, stored the way Odoo stores taxed lines.

		A line with a VAT tag but no tax is counted by the VAT Filing Report (tag based)
		but skipped by the Generic tax report and the tax closing entry (tax based).
		The tag is replaced by the one of the matching invoice/refund repartition line so
		that the computed tax_tag_invert keeps the VAT Filing Report amount unchanged.
		Falls back to the bare tag when it does not belong to exactly one tax.
		"""
		fallback = {'tax_tag_ids': [(6, 0, [tag_id])]}
		repartition_lines = self.env['account.tax.repartition.line'].sudo().with_context(active_test=False).search([
			('tag_ids', 'in', [tag_id]),
		])
		tax = repartition_lines.tax_id
		repartition_type = set(repartition_lines.mapped('repartition_type'))
		if len(tax) != 1 or len(repartition_type) != 1 or tax.type_tax_use not in ('sale', 'purchase'):
			return fallback
		repartition_type = repartition_type.pop()

		# Same rule as account.move.line._compute_is_refund for journal entries
		if tax.type_tax_use == 'sale':
			is_refund = not float(credit or 0)
		else:
			is_refund = not float(debit or 0)
		document_lines = tax.refund_repartition_line_ids if is_refund else tax.invoice_repartition_line_ids
		repartition_line = document_lines.filtered(lambda rl: rl.repartition_type == repartition_type)
		if len(repartition_line) != 1:
			return fallback

		vals = {'tax_tag_ids': [(6, 0, repartition_line.tag_ids.ids)]}
		if repartition_type == 'tax':
			vals['tax_repartition_line_id'] = repartition_line.id
		else:
			vals['tax_ids'] = [(6, 0, tax.ids)]
		return vals

	@api.model_create_multi
	def create(self, vals_list):
		moves = super().create(vals_list)
		for line in moves:
			move = line.move_id
			if move:
				if not line.customer_code:
					line.customer_code = move.customer_code
				if not line.customer_account:
					line.customer_account = move.customer_account.id
					line.contract_type = move.customer_account.contract_type if move.customer_account else ''
			line.get_employee_code()
		return moves

	def write(self, vals):
		res = super().write(vals)
		if not self:
			return res
		for line in self:
			move = line.move_id
			if move:
				if 'partner_id' in vals:
					if not line.partner_id and move.partner_id:
						line.partner_id = move.partner_id.id
						line.customer_code = move.partner_id.customer_code or move.customer_code
					if not line.customer_account:
						line.customer_account = move.customer_account.id if move.customer_account else False
						line.contract_type = move.customer_account.contract_type if move.customer_account else ''
			if 'employee_id' in vals:
				line.get_employee_code()
		return res
