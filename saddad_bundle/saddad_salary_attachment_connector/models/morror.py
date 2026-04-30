# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import ValidationError


class Morror(models.Model):
    _inherit = 'morror'

    loan_advance_request_id = fields.Many2one('hr.salary.attachment.request')

    def onchange_state(self):
        super().onchange_state()
        if self.morror_line_ids.filtered(lambda l: l.payment_mode == 'own_account'):
            self.create_loan_request()

    def create_loan_request(self):
        if not self.employee_id:
            return
        request_amount = sum(
            self.morror_line_ids.filtered(lambda l: l.payment_mode == 'own_account').mapped('unit_price'))
        if request_amount <= 0:
            return
        self.loan_advance_request_id = self.env['hr.salary.attachment.request'].create({
            'employee_id': self.employee_id.id,
            'company_id': self.employee_id.company_id.id,
            'description': self.serial_number,
            'loan_type_id': self.env['hr.payslip.input.type'].search([('code', '=', 'Morror')]).id or False,
            'date_start': fields.date.today(),
            'total_amount': request_amount,
            'monthly_amount': request_amount,
            'installment_method': 'duration',
            'duration': 1,
            'morror_id': self.id,
            'show_morror_button': True,
        })

    def action_cancel(self):
        if self.loan_advance_request_id:
            if self.loan_advance_request_id.state not in ('draft','cancelled'):
                raise ValidationError(
                    "You can not cancel this record because a loan request related to this is in approval process if you really need to cancel this please cancel the loan request first!")
            self.loan_advance_request_id.unlink()
        self.loan_advance_request_id = False
        super(Morror, self).action_cancel()

    def action_open_employee_loan_request(self):
        return {
            'name': 'Loan Request',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'hr.salary.attachment.request',
            'domain': [('id', '=', self.loan_advance_request_id.id)],
        }
