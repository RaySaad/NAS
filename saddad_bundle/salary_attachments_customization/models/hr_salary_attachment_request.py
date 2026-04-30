# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.date_utils import start_of
from dateutil.relativedelta import relativedelta
from math import ceil
from datetime import timedelta


class HrSalaryAttachmentRequest(models.Model):
    _name = 'hr.salary.attachment.request'
    _description = 'Employee Loan Requests'
    _inherit = ['mail.thread']
    _rec_name = 'loan_serial_number'

    _sql_constraints = [
        (
            'check_monthly_amount', 'CHECK (monthly_amount > 0)',
            'Monthly amount must be strictly positive.'
        ),
        (
            'check_total_amount',
            'CHECK ((total_amount > 0 AND total_amount >= monthly_amount))',
            'Total amount must be strictly positive and greater than or equal to the monthly amount.'
        ),
        ('check_remaining_amount', 'CHECK (remaining_amount >= 0)', 'Remaining amount must be positive.'),
    ]

    def employee_domain(self):
        return ['|', ('company_id', '=', self.env.company.id), ('company_id', 'in', self.env.company.child_ids.ids)]

    show_morror_button = fields.Boolean(string='Show Morror Button', default=False)
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True, domain=employee_domain)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    description = fields.Char(required=True)
    monthly_amount = fields.Monetary('Monthly Amount', required=True, store=True, tracking=True,
                                     help='Amount to pay each month.')
    active_amount = fields.Monetary(
        'Active Amount', compute='_compute_active_amount',
        help='Amount to pay for this month, Monthly Amount or less depending on the Remaining Amount.',
    )
    total_amount = fields.Monetary(
        'Total Amount',
        tracking=True,
        help='Total amount to be paid.',
    )
    has_total_amount = fields.Boolean('Has Total Amount', compute='_compute_has_total_amount')
    paid_amount = fields.Monetary('Paid Amount', tracking=True, help='Amount already paid.')
    remaining_amount = fields.Monetary(
        'Remaining Amount', compute='_compute_remaining_amount', store=True,
        help='Remaining amount to be paid.',
    )
    date_start = fields.Date('Deduction Start Date', required=True, default=lambda r: start_of(fields.Date.today(), 'month'),
                             tracking=True)
    date_estimated_end = fields.Date(
        'Estimated End Date', compute='_compute_estimated_end',
        help='Approximated end date.',
    )
    date_end = fields.Date(
        'End Date', default=False, tracking=True,
        help='Date at which this assignment has been set as completed or cancelled.',
    )
    employee_payment_id = fields.Many2one('account.payment')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('finance_approval', 'Finance Approval'),
            ('management_approval', 'Management Approval'),
            ('pending_payment', 'Pending Payments'),
            ('hr_approval', 'HR Approval'),
            ('confirmed', 'Running'),
            ('requested_pardon', 'Requested Pardon'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled')
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
    )

    attachment = fields.Binary('Document', copy=False, tracking=True)
    attachment_name = fields.Char()
    salary_attachment_id = fields.Many2one('hr.salary.attachment', copy=False)

    balance_amount = fields.Monetary(string='Balance Amount', default=0, copy=False, compute='compute_balance')
    pardon_amount = fields.Monetary(string='Pardon Amount', copy=False)
    loan_serial_number = fields.Char(string='Loan Serial Number', default='/', copy=False)
    department_id = fields.Many2one('hr.department', string='Department', related='employee_id.department_id',
                                    domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    employee_nationality_id = fields.Many2one(
        'res.country', 'Nationality (Country)', tracking=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], default="male")
    employee_company_id = fields.Many2one('res.company', string='Employee Company', related='employee_id.company_id')
    duration = fields.Integer('Duration')
    installment_method = fields.Selection([
        ('amount', 'Amount'),
        ('duration', 'Duration')
    ], default='amount', required=True)
    requesting_user_id = fields.Many2one('res.users', ondelete='restrict', string="Requested By",
                                         default=lambda self: self.env.user.id)
    loan_type_id = fields.Many2one('hr.payslip.input.type', ondelete='restrict', string='Transaction Type', required=True, domain=[('available_in_attachments', '=', True)])
    job_id = fields.Many2one('hr.job', string='Job Title', related='employee_id.job_id')
    years_of_service = fields.Integer(string='Years of Service')
    pardon_reason = fields.Char(string='Pardon Reason')
    payslip_count = fields.Integer('# Payslips', compute='_compute_payslip_count')
    active = fields.Boolean(string='Active', default=True)
    note = fields.Char(string='Note')
    parent_request_id = fields.Many2one('hr.salary.attachment.request', string="Merged Request")

    @api.onchange('installment_method')
    def change_installment_method(self):
        self.write({
            'total_amount': 0.0,
            'duration': 0,
            'monthly_amount': 0.0,
            'balance_amount': 0.0
        })

    @api.depends('salary_attachment_id.payslip_ids')
    def _compute_payslip_count(self):
        for record in self:
            record.payslip_count = len(record.salary_attachment_id.payslip_ids)

    def duplicate_record(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Employee Loan Request',
            'res_model': 'hr.salary.attachment.request',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_employee_id': self.employee_id.id,
            },
        }

    @api.depends('paid_amount', 'pardon_amount')
    def compute_balance(self):
        for rec in self:
            if rec.total_amount:
                rec.balance_amount = rec.total_amount - rec.paid_amount
            if rec.pardon_amount:
                rec.balance_amount = rec.balance_amount - rec.pardon_amount
            if rec.salary_attachment_id:
                rec.update_attachment_values()

    def update_attachment_values(self):
        pass
        # if self.salary_attachment_id:
        #     self.salary_attachment_id.write(
        #         {
        #             'total_amount': self.total_amount,
        #             'monthly_amount': self.monthly_amount
        #         }
        #     )

    def action_done(self):
        self.write({
            'pardon_amount': self.total_amount - self.paid_amount,
            'state': 'completed',
            'date_end': fields.Date.today()  if fields.Date.today() > self.date_start else self.date_start + timedelta(days=1)
        })
        if self.salary_attachment_id and self.salary_attachment_id.state != 'close':
            self.salary_attachment_id.action_done()

    def action_open(self):
        self.write({
            'state': 'confirmed',
            'date_end': False,
            'pardon_reason': '',
        })
        self.compute_balance()
        self.salary_attachment_id.action_open()

    def reset_to_draft(self):
        for rec in self:
            rec.update({
                'state': 'draft'
            })
            if rec.salary_attachment_id and rec.salary_attachment_id != 'draft':
                rec.salary_attachment_id.update({
                    'state': 'draft'
                })

    def action_cancel(self):
        self.write({
            'state': 'cancelled',
            'date_end': fields.Date.today(),
        })
        if self.salary_attachment_id and self.salary_attachment_id.state != 'cancel':
            self.salary_attachment_id.action_cancel()

    def open_pardon_request(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pardon Request',
            'res_model': 'pardon.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'attachment_id': self.salary_attachment_id.id,
            },
        }

    def unlink(self):
        res = False
        for rec in self:
            if rec.state not in ('draft','cancelled'):
                raise ValidationError("Request Could be Delet in Draft State Only")
            elif rec.state == 'draft' and rec.salary_attachment_id:
                salary_attachment = rec.salary_attachment_id
                rec.salary_attachment_id.update({
                    'salary_attachment_request_id': False
                })
                rec.salary_attachment_id = False
                res = super(HrSalaryAttachmentRequest, rec).unlink()
                salary_attachment.unlink()
            else:
                return super(HrSalaryAttachmentRequest, rec).unlink()
        return res

    @api.model_create_multi
    def create(self, vals):
        res = super(HrSalaryAttachmentRequest, self).create(vals)
        return res

    @api.depends('date_end')
    def _compute_has_total_amount(self):
        for record in self:
            if not record.date_end:
                record.has_total_amount = False
            else:
                record.has_total_amount = True

    @api.depends('total_amount', 'paid_amount', 'monthly_amount')
    def _compute_active_amount(self):
        for record in self:
            record.active_amount = min(record.monthly_amount, record.remaining_amount)

    # @api.onchange('employee_id')
    # def update_experience(self):
    #     if self.employee_id.joining_date:
    #         today = datetime.date.today()
    #         joining_date = self.employee_id.joining_date
    #         self.years_of_service = today.year - joining_date.year - (
    #                 (today.month, today.day) < (joining_date.month, joining_date.day))

    def send_for_approval(self):
        name = self.env['ir.sequence'].next_by_code('salary.attachment.request')
        self.update({
            'loan_serial_number': name,
        })
        for rec in self:
            rec.state = 'finance_approval'

    def action_finance_approval(self):
        for rec in self:
            rec.state = 'management_approval'

    def action_management_approval(self):
        for rec in self:
            rec.state = 'hr_approval'

    def action_hr_approval(self):
        for rec in self:
            if rec.loan_type_id.payment_type == 'with_payment':
                rec.state = 'pending_payment'
            else:
                return rec.action_confirm()

    def action_pardon_refused(self):
        for rec in self:
            rec.state = 'confirmed'
            rec.pardon_reason = 'False'

    def action_confirm(self):
        if self.state in ('hr_approval', 'pending_payment') and not self.salary_attachment_id:
            salary_attachment = self.env['hr.salary.attachment'].sudo().create({
                'employee_ids': [self.employee_id.id] or False,
                'company_id': self.company_id.id or False,
                'currency_id': self.currency_id.id or False,
                'date_estimated_end': self.date_estimated_end or '',
                'date_start': self.date_start,
                'other_input_type_id': self.loan_type_id.id,
                'description': self.description,
                'monthly_amount': self.monthly_amount or 0.0,
                'paid_amount': self.paid_amount or 0.0,
                'remaining_amount': self.remaining_amount or 0.0,
                'state': 'draft',
                'total_amount': self.total_amount,
                'salary_attachment_request_id': self.id
            })
            self.write({
                'state': 'confirmed',
                'salary_attachment_id': salary_attachment
            })
            if self.salary_attachment_id.other_input_type_id.payment_type != 'with_payment':
                res = self.salary_attachment_id.action_confirm()
                if res == True:
                    self.salary_attachment_id.generate_installments()
                return res
            else:
                self._loan_message_auto_subscribe_notify_owner()
        else:
            self.write({
                'state': 'confirmed'
            })
            if self.salary_attachment_id and self.salary_attachment_id.state == 'draft':
                self.salary_attachment_id.write({
                    'state': 'open'
                })

    @api.depends('total_amount', 'monthly_amount', 'date_start')
    def _compute_estimated_end(self):
        for record in self:
            if record.monthly_amount:
                record.date_estimated_end = start_of(
                    record.date_start + relativedelta(months=ceil(record.total_amount / record.monthly_amount)),
                    'month')
                if not record.paid_amount:
                    record.duration = record.total_amount / record.monthly_amount
            else:
                record.date_estimated_end = False

    @api.onchange('duration')
    def update_estimated_end(self):
        record = self
        if record.state != 'confirmed' and record.duration:
            record.date_estimated_end = start_of(
                record.date_start + relativedelta(months=record.duration),
                'month')
            record.monthly_amount = record.total_amount / record.duration

    @api.depends('total_amount', 'paid_amount')
    def _compute_remaining_amount(self):
        for record in self:
            if record.has_total_amount:
                record.remaining_amount = max(0, record.total_amount - record.paid_amount)
            else:
                record.remaining_amount = record.monthly_amount

    def record_payment(self, paid_amount):
        self.paid_amount = paid_amount

    def action_open_salary_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Salary Attachments',
            'res_model': 'hr.salary.attachment',
            'view_mode': 'form',
            'res_id': self.salary_attachment_id.id
            # 'domain': [('id', '=', self.salary_attachment_id.id)],
        }

    def action_open_payslips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payslips',
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.salary_attachment_id.payslip_ids.ids)],
        }

    def action_open_employee_payment(self):
        loan_type_id = self.employee_id.address_id or False
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payments',
            'res_model': 'account.payment',
            'view_mode': 'form',
            "context": {'default_employee_payment': True, 'default_is_loan_payment': True,
                        'default_payment_type': 'outbound', 'default_employee_id': self.employee_id.id,
                        'default_partner_id': loan_type_id.id,
                        'default_amount': self.total_amount,
                        'default_loan_request_id': self.id,
                        'default_journal_id': False,
                        'default_employee_payment_type': loan_type_id.id if loan_type_id else False},
        }

    def view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payments',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('loan_request_id', '=', self.id), ('is_loan_payment', '=', True)],
        }

    def get_res_id(self):
        res_id = self.env['morror'].search([('loan_advance_request_id', '=', self.id)])
        return res_id.id if res_id else False

    def action_get_morror_view(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Mirror View',
            'res_model': 'morror',
            'view_mode': 'form',
            'res_id': self.get_res_id(),
        }

    @api.model
    def _loan_message_auto_subscribe_notify_owner(self):
        if self.env.context.get('mail_auto_subscribe_no_notify'):
            return
        # Utility method to send assignation notification upon writing/creation.
        template_id = self.env['ir.model.data']._xmlid_to_res_id(
            'salary_attachments_customization.loan_message_user_assigned',
            raise_if_not_found=False)
        if not template_id:
            return
        model_description = self.env['ir.model']._get('hr.salary.attachment').display_name
        values = {
            'object': self.salary_attachment_id,
            'model_description': model_description,
            'access_link': self.salary_attachment_id._notify_get_action_link('view'),
        }
        group = self.env.ref('salary_attachments_customization.loan_approvers')
        users = group.users
        for user in users:
            values.update(assignee_name=' ' + user.partner_id.name)
            assignation_msg = self.env['ir.qweb']._render(
                'salary_attachments_customization.loan_message_user_assigned', values,
                minimal_qcontext=True)
            assignation_msg = self.env['mail.render.mixin']._replace_local_links(assignation_msg)
            self.salary_attachment_id.message_notify(
                subject=_('You have been assigned to %s', self.salary_attachment_id.display_name),
                body=assignation_msg,
                partner_ids=user.partner_id.ids,
                record_name=self.salary_attachment_id.display_name,
                email_layout_xmlid='mail.mail_notification_layout',
                model_description=model_description,
                mail_auto_delete=False,
            )
