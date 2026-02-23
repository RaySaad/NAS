from odoo import models, fields, api
from odoo.tools.date_utils import start_of
from dateutil.relativedelta import relativedelta


class AccountPaymentExt(models.Model):
    _inherit = "account.payment"

    is_loan_payment = fields.Boolean()
    loan_request_id = fields.Many2one('hr.salary.attachment.request', ondelete='restrict')
    employee_id = fields.Many2one(related='loan_request_id.employee_id', string='Employee', store=True)

    @api.model_create_multi
    def create(self, vals):
        payments = super(AccountPaymentExt, self).create(vals)
        for payment in payments:
            if payment.is_loan_payment:
                payment.loan_request_id.employee_payment_id = payment.id
        return payments

    def action_post(self):
        for rec in self:
            if rec.is_loan_payment:
                day_number = rec.date.day
                if day_number <= 20:
                    rec.loan_request_id.date_start = start_of(fields.Date.today(), 'month')
                if day_number > 20:
                    rec.loan_request_id.date_start = start_of(fields.Date.today(), 'month') + relativedelta(months=1)
                rec.loan_request_id.action_confirm()
        return super().action_post()
    
    def action_validate(self):
        res = super().action_validate()
        
        for payment in self:
            if payment.invoice_ids and payment.state == 'paid':
                payment._update_salary_attachment_lines()
        
        return res
    
    def action_cancel(self):
        for payment in self:
            if payment.invoice_ids:
                payment._reset_salary_attachment_lines()
        return super().action_cancel()
    
    def action_draft(self):
        for payment in self:
            if payment.invoice_ids:
                payment._reset_salary_attachment_lines()
        return super().action_draft()
    
    def _update_salary_attachment_lines(self):
        """Update salary attachment lines to paid when payslip payment is validated"""
        self.ensure_one()
        
        if not self.invoice_ids:
            return
        
        # Get payslips from reconciled moves
        payslips = self.env['hr.payslip'].search([('move_id', 'in', self.invoice_ids.ids)])
        
        # Update salary attachment lines for these payslips
        for payslip in payslips:
            attachment_lines = self.env['hr.salary.attachment.line'].search([
                ('payslip_id', '=', payslip.id),
                ('state', '=', 'draft')
            ])
            if attachment_lines:
                attachment_lines.write({'state': 'paid'})
    
    def _reset_salary_attachment_lines(self):
        """Reset salary attachment lines to draft when payment is cancelled or reset to draft"""
        self.ensure_one()
        
        if not self.invoice_ids:
            return
        
        # Get payslips from reconciled moves
        payslips = self.env['hr.payslip'].search([('move_id', 'in', self.invoice_ids.ids)])
        
        # Reset salary attachment lines for these payslips
        for payslip in payslips:
            attachment_lines = self.env['hr.salary.attachment.line'].search([
                ('payslip_id', '=', payslip.id),
                ('state', '=', 'paid')
            ])
            if attachment_lines:
                attachment_lines.write({'state': 'draft'})
