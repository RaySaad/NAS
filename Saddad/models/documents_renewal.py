# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import datetime
import base64


class DocumentRenewal(models.Model):
    _name = 'document.renewal'
    _description = "Document Renewal"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'id desc'

    def _employee_ids_domain(self):
        return [('company_id', '=', self.env.company.id)]

    def _get_default_product(self):
        product_id = self.env['product.product'].search(
            [('renewal_item', '=', True), ('renewal_type', '=', 'iqama_renewal'),
             ('company_id', '=', self.env.company.id)])
        return product_id

    date = fields.Date(readonly=True, default=fields.Date.context_today,
                       string="Date")
    is_iqama_renewal = fields.Boolean("Is Iqama Renewal", default=False)
    name = fields.Char('Description')
    bank_journal_id = fields.Many2one('account.journal')
    active = fields.Boolean(default=True)
    reference = fields.Char()
    identification_id = fields.Char(string="Iqama Number")
    date = fields.Date(readonly=True, default=fields.Date.context_today,
                       string="Date")
    iqama_expiry_date = fields.Date()
    employee_id = fields.Many2one('employee.record', string='Employee')


    days_left_to_expire = fields.Integer(string="Valid/Remaining Days", compute='_compute_days_left_to_expire')
    parent_id = fields.Many2one('employee.record', 'Manager')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id)
    decision = fields.Selection([('renewal', 'Renewal'),
                                 ('rejection', 'Rejection'),
                                 ], string='Decision')
    document_type = fields.Many2one('renewal.document.type', 'Type')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('hr_assistant', 'Hr Assistant'),
        ('hr_confirm', 'HR Confirmed'),
        ('refused', 'Refused'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')], string='Status', default='draft', tracking=True)
    period = fields.Selection([
        ('3month', '3 Months'),
        ('6month', '6 Months'),
        ('9month', '9 Months'),
        ('1year', '1 year')], string='Period', required=True)
    no_of_dependents = fields.Selection([
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5'),
        ('6', '6'),
        ('7', '7')], string='No Of Dependents')
    product_id = fields.Many2one('product.product', string="Product", readonly=True,
                                 default=_get_default_product)

    unit_price = fields.Float("Unit Price", readonly=True, required=True)
    quantity = fields.Float(required=True, readonly=True, default=1)
    # employee_iqama_expiry_list = fields.Binary('Employee Iqama Expiry', readonly=True)
    attachment_ids = fields.Many2many('ir.attachment')

    property_account_payable_id = fields.Many2one('account.account', string="Account Payable")

    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True,
                                  default=lambda self: self.env.company.currency_id)
    #
    total_amount = fields.Monetary("Total", store=True, currency_field='currency_id')

    work_permit_included = fields.Boolean(default=True)
    fee_for_family = fields.Boolean('Fee For Family', default=False)
    attachment_number = fields.Integer(compute='_compute_attachment_number')
    record_url = fields.Char(string="URL")

    def _compute_attachment_number(self):
        attachment_data = self.env['ir.attachment'].read_group([
            ('res_model', '=', 'document.renewal'),
            ('res_id', 'in', self.ids)], ['res_id'], ['res_id'])
        attachment = dict((data['res_id'], data['res_id_count']) for data in attachment_data)
        for doc in self:
            doc.attachment_number = attachment.get(doc.id, 0)

    def action_get_attachment_view(self):
        res = self.env['ir.actions.act_window']._for_xml_id('base.action_attachment')
        res['domain'] = [('res_model', '=', 'document.renewal'), ('res_id', '=', self.id)]
        res['context'] = {
            'create': False,
            'edit': False,
        }
        return res

    def _compute_days_left_to_expire(self):
        for rec in self:
            if rec.iqama_expiry_date:
                today = fields.Date.today()
                delta = rec.iqama_expiry_date - today
                rec.days_left_to_expire = delta.days
            else:
                rec.days_left_to_expire = 0

    


    @api.model_create_multi
    def create(self, vals):
        for val in vals:
            if not val.get('name'):
                val['name'] = self.env['ir.sequence'].next_by_code('document.renewal')
        records = super(DocumentRenewal, self).create(vals)
        for res in records:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            res.record_url = f"{base_url}/web#id={res.id}&model={self._name}&view_type=form"
        return records

    @api.onchange('period')
    def change_document_type(self):
        if self.period:
            document_type = self.env['renewal.document.type'].search([
                ('period', '=', self.period), ('type', '=', 'iqama_renewal')
            ])
            if document_type:
                self.unit_price = document_type.amount
                self.document_type = document_type.id
                self.total_amount = document_type.amount
            else:
                raise ValidationError(f"No Iqama Renewal Document defined for {self.period} period")
            if self.period and self.work_permit_included:
                work_permit = self.env['renewal.document.type'].search([
                    ('period', '=', self.period), ('type', '=', 'work_permit')
                ])
                if work_permit:
                    self.total_amount += work_permit.amount
                else:
                    raise ValidationError(f"No Work Permit Document defined for {self.period} period")

    @api.onchange('work_permit_included')
    def change_amount_total(self):
        if not self.work_permit_included:
            work_permit = self.env['renewal.document.type'].search([
                ('period', '=', self.period), ('type', '=', 'work_permit')
            ])
            self.total_amount -= work_permit.amount
        if self.work_permit_included:
            work_permit = self.env['renewal.document.type'].search([
                ('period', '=', self.period), ('type', '=', 'work_permit')
            ])
            self.total_amount += work_permit.amount

    @api.onchange('no_of_dependents')
    def change_no_of_dependents(self):
        if self.period and self.fee_for_family and self.no_of_dependents:
            document_type = self.env['renewal.document.type'].search([
                ('period', '=', self.period), ('type', '=', 'iqama_renewal')
            ])
            work_permit = self.env['renewal.document.type'].search([
                ('period', '=', self.period), ('type', '=', 'work_permit')
            ])
            fee_for_family = self.env['renewal.document.type'].search([
                ('period', '=', False), ('type', '=', 'other')
            ])

            if fee_for_family:
                self.total_amount = document_type.amount + work_permit.amount + (
                        int(self.no_of_dependents) * fee_for_family.amount * int(self.period[0]))

    @api.onchange('fee_for_family')
    def change_family_fee(self):
        if not self.fee_for_family and self.period and self.work_permit_included:
            document_type = self.env['renewal.document.type'].search([
                ('period', '=', self.period), ('type', '=', 'iqama_renewal')
            ])
            work_permit = self.env['renewal.document.type'].search([
                ('period', '=', self.period), ('type', '=', 'work_permit')
            ])
            self.total_amount = document_type.amount + work_permit.amount
        if self.period and self.fee_for_family and self.no_of_dependents:
            document_type = self.env['renewal.document.type'].search([
                ('period', '=', self.period), ('type', '=', 'iqama_renewal')
            ])
            work_permit = self.env['renewal.document.type'].search([
                ('period', '=', self.period), ('type', '=', 'work_permit')
            ])
            fee_for_family = self.env['renewal.document.type'].search([
                ('period', '=', False), ('type', '=', 'other')
            ])
            self.total_amount = document_type.amount + work_permit.amount + (
                int(self.no_of_dependents) * fee_for_family.amount * int(self.period[0]) if int(
                    self.period[0]) != 1 else 12)

    def attach_document(self, **kwargs):
        pass

    def send_approval_email(self, email_group):
        template_id = self.env.ref('saddad.pending_to_renew_email_template').id
        template = self.env['mail.template'].browse(template_id)
        template.email_to = ','.join(
            employee.work_email for employee in email_group.employee_ids if employee.work_email)
        template.sudo().send_mail(self.id, force_send=True)

    def confirm_by_hr(self):
        if not self.env.user.has_group('hr.group_hr_user'):
            raise ValidationError(_('Only Hr Assistant Can confirm expense'))
        self.write({
            'state': 'hr_confirm'
        })

    def action_submit(self):
        self.write({
            'state': 'hr_assistant'
        })

    def cancel_request(self):
        for rec in self:
            rec.state = 'cancel'

    def action_refuse(self):
        for rec in self:
            rec.state = 'refused'

    def reset_to_draft(self):
        for rec in self:
            rec.state = 'draft'

    def create_document_renewal_expense(self, rec, iqama_product, doc_type):
        available_request = self.env['document.renewal'].sudo().search(
            [('employee_id', '=', rec.id), ('state', '=', 'draft')])
        if not available_request:
            document_renewal_request = self.env['document.renewal'].sudo().create({
                'date': datetime.date.today(),
                'employee_id': rec.id,
                'identification_id': rec.identification_id,
                'iqama_expiry_date': rec.identification_expiry_date,
                'product_id': iqama_product.id,
                'property_account_payable_id': iqama_product.property_account_expense_id.id if iqama_product.property_account_expense_id else False,
                'quantity': 1.0, 'document_type': doc_type.id,
                'unit_price': doc_type.amount,
                'company_id': rec.company_id.id,
                'period': doc_type.period
            })
            # document_renewal_request._onchange_employee_id()
            document_renewal_request.change_document_type()
        else:
            pass

    def unlink(self):
        """ Override unlink to stop the deletion on records if not in draft state. """
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError('You can delete record only in draft state')
        res = super(DocumentRenewal, self).unlink()
        return res

    def create_decument_renewal_request(self, iqama_records, doc_type):
        for rec in iqama_records:
            iqama_product = self.env['product.product'].sudo().search([
                '|',  # This applies OR condition between the two AND conditions
                '&', ('renewal_type', '=', 'iqama_renewal'), ('company_id', '=', rec.company_id.id),
                # First AND condition
                '&', ('renewal_type', '=', 'iqama_renewal'), ('company_id', '=', False)  # Second AND condition
            ])
            if len(iqama_product) > 1:
                iqama_product = iqama_product[0]

            iqama_renewal_employee_ids = self.search([]).filtered(
                lambda x: x.create_date.date() >= datetime.date.today() - timedelta(days=30)).mapped('employee_id').ids

            if rec.id not in iqama_renewal_employee_ids:
                self.create_document_renewal_expense(rec, iqama_product, doc_type)

    @api.model
    def check_document_expiry(self):
        """Check for documents expiring in the next 30 days and create renewal records"""
        date_after_month = datetime.date.today() + timedelta(days=30)
        iqama_records = self.env['employee.record'].search(
            [('identification_id', '!=', False),
             ('identification_expiry_date', '<=', date_after_month)
             ])
        doc_type = self.env['renewal.document.type'].search([
            ('name', 'ilike', 'Iqama Renewal')
        ])
        doc_type = doc_type[0] if doc_type else False
        if doc_type:
            if iqama_records:
                self.create_decument_renewal_request(iqama_records, doc_type)
        else:
            raise ValidationError(_("There is no Document type name Iqama Renewal. Please create document type"))

    def _create_expense_lines(self):
        lines = []
        lines.append((0, 0, {
            'product_id': self.product_id.id,
            'date': self.date,
            'period': self.period,
            'unit_price': self.unit_price,
            'quantity': 1,
        }))
        if self.work_permit_included:
            permit_cost = 0.0
            product_id = self.env['product.product'].search(
                [
                    '|',  # OR condition between the two AND conditions
                    '&', ('renewal_type', '=', 'work_permit_renewal'), ('company_id', '=', self.company_id.id),
                    # First AND condition
                    '&', ('renewal_type', '=', 'work_permit_renewal'), ('company_id', '=', False)
                    # Second AND condition
                ])
            if not product_id:
                raise ValidationError(
                    f"Work permit Renewal not defined in {self.company_id.name} please create one and try again!")
            document_type = self.env['renewal.document.type'].search(
                [('period', '=', self.period), ('type', '=', 'work_permit')])
            if document_type:
                permit_cost = document_type.amount
            else:
                raise ValidationError(f"No work permit defined for {self.period} period")
            lines.append((0, 0, {
                'product_id': product_id[0].id if len(product_id) > 1 else product_id.id,
                'date': self.date,
                'period': self.period,
                'unit_price': permit_cost,
                'quantity': 1,
            }))
        if self.fee_for_family and self.no_of_dependents:
            product_id = self.env['product.product'].search(
                [
                    '|',  # OR condition between the two AND conditions
                    '&', ('name', '=', 'Fees For Family Iqama'), ('company_id', '=', self.company_id.id),
                    # First AND condition
                    '&', ('name', '=', 'Fees For Family Iqama'), ('company_id', '=', False)  # Second AND condition
                ])
            if not product_id:
                raise ValidationError(
                    f"FEES FOR FAMILY IQAMA not defined in {self.company_id.name} please create one and try again!")
            lines.append((0, 0, {
                'product_id': product_id[0].id if len(product_id) > 1 else product_id.id,
                'date': self.date,
                'period': self.period,
                'no_of_family_members': self.no_of_dependents,
                'unit_price': self.env['renewal.document.type'].search(
                    [('period', '=', False), ('type', '=', 'other')]).amount * int(self.no_of_dependents) * int(
                    self.period[0]) if int(
                    self.period[0]) != 1 else 12 if
                self.env['renewal.document.type'].search([('period', '=', False), ('type', '=', 'other')]) else 0.0,
                'quantity': 1,
            }))
        return lines

    def create_expense(self, rec):
        document_renew_expense = self.env['document.renew.expense'].create({
            'product_id': rec.product_id.id,
            'date': rec.date,
            'employee_id': rec.employee_id.id,
            'identification_id': rec.identification_id,
            'iqama_expiry_date': rec.iqama_expiry_date,
            'state': 'hr_confirm',
            'bank_journal_id': rec.bank_journal_id.id if rec.bank_journal_id else False,
            'company_id': rec.company_id.id,
            'document_renewal_request_id': rec.id,
            'expense_line_ids': self._create_expense_lines(),

        })
        # document_renew_expense._onchange_employee_id()
        # document_renew_expense.hr_approval()
        attachments = self.env['ir.attachment'].search(
            [('res_id', '=', self.id), ('res_model', '=', 'document.renewal')])
        if attachments:
            for attachment in attachments:
                encoded_data = base64.b64encode(attachment.datas)
                self.env['ir.attachment'].create({
                    'name': attachment.name,
                    'type': 'binary',
                    'datas': encoded_data,
                    'res_model': 'document.renew.expense',  # e.g., 'res.partner'
                    'res_id': document_renew_expense.id,  # ID of the record to attach to
                    'mimetype': 'application/octet-stream',  # Or the appropriate MIME type
                })
        self.active = False

    def approved_by_manager(self):
        try:
            if self.employee_id.employee_type == 'external':
                self.update({'state': 'done'})
                return {
                    'effect': {
                        'type': 'rainbow_man',
                        'message': _("For the external employee, the request is directly approved."),
                    }
                }
            bank_mapping = self.env['default.journal.mapping'].search([('company_id', '=', self.env.company.id)])
            if bank_mapping:
                self.bank_journal_id = bank_mapping.bank_journal_id.id
            for rec in self:
                if not self.env.user.has_group('hr.group_hr_manager'):
                    raise ValidationError(_('Only Hr Manager Can confirm expense'))
                self.create_expense(rec)
                rec.state = 'done'
        except Exception as e:
            raise e

    def get_pending_docs(self):
        return len(
            self.env['document.renewal'].search([('state', '=', 'draft'), ('company_id', '=', self.env.company.id)]))

    def delete_renewal_request(self):
        requests = self.search([('state', '=', 'draft')])
        for req in requests:
            if req.employee_id.days_left_to_expire >= 1:
                req.unlink()

