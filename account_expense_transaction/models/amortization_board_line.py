# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import json

class AmortizationBoardLine(models.Model):
    _name = 'amortization.board.line'
    _description = 'Model for Amortization Lines'

    expense_transaction_id = fields.Many2one("account.expense.transaction",
                                             string="Expense Transaction",
                                             ondelete='cascade')
    expense_detail_line_id = fields.Many2one("expense.detail.line",
                                             string="Expense Detail Line",
                                             ondelete='cascade')
    start_date = fields.Date("Start Date", required=True)
    end_date = fields.Date("End Date", required=True)
    prepaid_expense_account_id = fields.Many2one("account.account", string="Prepaid/Accrual Expense account",
                                                 domain="[('account_type', '=', 'expense_other'),('company_ids','in',[company_id])]",
                                                 required=True)
    expense_account_id = fields.Many2one("account.account", string="Expense account",
                                         domain="[('account_type', '=', 'expense'),('company_ids','in',[company_id])]",
                                         required=True)
    total_days = fields.Integer("Total Days")
    period_days = fields.Integer("Period Days")
    amortization_amount = fields.Float("Amortization Amount")
    amortization_accumulated = fields.Float("Amortization Accumulated")
    remaining_value = fields.Float("Remaining Value")
    move_id = fields.Many2one("account.move", string="Journal Entry",
                              readonly=False, copy=True)
    company_id = fields.Many2one(string="Company", related='expense_transaction_id.company_id', store=True,
                                 readonly=True)


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

    def post_entry(self, context=False, journal_id=False, group_entry=False):
        if not group_entry:
            for amortization_line in self:
                iml = list()

                iml.append((0, 0, {
                    'name': amortization_line.expense_detail_line_id.description,
                    'credit': amortization_line.amortization_amount,
                    'account_id': amortization_line.prepaid_expense_account_id.id,
                    'partner_id': amortization_line.expense_transaction_id.vendor_id.id,
                    'employee_id': amortization_line.expense_detail_line_id.employee_id.id,
                    'analytic_distribution': amortization_line.expense_detail_line_id.analytic_distribution,
                    'operating_unit_id': amortization_line.operating_unit_id.id,
                    'partner_id': amortization_line.partner_id.id,
                    'customer_code': amortization_line.customer_code,
                    'customer_account_domain': amortization_line.customer_account_domain,
                    'customer_account': amortization_line.customer_account.id,
                    'contract_type': amortization_line.contract_type,
                }))
                iml.append((0, 0, {
                    'name': amortization_line.expense_detail_line_id.description,
                    'debit': amortization_line.amortization_amount,
                    'account_id': amortization_line.expense_account_id.id,
                    'partner_id': amortization_line.expense_transaction_id.vendor_id.id,
                    'employee_id': amortization_line.expense_detail_line_id.employee_id.id,
                    'analytic_distribution': amortization_line.expense_detail_line_id.analytic_distribution,
                    'operating_unit_id': amortization_line.operating_unit_id.id,
                    'partner_id': amortization_line.partner_id.id,
                    'customer_code': amortization_line.customer_code,
                    'customer_account_domain': amortization_line.customer_account_domain,
                    'customer_account': amortization_line.customer_account.id,
                    'contract_type': amortization_line.contract_type,
                    # 'analytic_tag_ids': amortization_line.expense_detail_line_id.analytic_tag_ids and [
                    #     (6, 0, amortization_line.expense_detail_line_id.analytic_tag_ids.ids)],
                }))
                amortization_line.move_id = self.env['account.move'].create({
                    'journal_id': journal_id or amortization_line.expense_transaction_id.journal_id.id,
                    'partner_id': amortization_line.expense_transaction_id.vendor_id.id,
                    'line_ids': iml,
                    'date': amortization_line.start_date,
                    'ref': amortization_line.expense_transaction_id.reference
                })
                amortization_line.move_id.action_post()
                self.env.cr.commit()

            if all(amortization_line.move_id for amortization_line in
                   self[0].expense_transaction_id.amortization_board_ids):
                self[0].expense_transaction_id.action_full_amortization()

        else:  # if Group Entry is Enabled
            expense_detail_line_ids = list(set(self.mapped('expense_detail_line_id')))

            for expense_detail_line_id in expense_detail_line_ids:
                current_lines = self.filtered(lambda r: r.expense_detail_line_id == expense_detail_line_id)
                amortization_amount = sum(current_lines.mapped('amortization_amount'))
                iml = list()
                last_amortization_line = current_lines[0]
                iml.append((0, 0, {
                    'name': last_amortization_line.expense_detail_line_id.description,
                    'credit': amortization_amount,
                    'account_id': last_amortization_line.prepaid_expense_account_id.id,
                    'partner_id': last_amortization_line.expense_transaction_id.vendor_id.id,
                    'analytic_distribution': last_amortization_line.expense_detail_line_id.analytic_distribution,
                    'operating_unit_id': last_amortization_line.operating_unit_id.id,
                    'partner_id': last_amortization_line.partner_id.id,
                    'customer_code': last_amortization_line.customer_code,
                    'customer_account_domain': last_amortization_line.customer_account_domain,
                    'customer_account': last_amortization_line.customer_account.id,
                    'contract_type': last_amortization_line.contract_type,
                    # 'analytic_tag_ids': last_amortization_line.expense_detail_line_id.analytic_tag_ids and [
                    #     (6, 0, last_amortization_line.expense_detail_line_id.analytic_tag_ids.ids)],
                }))
                iml.append((0, 0, {
                    'name': last_amortization_line.expense_detail_line_id.description,
                    'debit': amortization_amount,
                    'account_id': last_amortization_line.expense_account_id.id,
                    'partner_id': last_amortization_line.expense_transaction_id.vendor_id.id,
                    'analytic_distribution': last_amortization_line.expense_detail_line_id.analytic_distribution,
                    'operating_unit_id': last_amortization_line.operating_unit_id.id,
                    'partner_id': last_amortization_line.partner_id.id,
                    'customer_code': last_amortization_line.customer_code,
                    'customer_account_domain': last_amortization_line.customer_account_domain,
                    'customer_account': last_amortization_line.customer_account.id,
                    'contract_type': last_amortization_line.contract_type,
                    # 'analytic_tag_ids': last_amortization_line.expense_detail_line_id.analytic_tag_ids and [
                    #     (6, 0, last_amortization_line.expense_detail_line_id.analytic_tag_ids.ids)],
                }))
                new_move_rec = self.env['account.move'].create({
                    'journal_id': journal_id or last_amortization_line.expense_transaction_id.journal_id.id,
                    'partner_id': last_amortization_line.expense_transaction_id.vendor_id.id,
                    'line_ids': iml,
                    'date': last_amortization_line.start_date,
                    'ref': last_amortization_line.expense_transaction_id.reference
                })
                for current_line in current_lines:
                    current_line.move_id = new_move_rec
                new_move_rec.action_post()
                self.env.cr.commit()

                if all(amortization_line.move_id for amortization_line in
                       last_amortization_line.expense_transaction_id.amortization_board_ids):
                    last_amortization_line.expense_transaction_id.action_full_amortization()

    _sql_constraints = [
        ('amortization_date_greater', 'check(end_date >= start_date)',
         'Error ! Ending Date cannot be set before Start Date.')
    ]
