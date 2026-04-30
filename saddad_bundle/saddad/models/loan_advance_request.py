# -*- coding: utf-8 -*-
from odoo import models, fields


class LoanAdvanceRequestExt(models.Model):
    _inherit = 'loan.advance.request'

    morror_id = fields.Many2one('morror')
    muqeem_expense_id = fields.Many2one('document.renew.expense')

    def action_open_morror(self):
        return {
            'name': 'Morror',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'morror',
            'domain': [('id', '=', self.morror_id.id)],

        }

    def action_open_muqeem_expense(self):
        return {
            'name': 'Muqeem Expense',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'document.renew.expense',
            'domain': [('id', '=', self.muqeem_expense_id.id)],

        }


class LoanAdvanceExt(models.Model):
    _inherit = 'hr_loans.loan_advance'

    is_traffic_violation = fields.Boolean(string='Traffic Violation Loan?', default=False)
