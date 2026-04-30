# -*- coding: utf-8 -*-

from odoo import models, fields,_


class HrPaySlipRunExt(models.Model):
    _inherit = 'hr.payslip.run'

    input_line_ids = fields.One2many(
        'hr.payslip.input', 'payslip_batch_id', string='Payslip Inputs')

    def _compute_reviewed_payslips(self):
        super(HrPaySlipRunExt, self)._compute_reviewed_payslips()
        for payslip in self.slip_ids:
            if payslip.input_line_ids:
                for other_input in payslip.input_line_ids:
                    salary_attachment_request_ids = payslip.salary_attachment_ids.mapped('salary_attachment_request_id')
                    other_input.update({
                        'payslip_batch_id': payslip.payslip_run_id.id,
                        'employee_id': payslip.employee_id.id,
                        'loan_ids': [
                            (6, 0, salary_attachment_request_ids.ids)] if salary_attachment_request_ids else [],
                        'installment_amount': other_input.amount})


    def cancel_payslip_run_action(self):
        if self.slip_ids:
            for slip in self.slip_ids:
                slip.cancel_payslip_run()

        self.write({'state': 'cancel'})
        body = "Document Cancelled"
        self.message_post(body=body, message_type='email')
        return {}


class HrPayslipInputExt(models.Model):
    _inherit = 'hr.payslip.input'

    payslip_batch_id = fields.Many2one('hr.payslip.run', ondelete='set null')
    employee_id = fields.Many2one('hr.employee', ondelete='set null')
    installment_amount = fields.Float(string='Installment Amount')
    loan_ids = fields.Many2many('hr.salary.attachment.request', ondelete='restrict')
