# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import math
from datetime import timedelta


def validation_message(self, message):
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': 'Validation Error!',
            'message': message,
            'type': 'danger',  # Can be 'success', 'warning', 'danger', 'info'
            'sticky': False,  # Set to True to make it stay until closed by user
        }
    }


class HrSalaryAttachmentExt(models.Model):
    _inherit = 'hr.salary.attachment'


    balance_amount = fields.Monetary(string='Balance Amount', default=0, compute='compute_balance')
    pardon_amount = fields.Monetary(string='Pardon Amount')
    active = fields.Boolean(default=True)
    salary_attachment_request_id = fields.Many2one('hr.salary.attachment.request')
    old_attachment_id = fields.Many2one('hr.salary.attachment')
    current_attachment_id = fields.Many2one('hr.salary.attachment')
    merge_note = fields.Char(string="Merge Note",
                             help="This field would appear on the salary attachments which have been merged to a new salary attachment")
    state = fields.Selection(
        selection_add=[
            ('draft', 'Draft'),
        ],
        ondelete={
            'draft': 'cascade',
        },
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
    )
    deduction_type_code = fields.Char(string='deduction type code')
    attachment_lines = fields.One2many('hr.salary.attachment.line', 'attachment_id', string='Attachment Lines')

    @api.onchange('monthly_amount')
    def validate_monthly_amount(self):
        if self.monthly_amount:
            if any(installment.state == 'paid' for installment in self.attachment_lines):
                raise ValidationError("Can't update the monthly amount if an installment of the loan have been paid")

    @api.depends('paid_amount', 'pardon_amount')
    def compute_balance(self):
        for rec in self:
            if rec.total_amount:
                rec.balance_amount = rec.total_amount - rec.paid_amount
            if rec.pardon_amount:
                rec.balance_amount = rec.balance_amount - rec.pardon_amount
            if not (rec.total_amount and not rec.pardon_amount):
               rec.balance_amount = 0

    def unlink(self):
        res = False
        for rec in self:
            if rec.state == 'draft' and rec.salary_attachment_request_id:
                salary_attachment_request = rec.salary_attachment_request_id
                rec.salary_attachment_request_id.write({
                    'salary_attachment_id': False
                })
                rec.salary_attachment_request_id = False
                res = super(HrSalaryAttachmentExt, rec).unlink()
                salary_attachment_request.unlink()
            elif rec.payslip_ids:
                return validation_message(self,"Can't delete a salary attachment if its attached with a payslip")
            else:
                res = super(HrSalaryAttachmentExt, rec).unlink()
        return res

    def action_done(self):
        # Change all unpaid installments to pardoned
        self.write({
            'pardon_amount': self.pardon_amount+sum(self.attachment_lines.filtered(lambda line: line.state == 'draft').mapped('amount')),
        })
        unpaid_installments = self.attachment_lines.filtered(lambda line: line.state == 'draft')
        unpaid_installments.write({'state': 'pardoned'})
        if self.salary_attachment_request_id and self.salary_attachment_request_id.state != 'completed':
            self.salary_attachment_request_id.write({
                'date_end': fields.Date.today() if fields.Date.today() > self.date_start else self.date_start + timedelta(days=1),
            })
            self.salary_attachment_request_id.action_done()
        res = super(HrSalaryAttachmentExt, self).action_done()
        for rec in self:
            rec.write({
                'date_end': fields.Date.today() if fields.Date.today() > rec.date_start else rec.date_start + timedelta(
                    days=1),
            })

    def action_cancel(self):
        if any(self.payslip_ids.filtered(lambda payslip: payslip.state in ('draft','verify'))):
            return validation_message(self,message="Can't cancel a salary attachment if its attached with a payslip")
        if any(self.attachment_lines.filtered(lambda line: line.state == 'paid')):
            return validation_message(self,message="Can't cancel a salary attachment with paid installments")
        super(HrSalaryAttachmentExt, self).action_cancel()
        if self.salary_attachment_request_id and self.salary_attachment_request_id.state != 'cancelled':
            self.salary_attachment_request_id.action_cancel()
        for rec in self:
            rec.write({
                'date_end': fields.Date.today() if fields.Date.today() > rec.date_start else rec.date_start + timedelta(
                    days=1),
            })

    @api.onchange('other_input_type_id')
    def update_deduction_type_code(self):
        if self.other_input_type_id:
            self.deduction_type_code = self.other_input_type_id.code
        else:
            self.deduction_type_code = self.other_input_type_id.code

    def action_confirm(self):
        if self.salary_attachment_request_id and self.salary_attachment_request_id.state == 'draft':
            self.salary_attachment_request_id.write({'state': 'confirmed'})
        for rec in self:
            other_open_attachments = self.env['hr.salary.attachment'].search(
                [('employee_ids', 'in', rec.employee_ids.ids),
                 ('other_input_type_id.code', '=', rec.other_input_type_id.code),
                 ('state', '=', 'open'), ('date_estimated_end', '>=', rec.date_start)])
            if other_open_attachments:
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Merge Confirmation',
                    'res_model': 'merge.attachment.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'view_id': self.env.ref('salary_attachments_customization.merge_attachment_wizard_form_view').id,
                    "context": {'default_old_attachment_id': other_open_attachments.id,
                                'default_current_attachment_id': rec.id}}
            rec.write({
                'state': 'open',
                'pardon_amount': 0.0
            })
            return True

    def reset_to_draft(self):
        for rec in self:
            rec.attachment_lines.unlink()
            rec.update({
                'state': 'draft',
                'pardon_amount': 0.0
            })
            if rec.salary_attachment_request_id:
                rec.salary_attachment_request_id.write({
                    'state': 'draft'
                })

    def action_open(self):
        super(HrSalaryAttachmentExt, self).action_open()
        self.compute_balance()
        self.write({
            'pardon_amount': 0.0
        })
        if self.salary_attachment_request_id:
            self.salary_attachment_request_id.compute_balance()
            self.salary_attachment_request_id.write({
                'pardon_amount': 0.0,
                'state': 'confirmed',
                'date_end': False,
                'pardon_reason': '',
            })

    def record_payment(self, total_amount):
        for rec in self:
            super(HrSalaryAttachmentExt, rec).record_payment(total_amount)
            if total_amount != rec.monthly_amount and rec.attachment_lines:
                remaining_lines = rec.attachment_lines.filtered(lambda l: l.state == 'draft')
                if remaining_lines and len(remaining_lines) != 0:
                    rec.write({
                        'monthly_amount': rec.balance_amount / len(remaining_lines)
                    })
                    for line in remaining_lines:
                        line.write({
                            'amount': rec.monthly_amount
                        })
            if rec.salary_attachment_request_id:
                rec.salary_attachment_request_id.record_payment(rec.paid_amount)
                if rec.salary_attachment_request_id.monthly_amount != rec.monthly_amount:
                    rec.salary_attachment_request_id.write({
                        'monthly_amount': rec.monthly_amount
                    })

    def update_installment(self):
        pass

    @api.onchange('total_amount')
    def amount_validation(self):
        if self.old_attachment_id and self.old_attachment_id.balance_amount > self.total_amount:
            raise ValidationError(
                "In case of merging a salary attachment the total amount should be greater than or equal to the old attachment's Balance Amount")

    def action_open_salary_attachment_request(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Employee Loan Requests',
            'res_model': 'hr.salary.attachment.request',
            'view_mode': 'form',
            'res_id': self.salary_attachment_request_id.id,
        }

    def generate_installments(self):
        if any(installment.state == 'paid' for installment in self.attachment_lines):
            return validation_message(self,message="Can't compute installments once an installment in a salary attachment have been paid")
        if self.total_amount <= 0:
            return validation_message(self,message='Total Amount Should Be More Than Zero!')

        if self.attachment_lines:
            self.attachment_lines.unlink()
        for count in range(0, math.ceil(self.total_amount / self.monthly_amount)):
            start_date = self.date_start
            # Calculate the new date by adding 'count' months
            installment_date = start_date + relativedelta(months=count)
            self.env['hr.salary.attachment.line'].create({
                'attachment_id': self.id,
                'amount': self.monthly_amount,
                'date': installment_date
            })

    def _update_paid_amount(self):
        """Update paid_amount and balance_amount based on attachment lines"""
        self.ensure_one()
        paid_lines = self.attachment_lines.filtered(lambda l: l.state == 'paid')
        unpaid_lines = self.attachment_lines.filtered(lambda l: l.state == 'draft')
        total_paid = sum(paid_lines.mapped('amount'))
        total_unpaid = sum(unpaid_lines.mapped('amount'))
        self.write({
            'paid_amount': total_paid,
            'balance_amount': total_unpaid
        })
    
    @api.model_create_multi
    def create(self, vals_list):
        res = super(HrSalaryAttachmentExt, self).create(vals_list)
        return res


