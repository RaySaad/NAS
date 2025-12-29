# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import datetime
from odoo.tools import format_date
from num2words import num2words
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        res = super(AccountMove, self).action_post()
        for expense in self:
            expense_product_line = self.env['account.move.line'].search(
                [('move_id', '=', expense.id), ('expense_nature', '=', 'prepaid')])
            if expense_product_line:
                vals = {
                    'date': fields.Date.today(),
                    'journal_id': expense.journal_id.id,
                    'amortization_method': 'monthly',
                    'reference': expense.number,
                    'payment_type': 'credit',
                    'vendor_id': expense.partner_id.id,
                    'invoice_id': expense.id,
                    'move_id': expense.move_id.id
                }
                transaction_rec = self.env['account.expense.transaction'].create(vals)
                for rec in expense_product_line:
                    transaction_rec.expense_detail_ids.create({
                        'expense_transaction_id': transaction_rec.id,
                        'expense_type_id': rec.expense_type_id.id,
                        'description': rec.name,
                        'prepaid_expense_account_id': rec.expense_type_id.prepaid_expense_account_id.id,
                        'expense_account_id': rec.expense_type_id.expense_account_id.id,
                        'analytic_distribution': rec.analytic_distribution,
                        # 'analytic_tag_ids': rec.analytic_tag_ids and [(6, 0, rec.analytic_tag_ids.ids)],
                        'start_date': rec.start_date,
                        'end_date': rec.end_date,
                        'quantity': rec.quantity,
                        'price_unit': rec.price_unit})
        return res
