# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp
from markupsafe import Markup
from odoo.exceptions import ValidationError
from lxml import etree
from datetime import datetime, timedelta


class Morror(models.Model):
    _name = 'morror'
    _description = 'Morror'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'serial_number'
    _order = 'id desc'

    @api.depends('morror_line_ids')
    def _compute_amount(self):
        total_value = 0
        for line in self.morror_line_ids:
            total_value += line.total_amount
        self.total_amount = total_value

    @api.depends('morror_line_ids')
    def _compute_violation_number(self):
        for rec in self:
            all_violations = ' '
            for line in rec.morror_line_ids:
                if line.violation_number:
                    all_violations = all_violations + ' ' + line.violation_number
            rec.violation_number = all_violations

    @api.depends('morror_line_ids')
    def _compute_product(self):
        if self.morror_line_ids and len(self.morror_line_ids) == 1:
            self.product_id = self.morror_line_ids.product_id.name
        if self.morror_line_ids and len(self.morror_line_ids) > 1:
            self.product_id = self.morror_line_ids[0].product_id.name + ' ' + 'Count' + ' ' + '[' + str(
                len(self.morror_line_ids)) + ']'

    def compute_attachment_number(self):
        for rec in self:
            attachments = self.env['ir.attachment'].search(
                [('res_model', '=', 'morror'),
                 ('res_id', '=', rec.id)])
            if attachments:
                rec.attachment_number = len(attachments)
            else:
                rec.attachment_number = 0

    def default_bank_journal(self):
        bank_mapping = self.env['default.journal.mapping'].search([('company_id', '=', self.env.company.id)])
        if bank_mapping:
            return bank_mapping.bank_journal_id.id

    def employee_domain(self):
        return ['|', ('company_id', '=', self.env.company.id), ('company_id', 'in', self.env.company.child_ids.ids)]

    name = fields.Char(default='New')
    serial_number = fields.Char()
    date = fields.Date(readonly=True, default=fields.Date.context_today,
                       string="Date")
    employee_id = fields.Many2one('hr.employee', string='Employee', domain=employee_domain)

    expense_type = fields.Selection([
        ('traffic_violation', 'Traffic Violation'),
        ('driving_licence', 'Driving Licence'),
        ('motor_vehicle', 'Motor Vehicle'),
    ], required=True)
    fleet_id = fields.Many2one('fleet.vehicle', string="Vehicle")
    fleet_readonly = fields.Boolean(string='Is Readonly')
    attachment_id = fields.Binary()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('fleet', 'Fleet Manager'),
        ('financial_approval', 'Financial Approval'),
        ('gm', 'GM'),
        ('payment_pending', 'Pending Payment'),
        ('refused', 'Refused'),
        ('done', 'Done'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled')], string='Status', default='draft', tracking=True)
    product_id = fields.Char(string="Product", store=True, compute='_compute_product')
    identification_id = fields.Char(string="Iqama Number")
    deduction_date = fields.Date('Deduction Date')
    sponsor_id = fields.Char()
    bank_journal_id = fields.Many2one('account.journal', 'Account Journal',
                                      domain=[('type', '=', 'bank')], default=default_bank_journal)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id)
    vehicle_no = fields.Char()
    owner_id = fields.Char(translate=True)
    sequence = fields.Char(translate=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True,
                                  default=lambda self: self.env.company.currency_id)
    morror_line_ids = fields.One2many('morror.line', 'morror_id', string="Expenses", )
    total_amount = fields.Monetary("Total Amount", store=True, currency_field='currency_id', compute='_compute_amount')
    attachment_number = fields.Integer('Attachment Number', )
    account_move_id = fields.Many2one('account.move', ondelete='cascade')
    record_url = fields.Char(string="URL")
    payment_mode = fields.Selection([
        ("own_account", "Employee"),
        ("company_account", "Company")
    ], default='own_account',
        string="Paid For")
    is_gm_user = fields.Boolean(string='Is GM User', compute="_compute_gm_user")
    violation_number = fields.Char(string='Violation Number', compute="_compute_violation_number")

    @api.onchange('employee_id')
    def _onchange_employee(self):
        if self.employee_id:
            self.sponsor_id = s = self.employee_id.sponsor_id
            self.identification_id = self.employee_id.identification_id

    def _compute_gm_user(self):
        if self.env.user.has_group('saddad.group_saddad_gm'):
            self.is_gm_user = True
        else:
            self.is_gm_user = False

    def attach_document(self, **kwargs):
        pass

    # def send_approval_email(self, group_xmlid, message_suffix):
    #     """Generic function to send approval emails to specified group"""
    #     try:
    #         group = self.env.ref(group_xmlid)
    #         if group and group.users:
    #             template = self.env.ref('saddad.morror_email_template')
    #             user_emails = [user.email for user in group.users if user.email]
    #             if user_emails:
    #                 template.email_to = ','.join(user_emails)
    #                 # Send email without posting to chatter
    #                 template.with_context(mail_post_autofollow=False).sudo().send_mail(self.id, force_send=True, email_layout_xmlid=False)
    #
    #                 # Add simple text message to chatter (without email template)
    #                 self.message_post(
    #                     body=f"Morror request {self.serial_number} {message_suffix}",
    #                     message_type='notification'
    #                 )
    #     except Exception:
    #         pass

    def send_approval_email(self, email_group):
        """Generic method to send approval emails to any group"""
        if not email_group:
            return

        # Get recipients from group users
        recipients = [user.partner_id.email for user in
                      email_group.users.filtered(lambda user: self.env.company in user.company_ids) if
                      user.partner_id.email]
        if not recipients:
            # Post message in chatter
            self.message_post(
                body=Markup(
                    f'<div class="alert alert-warning"><i class="fa fa-exclamation-triangle"></i> <strong>No email recipients found in {email_group.name} group for the company {self.env.company.name}</strong></div>'),
                message_type='notification'
            )
            return

        template = self.env.ref('saddad.morror_email_template', raise_if_not_found=False)
        if template:
            template.sudo().email_to = ','.join(recipients)
            template.sudo().send_mail(self.id, force_send=True)

        # Post message in chatter
        self.message_post(
            body=f'Notification sent to {email_group.name} group. Recipients: {", ".join(recipients)}',
            message_type='notification'
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('expense_type') == 'traffic_violation' and vals.get('morror_line_ids'):
                violation_numbers = [line[2].get('violation_number') for line in vals.get('morror_line_ids')]
                self.check_duplicates(violation_numbers)
            name = self.env['ir.sequence'].next_by_code('morror')
            vals.update({
                'serial_number': name,
            })
        records = super(Morror, self).create(vals_list)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in records:
            record.record_url = f"{base_url}/web#id={record.id}&model={self._name}&view_type=form"
        return records

    def check_duplicates(self, vals_list):
        """
        Function to check the duplicate violation number when we create a morror request to insure there wouldn't be a
        duplicate violation number
        """
        violations = []
        violation_numbers = self.env['morror.line'].search([('violation_number', '!=', False)]).mapped(
            'violation_number')
        for violation in vals_list:
            if violation in violation_numbers:
                violations.append(violation)
        if violations:
            raise ValidationError(f'Duplicate violation numbers not allowed {violations}')

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(Morror, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                  submenu=submenu)
        if self.env.user.has_group('saddad.group_saddad_accountant') and not self.env.user.has_group(
                'base.group_system'):
            root = etree.fromstring(res['arch'])
            root.set('create', 'false')
            res['arch'] = etree.tostring(root)
        elif self.env.user.has_group('saddad.saddad_post_entries') and not self.env.user.has_group(
                'base.group_system'):
            root = etree.fromstring(res['arch'])
            root.set('create', 'false')
            root.set('edit', 'false')
            res['arch'] = etree.tostring(root)
        else:
            pass
        return res

    def action_confirm(self):
        if not self.morror_line_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'You cannot submit an expense without expense lines.',
                    'type': 'danger',
                }
            }
        self.write({
            'state': 'fleet'
        })
        fleet_manager_group = self.env.ref('saddad.fleet_manager_group', raise_if_not_found=False)
        if fleet_manager_group:
            self.send_approval_email(fleet_manager_group)

    def fleet_manager_approval(self):
        self.write({
            'state': 'financial_approval'
        })
        gm_group = self.env.ref('saddad.group_saddad_financial_approval', raise_if_not_found=False)
        if gm_group:
            self.send_approval_email(gm_group)

    def financial_approval(self):
        self.write({
            'state': 'gm'
        })
        gm_group = self.env.ref('saddad.group_saddad_gm', raise_if_not_found=False)
        if gm_group:
            self.send_approval_email(gm_group)

    def gm_approval(self):
        self.write({
            'state': 'payment_pending'
        })
        accountant_group = self.env.ref('saddad.group_saddad_accountant', raise_if_not_found=False)
        if accountant_group:
            self.send_approval_email(accountant_group)

    def action_cancel(self):
        self.write({
            'state': 'cancel'
        })
        self.morror_line_ids.write({
            'is_paid': False
        })

    def action_refuse(self):
        self.write({
            'state': 'refused'
        })

    def action_reset_to_draft(self):
        self.write({
            'state': 'draft'
        })

    def onchange_state(self):
        pass

    def get_starting_month(self, month_number):
        if len(str(month_number)) == 1:
            month_value = str(month_number).zfill(2)
        else:
            month_value = str(month_number)
        month_dict = {
            '01': 'January',
            '02': 'February',
            '03': 'March',
            '04': 'April',
            '05': 'May',
            '06': 'June',
            '07': 'July',
            '08': 'August',
            '09': 'September',
            '10': 'October',
            '11': 'November',
            '12': 'December'
        }
        return [key for key in month_dict.keys() if key == month_value][0]

    @api.onchange('deduction_date')
    def onchange_deduction_date(self):
        if self.deduction_date:
            if self.deduction_date < fields.date.today():
                raise ValidationError("Deduction Date Can't be in past please select from today or in near future")
            if self.deduction_date > fields.date.today() + timedelta(days=60):
                raise ValidationError("You can select a date between today and or within next 30 days")

    @api.onchange('fleet_id')
    def _onchange_fleet(self):
        if self.fleet_id:
            self.vehicle_no = self.fleet_id.license_plate
        else:
            self.vehicle_no = ''
            self.owner_id = ''
            self.sequence = ''

    def action_get_attachment_view(self):
        res_ids = self.morror_line_ids.mapped('id')
        res_ids.append(self.id)
        res = self.env['ir.actions.act_window']._for_xml_id('base.action_attachment')
        res['domain'] = [('res_model', 'in', ('morror', 'morror.line')),
                         ('res_id', 'in', res_ids)]
        res['context'] = {
            'create': False,
            'edit': False,
        }
        return res

    def action_open_account_move(self):
        self.ensure_one()
        return {
            'name': self.account_move_id.name,
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.account_move_id.id
        }

    def get_expense_account(self, line):
        if line.payment_mode == 'company_account':
            return line.product_id.property_account_expense_id.id,
        else:
            default_loan_account = self.env['company.loan.account.mapping'].search(
                [('company_id', '=', self.company_id.id)])
            return default_loan_account.loan_account_id.id

    def _create_move_lines(self):
        lines = []
        for line in self.morror_line_ids:
            i = 1
            while i != 3:
                if i == 1:
                    lines.append((0, 0, {
                        'account_id': self.get_expense_account(line),
                        'name': str(line.morror_id.employee_id.name) + str(line.product_id.name),
                        'currency_id': line.currency_id.id,
                        'debit': line.total_amount,
                        'credit': 0.0,
                    }))
                else:
                    lines.append((0, 0, {
                        'account_id': self.bank_journal_id.default_account_id.id,
                        'name': str(line.morror_id.employee_id.name) + str(line.product_id.name),
                        'currency_id': line.currency_id.id,
                        'debit': 0.0,
                        'credit': line.total_amount,
                    }))
                i += 1
        return lines

    def post_entries(self):
        if self.state == 'done' and self.bank_journal_id:
            move = self.env['account.move'].create({
                'ref': self.name,
                'move_type': 'entry',
                'company_id': self.company_id.id,
                'journal_id': self.bank_journal_id.id,
                'currency_id': self.currency_id.id,
                'date': fields.Date.today(),
                'line_ids': self._create_move_lines(),
            })
            self.write({
                'account_move_id': move.id,
                'state': 'posted',
            })
        else:
            raise ValidationError('Bank Journal Missing')

    def unlink(self):
        """ Override unlink to stop the deletion on records if not in draft state. """
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError('You can delete record only in draft state')
        res = super(Morror, self).unlink()
        return res

    def mark_state_done(self):
        if all(self.morror_line_ids.mapped('is_paid')):
            self.state = 'done'
            self.onchange_state()

    def fleet_manager_approvals(self):
        morror_ids = self.env['morror'].browse(self.env.context.get('active_ids'))
        morror_ids = morror_ids.filtered(lambda x: x.state == 'fleet')
        for morror in morror_ids:
            morror.fleet_manager_approval()

    def gm_approvals(self):
        morror_ids = self.env['morror'].browse(self.env.context.get('active_ids'))
        morror_ids = morror_ids.filtered(lambda x: x.state == 'gm')
        for morror in morror_ids:
            morror.gm_approval()


