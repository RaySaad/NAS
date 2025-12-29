# -*- coding: utf-8 -*-

from datetime import datetime
from odoo import api, fields, models, _
from odoo.tools.date_utils import start_of, end_of, add, date_range


class ExpenseTransaction(models.Model):
    _name = "account.expense.transaction"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'expense_nature'
    _description = "Account Expense Transaction"

    date = fields.Date(required=True)
    state = fields.Selection([('draft', 'Draft'), ('reviewed', 'Reviewed'),
                              ('confirmed', 'Confirmed'), ('final_approval', 'Final Approval'),
                              ('full_amortization', 'Full Amortization')],
                             string='Status', required=True,
                             copy=False, default='draft')
    expense_nature = fields.Selection([('prepaid', 'Prepaid'), ('accrual', 'Accrual')],
                                      string='Expense Nature', required=True,
                                      default="accrual")
    amortization_method = fields.Selection([('monthly', 'Monthly'), ('on_time', 'On Time')],
                                           string='Amortization Method', required=True,
                                           )
    reference = fields.Char(required=True)
    move_id = fields.Many2one("account.move", string="Journal Entry",copy=False)
    payment_type = fields.Selection([('bank_cash', 'Bank/Cash'), ('credit', 'Credit')],
                                    string='Payment type')
    payment_journal_id = fields.Many2one("account.journal", string="Payment Method",
                                         domain="[('type', 'in', ['bank', 'cash']),('company_id','=',company_id)]",
                                         )
    bank_account_id = fields.Many2one("account.account", string="Bank/Cash Account",
                                      domain="[('account_type', '=', 'asset_cash'),('company_ids','in',[company_id])]",

                                      )
    # When payment_type is credit
    journal_id = fields.Many2one("account.journal", string="Amortization Journal",
                                 domain="[('type', 'in', ['purchase', 'general']),('company_id','=',company_id)]",
                                  required=True)
    vendor_id = fields.Many2one("res.partner", string="Vendor")
    invoice_id = fields.Many2one("account.move", string="Invoice")
    expense_detail_ids = fields.One2many('expense.detail.line',
                                         'expense_transaction_id',
                                         string="Expense Detail Lines",
                                         copy=True)
    amortization_board_ids = fields.One2many('amortization.board.line',
                                             'expense_transaction_id',
                                             string="Amortization Board Lines")
    entry_count = fields.Integer(compute='_entry_count', string='# Journal Entries')
    type_jv = fields.Selection([('all_line', 'JV for all line'), ('each_line', 'JV for each line')],
                               default='each_line')
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)

    def temp_reset(self):
        exception=[]
        allotted_move_mesc = []
        total_move_ids = []
        transactions = self.sudo().search([('state', '=', 'final_approval')])
        for transaction in transactions:
            if transaction.amortization_board_ids:
                for line in transaction.amortization_board_ids:
                    if not line.move_id:
                        move = self.env["account.move"].sudo().search([("partner_id", "=", transaction.vendor_id.id),
                                                                        ("date", "=", line.start_date),
                                                                        ("state", "=", 'posted'),
                                                                        ("ref", "=", transaction.reference)])

                        if move:
                            move = move.filtered(
                                    lambda record: record.journal_id.name in  ['Miscellaneous Operations',
                                                                              "AAC-Miscellaneous Operations",
                                                                              "DCC-Miscellaneous Operations",
                                                                              "DG-Miscellaneous Operations",
                                                                              "DPC-Miscellaneous Operations"])
                            if move:
                                move = move.filtered(
                                    lambda record: sum(record.line_ids.mapped('debit')) == round(line.amortization_amount, 2))
                                ref = move
                                if move:
                                    if len(move) > 1:
                                        if transaction.id not in exception:
                                            exception.append(transaction.id)
                                        for mv in move:
                                            if mv.id in allotted_move_mesc:
                                                move = move.filtered(lambda r: r.id != mv.id)
                                        if move:
                                            move = move[0]
                                            line.move_id = move.id
                                            allotted_move_mesc.append(move.id)
                                            total_move_ids.append(move.id)
                                        continue
                                    if move.id not in total_move_ids:
                                        total_move_ids.append(move.id)
                                        line.move_id = move.id
                    else:
                        allotted_move_mesc.append(line.move_id.id)

    @api.depends('amortization_board_ids.move_id')
    def _entry_count(self):
        for expense_transaction in self:
            res = self.env['amortization.board.line'].search(
                [('expense_transaction_id', '=', expense_transaction.id), ('move_id', '!=', False)])
            expense_transaction.entry_count = res and len(set(res.mapped('move_id.id'))) or 0

    def open_entries(self):
        move_ids = []
        for expense_transaction in self:
            for amortization_board_line in expense_transaction.amortization_board_ids:
                if amortization_board_line.move_id:
                    move_ids.append(amortization_board_line.move_id.id)
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', move_ids)],
        }

    @api.onchange('payment_type')
    def onchange_payment_type(self):
        for rec in self:
            if rec.payment_type == 'bank_cash':
                rec.vendor_id = False
                rec.invoice_id = False
            elif rec.payment_type == 'credit':
                rec.payment_journal_id = False
                rec.bank_account_id = False
            else:
                rec.vendor_id = False
                rec.invoice_id = False
                rec.payment_journal_id = False
                rec.bank_account_id = False

    @api.onchange('expense_nature')
    def onchange_expense_nature(self):
        for rec in self:
            if rec.expense_nature == 'prepaid':
                return {'domain': {'journal_id': [('type', 'in', ['purchase', 'general']),
                                                  ('company_id', '=', rec.company_id.id)]}}
            if rec.expense_nature == 'accrual':
                return {'domain': {'journal_id': [('type', 'in', ['general']),
                                                  ('company_id', '=', rec.company_id.id)]}}

    @api.onchange('payment_journal_id')
    def onchange_payment_journal(self):
        for rec in self:
            if rec.payment_journal_id and rec.payment_journal_id.default_account_id:
                rec.bank_account_id = rec.payment_journal_id.default_account_id.id
            else:
                rec.bank_account_id = False

    def action_review(self):
        for expense_rec in self:
            expense_rec.write({
                'state': 'reviewed'
            })

    def action_confirm(self):
        for expense_rec in self:
            expense_rec.write({
                'state': 'confirmed'
            })

    def get_date_range(self, start_date, end_date):
        min_time = datetime.min.time()
        date_list = []
        single_month = False

        # Calculate the last day of month of start date
        month_end = end_of(start_date, 'month')
        if start_date != end_date and end_date > month_end:
            date_list.append((start_date, month_end))
            next_month_start = add(month_end, days=1)
            end_month_start = start_of(end_date, 'month')
            if end_month_start == end_date:
                previous_month_end = end_month_start
            elif next_month_start > add(end_month_start, days=-1):
                previous_month_end = end_month_start
            else:
                previous_month_end = add(end_month_start, days=-1)
        else:
            date_list.append((start_date, end_date))
            next_month_start = start_date
            end_month_start = start_of(end_date, 'month')
            previous_month_end = end_date
            single_month = True

        if not single_month and next_month_start != previous_month_end:
            # Loop over "date_range" odoo library function
            for start_day_month in date_range(datetime.combine(next_month_start, min_time),
                                              datetime.combine(previous_month_end, min_time)):
                end_day_month = end_of(start_day_month.date(), 'month')
                if end_day_month <= end_date:
                    date_list.append((start_day_month.date(), end_day_month))

        if end_month_start > start_date and end_month_start != end_date:
            date_list.append((end_month_start, end_date))
        elif end_month_start > start_date and end_month_start == end_date:
            date_list.append((end_date, end_date))
        return date_list

    def create_expense_journal_entry(self):
        iml = []
        total_amount = 0
        if self.type_jv == 'all_line':
            for expense_detail_rec in self.expense_detail_ids:
                iml.append((0, 0, {
                    'name': expense_detail_rec.description,
                    'debit': expense_detail_rec.price_total,
                    'account_id': expense_detail_rec.prepaid_expense_account_id.id,
                    'analytic_distribution': expense_detail_rec.analytic_distribution,
                    'operating_unit_id': expense_detail_rec.operating_unit_id.id,
                    'partner_id': expense_detail_rec.partner_id.id,
                    'customer_code': expense_detail_rec.customer_code,
                    'customer_account_domain': expense_detail_rec.customer_account_domain,
                    'customer_account': expense_detail_rec.customer_account.id,
                    'contract_type': expense_detail_rec.contract_type,
                }))
                total_amount += expense_detail_rec.price_total
            iml.append((0, 0, {
                'name': self.reference,
                'credit': total_amount,
                'account_id': self.bank_account_id.id or self.journal_id.default_account_id.id,
                'analytic_distribution': self.expense_detail_ids and self.expense_detail_ids[
                    0].analytic_distribution or False
            }))
            self.move_id = self.env['account.move'].create({
                'journal_id': self.payment_journal_id.id,
                'line_ids': iml,
                'date': self.date,
                'ref': self.reference,
            })
        if self.type_jv == 'each_line':
            for expense_detail_rec in self.expense_detail_ids:
                iml.append((0, 0, {
                    'name': expense_detail_rec.description,
                    'debit': expense_detail_rec.price_total,
                    'account_id': expense_detail_rec.prepaid_expense_account_id.id,
                    'analytic_distribution': expense_detail_rec.analytic_distribution,
                    'operating_unit_id': expense_detail_rec.operating_unit_id.id,
                    'partner_id': expense_detail_rec.partner_id.id,
                    'customer_code': expense_detail_rec.customer_code,
                    'customer_account_domain': expense_detail_rec.customer_account_domain,
                    'customer_account': expense_detail_rec.customer_account.id,
                    'contract_type': expense_detail_rec.contract_type,
                }))
                iml.append((0, 0, {
                    'name': self.reference,
                    'credit': expense_detail_rec.price_total,
                    'account_id': self.bank_account_id.id or self.journal_id.default_account_id.id,
                    'analytic_distribution': self.expense_detail_ids and self.expense_detail_ids[
                        0].analytic_distribution or False,
                    'operating_unit_id': expense_detail_rec.operating_unit_id.id,
                    'partner_id': expense_detail_rec.partner_id.id,
                    'customer_code': expense_detail_rec.customer_code,
                    'customer_account_domain': expense_detail_rec.customer_account_domain,
                    'customer_account': expense_detail_rec.customer_account.id,
                    'contract_type': expense_detail_rec.contract_type,
                }))
                self.move_id = self.env['account.move'].create({
                    'journal_id': self.payment_journal_id.id,
                    'line_ids': iml,
                    'date': self.date,
                    'ref': self.reference,
                })
        self.move_id.action_post()

    def action_final_approval(self):
        for expense_rec in self:
            # Creating the journal Entry
            if expense_rec.expense_nature == 'prepaid' and expense_rec.payment_type == 'bank_cash':
                expense_rec.create_expense_journal_entry()

            # Creating Amortization Lines
            for expense_detail_rec in expense_rec.expense_detail_ids:
                # Storing start and end dates
                start_date = expense_detail_rec.start_date
                end_date = expense_detail_rec.end_date
                date_list = self.get_date_range(start_date, end_date)
                accumulated_amortization = 0
                remaining_value = expense_detail_rec.price_total
                for date_range in date_list:
                    accumulated_amortization, remaining_value = \
                        expense_detail_rec.create_amortization_line(
                            date_range[0], date_range[1], accumulated_amortization, remaining_value)

            # Setting the state to Final Approval
            expense_rec.write({
                'state': 'final_approval'
            })

    def action_full_amortization(self):
        for expense_rec in self:
            expense_rec.write({
                'state': 'full_amortization'
            })

    def action_draft(self):
        for expense_rec in self:
            expense_rec.write({
                'state': 'draft'
            })

    def post_expense_entries(self):
        expenses = self.sudo().search([('state', '=', 'final_approval')])
        for expense in expenses:
            if expense.amortization_board_ids:
                for line in expense.amortization_board_ids:
                    if not line.move_id and line.end_date <= fields.Date.today():
                        line.post_entry()