class HrSalaryAttachmentLine(models.Model):
    _name = 'hr.salary.attachment.line'
    _inherit = ['mail.thread']
    _description = 'Loan Installment Line'
    _rec_name = 'attachment_id'

    attachment_id = fields.Many2one('hr.salary.attachment', string='Attachment', required=True, ondelete='cascade', tracking=True)
    date = fields.Date(string='Date', tracking=True)
    payslip_id = fields.Many2one('hr.payslip', string='Payslip', tracking=True)
    input_line_id = fields.Many2one('hr.payslip.input')
    amount = fields.Float(string='Amount', tracking=True)
    paid_amount = fields.Float(string='Payment Amount')
    employee_ids = fields.Many2many('hr.employee', string='Employee', related='attachment_id.employee_ids', tracking=True)
    state = fields.Selection([
        ('draft', 'Unpaid'),
        ('paid', 'Paid'),
        ('postponed', 'Postponed'),
        ('pardoned', 'Pardoned')
    ], default='draft', tracking=True)
    pardon_reason = fields.Char(string='Pardon Reason')
    postpone_reason = fields.Char(string='Postpone Reason')

    def action_open_postpone_request(self):
        if self.state == 'paid':
            return validation_message(self, message="Can't postpone a paid installment")
        
        # Check if payslip exists for this month and is not in draft state
        payslip = self.env['hr.payslip'].search([
            ('employee_id', 'in', self.attachment_id.employee_ids.ids),
            ('date_from', '=', self.date),
            ('state', '!=', 'draft')
        ])
        
        if payslip:
            return validation_message(self, "Can't postpone because payslip has been generated for this month")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Postpone Request',
            'res_model': 'postpone.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_loan_line_id': self.id}
        }

    def action_open_pardon_request(self):
        if self.state == 'paid':
            return validation_message(self, message="Can't pardon a paid installment")
        
        # Check if payslip exists for this month and is not in draft state
        payslip = self.env['hr.payslip'].search([
            ('employee_id', 'in', self.attachment_id.employee_ids.ids),
            ('date_from', '=', self.date),
            ('state', '!=', 'draft')
        ])
        
        if payslip:
            return validation_message(self, "Can't pardon because payslip has been generated for this month")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pardon Request',
            'res_model': 'pardon.request',
            'view_mode': 'form',
            'target': 'new',
            'view_id': self.env.ref('salary_attachments_customization.view_pardon_request_loan_line_form').id,
            'context': {'default_loan_line_id': self.id}
        }

    def action_open_salary_attachment(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Salary Attachment',
            'res_model': 'hr.salary.attachment',
            'view_mode': 'form',
            'res_id': self.attachment_id.id,
        }

    def action_view_line(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Installment Line',
            'res_model': 'hr.salary.attachment.line',
            'view_mode': 'form',
            'res_id': self.id,
        }
    
    def write(self, vals):
        res = super(HrSalaryAttachmentLine, self).write(vals)

        if 'state' in vals:
            for line in self:
                if line.attachment_id:
                    line.attachment_id._update_paid_amount()

        return res