class MorrorLines(models.Model):
    _name = 'morror.line'
    _description = "Morror Line"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _product_domain(self):
        return [
            '&',  # AND condition between the first condition and the result of the OR condition
            ('categ_id.type', '=', 'traffic_violation'),
            '|',  # OR condition for company_id
            ('company_id', '=', self.env.company.id),
            ('company_id', '=', False)
        ]

    date = fields.Date(readonly=True, default=fields.Date.context_today, string="Date")
    morror_id = fields.Many2one('morror', ondelete='cascade')
    description = fields.Char()
    product_id = fields.Many2one('product.product', string="Product", ondelete='restrict', required=True,
                                 domain=_product_domain)
    analytic_account_id = fields.Many2one("account.analytic.account", string="Analytic Account")
    attachment_id = fields.Binary(string='Attachment')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    unit_price = fields.Float("Unit Price", readonly=False, store=True, related='product_id.list_price',
                              tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True,
                                  default=lambda self: self.env.company.currency_id)
    total_amount = fields.Monetary(string="Total", store=True, currency_field='currency_id',
                                   compute='_compute_total_amount')

    violation_number = fields.Char()
    violation_date = fields.Date(string="Violation Date")
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id)

    is_paid = fields.Boolean('Paid')
    period = fields.Selection([
        ('2', '2'),
        ('5', '5'),
        ('10', '10'),
    ])
    note = fields.Char()
    attachment_number = fields.Integer('Attachment Number', compute='_compute_attachment_number')
    payment_mode = fields.Selection([
        ("own_account", "Employee"),
        ("company_account", "Company")
    ], default='own_account',
        string="Paid For", required=True)

    def unlink(self):
        """ Override unlink to delete messages and followers. This cannot be
        cascaded, because link is done through (res_model, res_id). """
        for rec in self:
            if rec.morror_id.state != 'draft':
                raise ValidationError('You can delete expense products only in draft state')
        res = super(MorrorLines, self).unlink()
        return res

    @api.onchange('violation_date')
    def violation_date_domain_change(self):
        if self.violation_date:
            if self.violation_date > fields.date.today():
                raise ValidationError("Violation Date Can't be in Future please select from today or in the past")

    def _compute_attachment_number(self):
        attachment_data = self.env['ir.attachment'].read_group([
            ('res_model', '=', 'morror.line'),
            ('res_id', 'in', self.ids)], ['res_id'], ['res_id'])
        attachment = dict((data['res_id'], data['res_id_count']) for data in attachment_data)
        for doc in self:
            doc.attachment_number = attachment.get(doc.id, 0)

    def action_get_attachment_view(self):
        self.ensure_one()
        res = self.env['ir.actions.act_window']._for_xml_id('base.action_attachment')
        res['domain'] = [('res_model', '=', 'morror.line'), ('res_id', 'in', self.ids)]
        res['context'] = {'default_res_model': 'morror.line', 'default_res_id': self.id}
        return res

    def service_paid(self):
        if not self.morror_id.bank_journal_id:
            raise ValidationError('You need to select bank journal to process a payment')
        for rec in self:
            rec.is_paid = True
        if all(self.morror_id.morror_line_ids.mapped('is_paid')):
            self.morror_id.update({
                'state': 'done'
            })
            self.morror_id.mark_state_done()

    @api.depends('unit_price')
    def _compute_total_amount(self):
        for line in self:
            line.update({
                'total_amount': line.unit_price or 0.0
            })
