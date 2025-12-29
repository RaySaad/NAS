# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import json

class ExpenseDetailsLine(models.Model):
    _name = 'expense.detail.line'
    _inherit = "analytic.mixin"
    _description = 'Model for Expense Lines'

    expense_transaction_id = fields.Many2one("account.expense.transaction",
                                             string="Expense Transaction",
                                             ondelete='cascade')
    expense_type_id = fields.Many2one("account.expense.type",
                                      string="Expense Type",
                                      domain=[('state', '=', 'confirmed')],
                                      )
    description = fields.Char(required=True)
    prepaid_expense_account_id = fields.Many2one("account.account", string="Prepaid/Accrual Expense account",
                                                 domain="[('account_type', '=', 'expense'),('company_ids','in',[company_id])]",
                                                 required=True)
    expense_account_id = fields.Many2one("account.account", string="Expense account",
                                         domain="[('account_type', '=', 'expense'),('company_ids','in',[company_id])]",
                                         required=True)
    # analytic_account_id = fields.Many2one("account.analytic.account", string="Analytic Account")
    # analytic_distribution = fields.Json()
    #todo: this model depriciated in 18
    # analytic_tag_ids = fields.Many2many('account.analytic.tag', 'expense_tag_rel', 'expense_line_id',
    #                                     'tag_id', string='Analytic Tags')
    start_date = fields.Date("Start Date", required=True)
    end_date = fields.Date("End Date", required=True)
    total_days = fields.Integer(compute='_compute_total_days', string='Total Days', store=True)
    quantity = fields.Float("Quantity", required=True)
    price_unit = fields.Float("Amount", required=True)
    price_total = fields.Float("Total", compute='_compute_price_total', store=True)
    company_id = fields.Many2one(string="Company", related='expense_transaction_id.company_id', store=True,
                                 readonly=True)
    employee_id = fields.Many2one('hr.employee', domain="[('company_id', '=', company_id)]")

    _sql_constraints = [
        ('expense_date_greater', 'check(end_date >= start_date)',
         'Error ! Ending Date cannot be set before Start Date.')
    ]

    @api.model
    def default_get(self, fields):
        res = super(ExpenseDetailsLine, self).default_get(fields)
        if 'reference' in self._context:
            res.update({
                'description': self._context.get('reference'),
            })
        if 'company_id' in self._context:
            res.update({
                'company_id': self._context.get('company_id')
            })
        return res

    @api.onchange('expense_type_id')
    def onchange_expense_type(self):
        for rec in self:
            if rec.expense_type_id:
                rec.prepaid_expense_account_id = rec.expense_type_id.prepaid_expense_account_id.id
                rec.expense_account_id = rec.expense_type_id.expense_account_id.id
            else:
                rec.prepaid_expense_account_id = False
                rec.expense_account_id = False

    @api.depends('start_date', 'end_date')
    def _compute_total_days(self):
        for expense_line in self:
            if expense_line.start_date and expense_line.end_date:
                delta = expense_line.end_date - expense_line.start_date
                expense_line.total_days = delta.days + 1

    @api.depends('quantity', 'price_unit')
    def _compute_price_total(self):
        for expense_line in self:
            expense_line.price_total = expense_line.quantity * expense_line.price_unit

    operating_unit_id = fields.Many2one(
        check_company=True,
        comodel_name="operating.unit",
        help="Operating Unit that will be used in payments, "
             "when this journal is used.",
    )
    
    partner_id = fields.Many2one('res.partner', string='Customer', store=True, tracking=True)
    customer_code = fields.Char(string='Customer Code', store=True)
    customer_account_domain = fields.Char(compute="_compute_customer_account_domain", readonly=True, store=False)
    customer_account = fields.Many2one('partner.subscription', string='Customer Contract', store=True)
    contract_type = fields.Char("Contract Type", tracking=True)

    @api.depends('partner_id')
    def _compute_customer_account_domain(self):
        for rec in self:
            if rec.partner_id:
                rec.customer_account_domain = json.dumps([('id', 'in', rec.partner_id.subscription_id.ids)])
            else:
                rec.customer_account_domain = json.dumps(['id', 'in', []])

    @api.onchange('partner_id')
    def _get_partner_info(self):
        for rec in self:
            rec.customer_code = rec.partner_id.customer_code if rec.partner_id else ''
            rec.customer_account = False

    @api.onchange('customer_code')
    def _get_customer_code_info(self):
        for rec in self:
            if rec.customer_code:
                partner = self.env['res.partner'].search([("customer_code", "=", rec.customer_code)], limit=1)
                rec.partner_id = partner.id if partner else False
                rec.customer_account = False

    @api.onchange('customer_account')
    def _get_customer_account_info(self):
        for rec in self:
            rec.contract_type = rec.customer_account.contract_type if rec.customer_account else ''

    def create_amortization_line(self, start_date, end_date, accumulated_amortization, remaining_value):
        # Period Days
        delta = end_date - start_date
        period_days = delta.days + 1

        # Amortization Amount
        amount_day = self.price_total / self.total_days
        amortization_amount = amount_day * period_days

        # Accumulated Amortization
        accumulated_amortization = accumulated_amortization + amortization_amount
        remaining_value = remaining_value - amortization_amount

        vals = {
            'expense_transaction_id': self.expense_transaction_id.id,
            'expense_detail_line_id': self.id,
            'start_date': start_date,
            'end_date': end_date,
            'prepaid_expense_account_id': self.prepaid_expense_account_id.id,
            'expense_account_id': self.expense_account_id.id,
            'total_days': self.total_days,
            'period_days': period_days,
            'amortization_amount': amortization_amount,
            'amortization_accumulated': accumulated_amortization,
            'remaining_value': remaining_value,
            'operating_unit_id': self.operating_unit_id.id,
            'partner_id': self.partner_id.id,
            'customer_code': self.customer_code,
            'customer_account_domain': self.customer_account_domain,
            'customer_account': self.customer_account.id,
            'contract_type': self.contract_type,
        }
        self.env['amortization.board.line'].create(vals)
        return accumulated_amortization, remaining_value
