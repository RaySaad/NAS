# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError
from lxml import etree
from markupsafe import Markup
from datetime import timedelta
import re


def get_starting_month(month_number):
    """Convert month number to two digit string format (e.g. 1 -> '01')"""
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


def set_period(period):
    """Convert period months to equivalent days (3,6,9,12 months)"""
    if period == 3:
        return 90
    elif period == 6:
        return 180
    elif period == 9:
        return 270
    else:
        return 365


class DocumentRenewExpense(models.Model):
    _name = 'document.renew.expense'
    _description = "Document Renew Expense"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    @api.depends('expense_line_ids')
    def _compute_amount(self):
        """Compute total amount by summing expense line amounts"""
        total_value = 0
        for expense in self.expense_line_ids:
            total_value += expense.total_amount
        self.total_amount = total_value

    @api.depends('expense_line_ids')
    def _compute_product(self):
        """Set product name from expense lines, with count if multiple lines exist"""
        if self.expense_line_ids and len(self.expense_line_ids) == 1:
            self.product_id = self.expense_line_ids.product_id.name
        if self.expense_line_ids and len(self.expense_line_ids) > 1:
            self.product_id = self.expense_line_ids[0].product_id.name + ' ' + 'Count' + ' ' + '[' + str(
                len(self.expense_line_ids)) + ']'

    @api.depends('expense_line_ids')
    def _compute_remarks(self):
        """Concatenate remarks from all expense lines"""
        for rec in self:
            all_remarks = ' '
            for expense in rec.expense_line_ids:
                if expense.remarks:
                    all_remarks = all_remarks + ' ' + expense.remarks
            rec.remarks = all_remarks

    def default_bank_journal(self):
        """Get default bank journal from mapping for current company"""
        bank_mapping = self.env['default.journal.mapping'].search([('company_id', '=', self.env.company.id)])
        if bank_mapping:
            return bank_mapping.bank_journal_id.id

    def employee_domain(self):
        return ['|', ('company_id', '=', self.env.company.id), ('company_id', 'in', self.env.company.child_ids.ids),
                ('employee_type', '=', 'internal')]

    def compute_attachment_number(self):
        """Calculate number of attachments linked to this record"""
        for rec in self:
            attachments = self.env['ir.attachment'].search(
                [('res_model', '=', 'document.renew.expense'),
                 ('res_id', '=', rec.id)])
            if attachments:
                rec.attachment_number = len(attachments)
            else:
                rec.attachment_number = 0

    name = fields.Char('Name', help="The name of the document renew expense")
    active = fields.Boolean(default=True, help="Whether this record is active or archived")
    document_renewal_request_id = fields.Many2one('document.renewal', ondelete='restrict',
                                                  help="Related document renewal request")
    date = fields.Date(readonly=True, default=fields.Date.context_today,
                       string="Date", help="Date of the expense")
    product_id = fields.Char(string="Product", store=True, compute='_compute_product',
                             help="Product name from expense lines")
    attachment_id = fields.Binary(help="Binary attachment for the expense")
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True,
                                  default=lambda self: self.env.company.currency_id,
                                  help="Currency used for the expense")

    employee_id = fields.Many2one('employee.record', string='Employee', required=True, tracking=True,
                                  domain=employee_domain, help="Employee associated with this expense")

    identification_id = fields.Char(string="Iqama Number", help="Identification number of the employee")
    paid_by = fields.Char('Paid By', help="Person or entity who paid the expense")
    total_amount = fields.Monetary("Amount Total", store=True, currency_field='currency_id', compute='_compute_amount',
                                   help="Total amount of the expense")
    bank_journal_id = fields.Many2one('account.journal', 'Account Journal', tracking=True,
                                      domain=[('type', '=', 'bank')], default=default_bank_journal,
                                      help="Bank journal for expense transactions")
    # modify field to add method
    operating_unit_id = fields.Many2one(
        comodel_name="operating.unit",
        string="Operating Unit",
        check_company=True,
        readonly=True,
        compute="_compute_operating_unit",
        store=True,
    )
    expense_account_id = fields.Many2one('account.account', 'Expense Account',
                                         help="Account used to record the expense")
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id, tracking=True,
                                 help="Company associated with this expense")
    cancel_note = fields.Char('Cancel Note', help="Note explaining why the expense was cancelled")
    account_move_id = fields.Many2one('account.move', ondelete='cascade', help="Related journal entry")
    # sponsor_id = fields.Char(help="Sponsor identifier")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('hr_assistant', 'HR Assistant'),
        ('hr_confirm', 'HR Approval'),
        ('financial_approval', 'Financial Approval'),
        ('gm', 'GM'),
        ('payment', 'Pending Payment'),
        ('refused', 'Refused'),
        ('done', 'Done'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled')], string='Status', default='draft', tracking=True)

    is_gm_user = fields.Boolean(string='Is GM User', compute="_compute_gm_user",
                                help="Indicates if the current user is a General Manager")
    has_loan_requests = fields.Boolean(default=False, help="Indicates if there are associated loan requests")
    jv_count = fields.Integer(compute='count_jv', help="Count of related journal vouchers")
    loan_request_count = fields.Integer(help="Count of related loan requests")

    serial_number = fields.Char()
    expense_line_ids = fields.One2many('document.renew.expense.line', 'expense_id')
    validated = fields.Boolean(default=False)
    attachment_number = fields.Integer(compute='compute_attachment_number')
    show_validate_expense_button = fields.Boolean()
    iqama_expiry_date = fields.Date('Iqama Expiry Date')
    iqama_expiry_date_hijri = fields.Char()
    record_url = fields.Char(string="URL")
    remarks = fields.Char(compute="_compute_remarks", store=True)
    show_journal_entry_button = fields.Boolean()
    # below method added for get auto fetch operating unit id against that employye we select in document renew expense form as per new changes in employee record model
    @api.depends('employee_id')
    def _compute_operating_unit(self):
        for rec in self:
            if rec.employee_id and rec.employee_id.employee_id:
                rec.operating_unit_id = rec.employee_id.employee_id.operating_unit_id or False
            elif rec.employee_id:
                rec.operating_unit_id = rec.employee_id.operating_unit_id or False
            else:
                rec.operating_unit_id = False

    @api.onchange('employee_id')
    def _onchange_employee(self):
        if self.employee_id:
            self.iqama_expiry_date = self.employee_id.identification_expiry_date
            # self.sponsor_id = self.employee_id.sponsor_id
            self.identification_id = self.employee_id.identification_id

    def _compute_gm_user(self):
        """Compute whether current user is a General Manager based on group membership"""
        if self.env.user.has_group('saddad.group_saddad_gm'):
            self.is_gm_user = True
        else:
            self.is_gm_user = False

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """Override fields_view_get to modify view permissions based on user groups"""
        res = super(DocumentRenewExpense, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
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

    def unlink(self):
        """ Override unlink to stop the deletion on records if not in draft state. """
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError('You can delete record only in draft state')
        res = super(DocumentRenewExpense, self).unlink()
        return res

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

        template = self.env.ref('saddad.muqeem_expense_email_template', raise_if_not_found=False)
        if template:
            template.sudo().email_to = ','.join(recipients)
            template.sudo().send_mail(self.id, force_send=True)

        # Post message in chatter
        self.message_post(
            body=f'Notification sent to {email_group.name} group. Recipients: {", ".join(recipients)}',
            message_type='notification'
        )

    def action_confirm(self):
        if not self.expense_line_ids:
            raise ValidationError('You cannot submit an expense without expense lines.')
        """Set state to hr_assistant and send approval email"""
        self.write({
            'state': 'hr_assistant'
        })
        hr_assistant_group = self.env.ref('saddad.group_saddad_hr_assistant', raise_if_not_found=False)
        if hr_assistant_group:
            self.send_approval_email(hr_assistant_group)

    def attach_document(self, **kwargs):
        """Placeholder for document attachment functionality"""
        pass

    def hr_assistant_confirm(self):
        """Set state to hr_confirm and send approval email"""
        self.write({
            'state': 'hr_confirm'
        })
        hr_group = self.env.ref('saddad.group_saddad_hr', raise_if_not_found=False)
        if hr_group:
            self.send_approval_email(hr_group)

    def hr_approval(self):
        """Set state to gm and send approval email"""
        self.write({
            'state': 'financial_approval'
        })
        accountant_group = self.env.ref('saddad.group_saddad_financial_approval', raise_if_not_found=False)
        if accountant_group:
            self.send_approval_email(accountant_group)

    def financial_approval(self):
        self.write({
            'state': 'gm'
        })
        gm_group = self.env.ref('saddad.group_saddad_gm', raise_if_not_found=False)
        if gm_group:
            self.send_approval_email(gm_group)

    def gm_approval(self):
        """Set state to payment and send approval email"""
        self.write({
            'state': 'payment'
        })
        accountant_group = self.env.ref('saddad.group_saddad_accountant', raise_if_not_found=False)
        if accountant_group:
            self.send_approval_email(accountant_group)

    def action_cancel(self):
        """Set state to cancel"""
        self.write({
            'state': 'cancel'
        })
        self.expense_line_ids.write({
            'is_paid': False
        })

    def action_refuse(self):
        self.write({
            'state': 'refused'
        })

    def action_reset_to_draft(self):
        """Reset state to draft"""
        self.write({
            'state': 'draft'
        })

    @api.model_create_multi
    def create(self, vals_list):
        """Create document renew expense with sequence number"""
        for vals in vals_list:
            name = self.env['ir.sequence'].next_by_code('document.renew.expense')
            vals.update({
                'name': name,
                'serial_number': name
            })
        records = super(DocumentRenewExpense, self).create(vals_list)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in records:
            record.record_url = f"{base_url}/web#id={record.id}&model={self._name}&view_type=form"
        return records

    def action_open_account_move(self):
        """Open journal entries view"""
        return {
            'name': 'Journal Entries',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'domain': [('expense_id', '=', self.id)],
        }

    def action_open_pending_to_renew(self):
        """Open document renewal request form view"""
        self.ensure_one()
        return {
            'name': self.document_renewal_request_id.name,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'document.renewal',
            'res_id': self.document_renewal_request_id.id
        }

    def _create_move_lines(self, available_lines):
        """Create journal entry lines"""
        lines = []
        for line in available_lines:
            i = 1
            while (i != 3):
                if i == 1:
                    lines.append((0, 0, {
                        'account_id': self.get_expense_account(line),
                        'name': str(line.expense_id.employee_id.employee_name) + str(line.product_id.name),
                        'currency_id': line.currency_id.id,
                        'debit': line.total_amount,
                        'credit': 0.0,
                    }))
                else:
                    lines.append((0, 0, {
                        'account_id': self.bank_journal_id.default_account_id.id,
                        'name': str(line.expense_id.employee_id.employee_name) + str(line.product_id.name),
                        'currency_id': line.currency_id.id,
                        'debit': 0.0,
                        'credit': line.total_amount,
                    }))
                i += 1
        return lines

    def post_entries(self):
        """Post journal entries"""
        if self.bank_journal_id:
            available_lines = self.expense_line_ids.filtered(lambda l: l.entry_created == False and l.is_paid == True)
            if not available_lines:
                raise ValidationError('No Lines available to create journal entries')
            move = self.env['account.move'].create({
                # 'recording_rule': 'standard',
                'ref': self.name,
                'move_type': 'entry',
                'company_id': self.company_id.id,
                'journal_id': self.bank_journal_id.id,
                'currency_id': self.currency_id.id,
                'date': fields.Date.today(),
                'expense_id': self.id,
                'line_ids': self._create_move_lines(available_lines),
            })
            available_lines.write({
                'entry_created': True
            })
            if any(self.expense_line_ids.mapped('entry_created')):
                self.update({
                    'show_journal_entry_button': True
                }
                )
            self.update_request_status()
        else:
            raise ValidationError('Bank Journal Missing')

    def update_request_status(self):
        """Update expense state to posted"""
        if all(self.expense_line_ids.mapped('entry_created')):
            self.state = 'posted'

    def copy(self, default=None):
        """Copy expense record"""
        default = default or {}
        res = super(DocumentRenewExpense, self).copy(default)
        res.expense_line_ids += self.expense_line_ids
        for line in self.expense_line_ids:
            line.copy({'expense_id': res.id})
        return res

    def action_validate_expense(self):
        """Validate multiple expenses"""
        expense_ids = self.env['document.renew.expense'].browse(self.env.context.get('active_ids')).filtered(
            lambda e: not e.validated)
        for expense in expense_ids:
            period_obj = expense.expense_line_ids.mapped('period')
            if len(period_obj) == 0:
                raise ValidationError(
                    "You haven't added period field in the expense you have to update first than you can process "
                    "this expense")
            elif len(period_obj) > 0:
                period_value = int(period_obj[0][0])
                expense.employee_id.update({
                    'identification_expiry_date': expense.employee_id.identification_expiry_date + timedelta(
                        days=set_period(period_value))
                })
                expense.update({
                    'validated': True
                })
            else:
                pass

    def validate_expense(self):
        """Validate single expense"""
        period_obj = self.expense_line_ids.mapped('period')
        if len(period_obj) == 0:
            raise ValidationError(
                "You haven't added period field in the expense you have to update first than you can process "
                "this expense")
        elif len(period_obj) > 0:
            period_value = int(period_obj[0][0])
            self.employee_id.write({
                'identification_expiry_date': self.employee_id.identification_expiry_date + timedelta(
                    days=set_period(period_value))
            })
            self.update({
                'validated': True
            })
        else:
            pass

    def action_get_attachment_view(self):
        """Open attachments view"""
        res_ids = self.expense_line_ids.mapped('id')
        res_ids.append(self.id)
        res = self.env['ir.actions.act_window']._for_xml_id('base.action_attachment')
        res['domain'] = [('res_model', 'in', ('document.renew.expense', 'document.renew.expense.line')),
                         ('res_id', 'in', res_ids)]
        res['context'] = {
            'create': False,
            'edit': False,
        }
        return res

    def get_muqeem_expenses(self):
        """Get count of pending expenses"""
        return len(
            self.env['document.renew.expense'].search([('state', 'not in', ('draft', 'done', 'posted', 'cancel'))]))

    def get_validate_expenses(self):
        """Get count of expenses to validate"""
        return len(
            self.env['document.renew.expense'].search([('state', 'in', ('posted', 'done')), ('validated', '=',
                                                                                             False),
                                                       ('show_validate_expense_button', '=', True)]))

    def action_open_loan_request(self):
        """Open loan requests view"""
        return {
            'name': 'Loan Request',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'loan.advance.request',
            'domain': [('muqeem_expense_id', '=', self.id)],

        }

    def get_expense_account(self, line):
        """Get expense account based on payment mode"""
        if line.payment_mode == 'company_account':
            if line.product_id.property_account_expense_id.id:
                return line.product_id.property_account_expense_id.id
            else:
                raise ValidationError(
                    f"You haven't specified the expense account for product [{line.product_id.name}] please specify one in configuration and try again")
        else:
            default_loan_account = self.env['company.loan.account.mapping'].search(
                [('company_id', '=', self.company_id.id)])
            if not default_loan_account:
                raise ValidationError(
                    f"You haven't specified the employee loan account for {self.company_id.name} please specify one in configuration and try again")
            else:
                return default_loan_account.loan_account_id.id

    def count_jv(self):
        """Count journal entries"""
        self.update({
            'jv_count': len(self.env['account.move'].search([('expense_id', '=', self.id)]))
        })

    def loan_count(self):
        """Count loan requests
        """
        self.update({
            'loan_request_count': len(self.env['loan.advance.request'].search([('muqeem_expense_id', '=', self.id)]))
        })

    def hr_assistant_approve(self):
        expense_ids = self.env['document.renew.expense'].browse(self.env.context.get('active_ids'))
        expense_ids = expense_ids.filtered(lambda l: l.state == 'hr_assistant')
        for expense in expense_ids:
            expense.hr_assistant_confirm()

    def hr_approvals(self):
        expense_ids = self.env['document.renew.expense'].browse(self.env.context.get('active_ids'))
        expense_ids = expense_ids.filtered(lambda l: l.state == 'hr_confirm')
        for expense in expense_ids:
            expense.hr_approval()

    def gm_approvals(self):
        expense_ids = self.env['document.renew.expense'].browse(self.env.context.get('active_ids'))
        expense_ids = expense_ids.filtered(lambda l: l.state == 'gm')
        for expense in expense_ids:
            expense.gm_approval()


class DocumentRenewExpenseLines(models.Model):
    _name = 'document.renew.expense.line'
    _description = 'Muqeem Expense Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.depends('quantity', 'unit_price', 'currency_id')
    def _compute_amount(self):
        for expense in self:
            expense.total_amount = expense.unit_price * expense.quantity
    # as this domain not showing products in  muqeem expense lines as it get no type field blank
    # def _product_domain(self):
    #     return [
    #         '&',  # AND condition between the first condition and the result of the OR condition
    #         ('categ_id.type', '=', 'muqeem_expenses'),
    #         '|',  # OR condition for company_id
    #         ('company_id', '=', self.env.company.id),
    #         ('company_id', '=', False)
    #     ]
    def _product_domain(self):
        return [
            '|',  # OR condition
            ('company_id', '=', self.env.company.id),
            ('company_id', '=', False)
        ]

    date = fields.Date(default=fields.Date.context_today,
                       string="Date")
    product_id = fields.Many2one('product.product', string="Product", required=True,
                                 domain=_product_domain)
    expense_id = fields.Many2one('document.renew.expense', ondelete='cascade')
    analytic_account_id = fields.Many2one("account.analytic.account", string="Analytic Account")
    attachment_id = fields.Binary(string='Attachment')
    unit_price = fields.Float("Unit Price", required=True, tracking=True)
    period = fields.Selection([
        ('3month', '3 Months'),
        ('6month', '6 Months'),
        ('9month', '9 Months'),
        ('1year', '1 year')], string="Iqama Period")
    visa_period = fields.Selection([
        ('30', '30'),
        ('60', '60'),
        ('90', '90'),
        ('120', '120'),
        ('150', '150'),
        ('180', '180'),
        ('210', '210'),
        ('240', '240'),
        ('270', '270'),
        ('300', '300'),
    ], string="Visa Period")
    iqama_period_readonly = fields.Boolean(default=False)
    visa_period_readonly = fields.Boolean(default=False)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True,
                                  default=lambda self: self.env.company.currency_id)
    total_amount = fields.Monetary("Total", store=True, currency_field='currency_id', compute='_compute_amount')

    quantity = fields.Float(required=True, readonly=True, default=1)
    remarks = fields.Char(tracking=True)
    is_paid = fields.Boolean('Paid')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')

    attachment_number = fields.Integer(compute='_compute_attachment_number')
    no_of_family_members = fields.Integer('Family Members')
    show_button = fields.Boolean(string="Show Button", compute='_compute_show_button')
    payment_mode = fields.Selection([
        ("own_account", "Employee"),
        ("company_account", "Company")
    ], default='company_account', string="Paid For", required=True)
    entry_created = fields.Boolean(default=False)
    created_loan_request = fields.Boolean(default=False)

    @api.depends('remarks')
    def _compute_show_button(self):
        for record in self:
            if record.remarks and re.match(r'^\d+$', record.remarks):
                record.show_button = True
            else:
                record.show_button = False

    @api.onchange('no_of_family_members')
    def update_price_unit(self):
        for rec in self:
            if rec.no_of_family_members and rec.product_id.name in (
                    'FEES FOR FAMILY IQAMA', 'رسوم المرافقين') and rec.period:
                rec.unit_price = rec.no_of_family_members * rec.unit_price
            if rec.product_id and rec.product_id.name not in ('FEES FOR FAMILY IQAMA', 'رسوم المرافقين'):
                raise ValidationError(
                    f"You can't add family members with {rec.product_id.name} Product. it could be select only with FEES FOR FAMILY IQAMA")

    def _compute_attachment_number(self):
        attachment_data = self.env['ir.attachment'].read_group([
            ('res_model', '=', 'document.renew.expense.line'),
            ('res_id', 'in', self.ids)], ['res_id'], ['res_id'])
        attachment = dict((data['res_id'], data['res_id_count']) for data in attachment_data)
        for doc in self:
            doc.attachment_number = attachment.get(doc.id, 0)

    def action_get_attachment_view(self):
        self.ensure_one()
        res = self.env['ir.actions.act_window']._for_xml_id('base.action_attachment')
        res['domain'] = [('res_model', '=', 'document.renew.expense.line'), ('res_id', 'in', self.ids)]
        res['context'] = {'default_res_model': 'document.renew.expense.line', 'default_res_id': self.id}
        return res

    def service_paid(self):
        if not self.expense_id.bank_journal_id:
            raise ValidationError('You need to select bank journal to process a payment')
        for rec in self:
            rec.is_paid = True
        if all(self.expense_id.expense_line_ids.mapped('is_paid')):
            self.expense_id.state = 'done'
            self.expense_id.paid_by = self.env.user.name

    @api.onchange('period')
    def change_document_type(self):
        if not self.period:
            return

        if not self.product_id:
            return

        document_type = False
        if self.product_id.renewal_type == 'iqama_renewal':
            document_type = self.env['renewal.document.type'].search([
                ('period', '=', self.period), ('type', '=', 'iqama_renewal')
            ])
        elif self.product_id.renewal_type == 'work_permit_renewal':
            document_type = self.env['renewal.document.type'].search([
                ('period', '=', self.period), ('type', '=', 'work_permit')
            ])

        if document_type and self.product_id.renewal_type in ('iqama_renewal', 'work_permit_renewal'):
            self.unit_price = document_type.amount
            return
        elif self.product_id.renewal_type in ('iqama_renewal', 'work_permit_renewal'):
            raise ValidationError(
                f"You haven't set price for {self.period} period please update in configuration")

        if self.product_id.name in ('FEES FOR FAMILY IQAMA', 'رسوم المرافقين'):
            document_type = self.env['renewal.document.type'].search([('type', '=', 'other')])
            if document_type:
                period_multiplier = int(self.period[0])
                family_members = self.no_of_family_members or 1
                self.unit_price = document_type.amount * period_multiplier * family_members
                if not self.no_of_family_members:
                    self.no_of_family_members = 1

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id:
            if self.product_id.renewal_type in (
                    'iqama_renewal', 'work_permit_renewal') or self.product_id.name in (
                    'FEES FOR FAMILY IQAMA', 'رسوم المرافقين'):
                self.iqama_period_readonly = True
                self.visa_period_readonly = False
            else:
                self.visa_period_readonly = True
                self.iqama_period_readonly = False
        else:
            self.visa_period_readonly = False
            self.iqama_period_readonly = False

    def unlink(self):
        """ Override unlink to delete messages and followers. This cannot be
        cascaded, because link is done through (res_model, res_id). """
        for rec in self:
            if rec.product_id.renewal_type == 'iqama_renewal':
                rec.expense_id.show_validate_expense_button = False
            if rec.expense_id.state != 'draft':
                raise ValidationError('You can delete expense products only in draft state')
        res = super(DocumentRenewExpenseLines, self).unlink()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super(DocumentRenewExpenseLines, self).create(vals_list)
        for record in records:
            if record.product_id.renewal_type == 'iqama_renewal':
                record.expense_id.show_validate_expense_button = True
        return records

    def write(self, vals):
        res = super(DocumentRenewExpenseLines, self).write(vals)
        if any(line.product_id.renewal_type == 'iqama_renewal' for line in
               self.expense_id.expense_line_ids):
            self.expense_id.show_validate_expense_button = True
        else:
            self.expense_id.show_validate_expense_button = False
        if set(vals) & set(self._track_get_fields()):
            self._track_changes(self.expense_id)
        return res

    def open_invoice_details(self):
        expense_lines = self.env['document.renew.expense.line'].sudo().search([('remarks', '=', self.remarks)])
        detail_ids = []
        for line in expense_lines:
            vals = {
                'expense_number': line.expense_id.serial_number or '',
                'employee_id': line.expense_id.employee_id.id or False,
                'identification_id': line.expense_id.identification_id or '',
                'company_id': line.expense_id.company_id.id or False,
                'status': line.expense_id.state or '',
                'unit_price': line.unit_price or 0.0,
                'remarks': line.remarks
            }
            line_details_obj = self.env['muqeem.expense.line.details'].sudo().create(vals)
            detail_ids.append(line_details_obj.id)
        domain = [("id", "in", detail_ids)]
        return {
            "name": _("Invoice Details"),
            "type": "ir.actions.act_window",
            "res_model": "muqeem.expense.line.details",
            "target": "new",
            "view_mode": "list",
            "domain": domain
        }

    def _track_changes(self, field_to_track):
        """
        function to log line level fields
        """
        message_id = field_to_track.message_post(
            body=f'{self._description} : {self.product_id.name} ').id
        trackings = self.env['mail.message'].search([('res_id', '=', self.id)]).filtered(
            lambda l: l.model == self.display_name.split(',')[0]).tracking_value_ids
        for tracking in trackings:
            tracking.write({
                'mail_message_id': message_id
            })

    # method for expense lines export to expense transactions
    def _track_changes(self, field_to_track):
        """
        function to log line level fields
        """
        message_id = field_to_track.message_post(
            body=f'{self._description} : {self.product_id.name} ').id
        trackings = self.env['mail.message'].search([('res_id', '=', self.id)]).filtered(
            lambda l: l.model == self.display_name.split(',')[0]).tracking_value_ids
        for tracking in trackings:
            tracking.write({
                'mail_message_id': message_id
            })

    def action_export_to_expense_transaction(self):
        """Export selected Muqeem Expense Lines to Expense Transaction"""
        selected_line_ids = self.env.context.get('active_ids', [])
        if not selected_line_ids:
            raise ValidationError('No lines selected for export')

        expense_lines = self.env['document.renew.expense.line'].browse(selected_line_ids)

        if not expense_lines:
            raise ValidationError('Selected lines not found')

        # Prepare expense detail lines data
        expense_detail_lines = []
        for line in expense_lines:
            # Get expense account from product
            expense_account = line.product_id.property_account_expense_id or False
            if not expense_account:
                raise ValidationError(
                    f"Product '{line.product_id.name}' does not have an Expense Account configured. "
                    f"Please configure it in the product's Accounting tab."
                )

            # Use same account for both fields (or configure separately if needed)
            prepaid_account = expense_account

            # Create analytic distribution if analytic account exists
            analytic_dist = False
            if line.analytic_account_id:
                analytic_dist = {str(line.analytic_account_id.id): 100}

            expense_detail_lines.append((0, 0, {
                'description': line.product_id.name,
                'employee_id': line.expense_id.employee_id.id,
                'operating_unit_id': line.expense_id.operating_unit_id.id,
                'prepaid_expense_account_id': prepaid_account.id,
                'expense_account_id': expense_account.id,
                'analytic_distribution': analytic_dist,
                'start_date': line.date,
                'end_date': line.date,
                'quantity': 1,
                'price_unit': line.unit_price,
                'price_total': line.total_amount,
                'company_id': line.expense_id.company_id.id,
            }))

        # Get company from first line
        company_id = expense_lines[0].expense_id.company_id.id

        # Find a general journal for the company
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', company_id)
        ], limit=1)

        if not journal:
            raise ValidationError(f'No General Journal found for company {expense_lines[0].expense_id.company_id.name}')

        # Create new Expense Transaction
        expense_transaction = self.env['account.expense.transaction'].create({
            'date': fields.Date.today(),
            'expense_nature': 'accrual',
            'amortization_method': 'on_time',
            'reference': f'MUQEEM-{fields.Date.today().strftime("%Y%m%d")}-{self.env.user.id}',
            'company_id': company_id,
            'expense_detail_ids': expense_detail_lines,
            'type_jv': 'each_line',
            'journal_id': journal.id,
        })

        # Return form view of created transaction
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.expense.transaction',
            'res_id': expense_transaction.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
        }