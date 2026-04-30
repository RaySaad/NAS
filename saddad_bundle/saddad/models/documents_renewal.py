# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from markupsafe import Markup
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
        """Generic method to send approval emails to any group"""
        if not email_group:
            return
        
        # Get recipients from group users
        recipients = [user.partner_id.email for user in email_group.users.filtered(lambda user: self.env.company in user.company_ids) if user.partner_id.email]
        if not recipients:
            # Post message in chatter
            self.message_post(
                body=Markup(f'<div class="alert alert-warning"><i class="fa fa-exclamation-triangle"></i> <strong>No email recipients found in {email_group.name} group for the company {self.env.company.name}</strong></div>'),
                message_type='notification'
            )
            return

        template = self.env.ref('saddad.pending_to_renew_email_template', raise_if_not_found=False)
        if template:
            template.sudo().email_to = ','.join(recipients)
            template.sudo().send_mail(self.id, force_send=True)

        # Post message in chatter
        self.message_post(
            body=f'Notification sent to {email_group.name} group. Recipients: {", ".join(recipients)}',
            message_type='notification'
        )

    def confirm_by_hr(self):
        if not self.env.user.has_group('hr.group_hr_user'):
            raise ValidationError(_('Only Hr Assistant Can confirm expense'))
        self.write({
            'state': 'hr_confirm'
        })

        hr_group = self.env.ref('saddad.group_saddad_hr', raise_if_not_found=False)
        if hr_group:
            self.send_approval_email(hr_group)

    def action_submit(self):
        self.write({
            'state': 'hr_assistant'
        })
        hr_assistant_group = self.env.ref('saddad.group_saddad_hr_assistant', raise_if_not_found=False)
        if hr_assistant_group:
            self.send_approval_email(hr_assistant_group)

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
        # Pre-calculate cutoff date to avoid repeated calculations
        today = datetime.date.today()
        
        # Get existing renewal employee IDs once per company to avoid repeated searches
        company_renewal_cache = {}
        
        for rec in iqama_records:
            # Cache product search per company
            if rec.company_id.id not in company_renewal_cache:
                iqama_product = self.env['product.product'].sudo().search([
                    '|',
                    '&', ('renewal_type', '=', 'iqama_renewal'), ('company_id', '=', rec.company_id.id),
                    '&', ('renewal_type', '=', 'iqama_renewal'), ('company_id', '=', False)
                ], limit=1)
                
                ptr_days = rec.company_id.ptr_days or 50
                cutoff_date = today - timedelta(days=ptr_days)
                
                # More efficient domain search instead of filtered
                existing_renewals = self.search([
                    ('create_date', '>=', cutoff_date),
                    ('employee_id.company_id', '=', rec.company_id.id)
                ]).mapped('employee_id').ids
                
                company_renewal_cache[rec.company_id.id] = {
                    'product': iqama_product,
                    'existing_employee_ids': existing_renewals
                }
            
            cache_data = company_renewal_cache[rec.company_id.id]
            if rec.id not in cache_data['existing_employee_ids']:
                self.create_document_renewal_expense(rec, cache_data['product'], doc_type)
            

    @api.model
    def check_document_expiry(self):
        """Check for documents expiring based on company-specific ptr_days and create renewal records"""
        companies = self.env['res.company'].search([('ptr_days', '>', 0)])
        all_iqama_records = self.env['employee.record']
        
        for company in companies:
            date_after_ptr_days = datetime.date.today() + timedelta(days=company.ptr_days)
            company_iqama_records = self.env['employee.record'].search(
                [('identification_id', '!=', False),
                 ('identification_expiry_date', '<=', date_after_ptr_days),
                 ('company_id', '=', company.id)
                 ])
            all_iqama_records |= company_iqama_records
        
        iqama_records = all_iqama_records
        doc_type = self.env['renewal.document.type'].search([
            ('name', 'ilike', 'Iqama Renewal')
        ])
        doc_type = doc_type[0] if doc_type else False
        if doc_type:
            if iqama_records:
                self.create_decument_renewal_request(iqama_records, doc_type)
                self._generate_excel_report(iqama_records)
        else:
            raise ValidationError(_("There is no Document type name Iqama Renewal. Please create document type"))

    def _generate_excel_report(self, iqama_records):
        """Generate professional Excel report and send via email"""
        import xlsxwriter
        import tempfile
        import base64
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        workbook = xlsxwriter.Workbook(temp_file.name)
        worksheet = workbook.add_worksheet('Document Expiry Report')
        
        # Professional formatting
        title_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#1F4E79', 'font_color': 'white', 'border': 1
        })
        header_format = workbook.add_format({
            'bold': True, 'font_size': 12, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#4472C4', 'font_color': 'white', 'border': 1
        })
        company_format = workbook.add_format({
            'bold': True, 'font_size': 11, 'align': 'left', 'valign': 'vcenter',
            'bg_color': '#D9E2F3', 'font_color': '#1F4E79', 'border': 1
        })
        data_format = workbook.add_format({
            'font_size': 10, 'align': 'left', 'valign': 'vcenter', 'border': 1
        })
        date_format = workbook.add_format({
            'font_size': 10, 'align': 'center', 'valign': 'vcenter', 'border': 1,
            'num_format': 'yyyy-mm-dd'
        })
        
        # Set column widths
        worksheet.set_column('A:A', 12)  # Emp Id
        worksheet.set_column('B:B', 25)  # Emp Name
        worksheet.set_column('C:C', 15)  # Iqama Number
        worksheet.set_column('D:D', 15)  # Expiry Date
        worksheet.set_column('E:E', 20)  # Company
        
        # Title row
        worksheet.merge_range('A1:E1', 'DOCUMENT EXPIRY REPORT', title_format)
        worksheet.set_row(0, 25)
        
        # Date row
        worksheet.merge_range('A2:E2', f'Generated on: {datetime.date.today().strftime("%B %d, %Y")}', 
                            workbook.add_format({'align': 'center', 'italic': True, 'font_size': 10}))
        
        # Group data by company
        companies_data = {}
        for rec in iqama_records:
            if rec.company_id.name not in companies_data:
                companies_data[rec.company_id.name] = []
            companies_data[rec.company_id.name].append(rec)
        
        row = 3
        headers = ['Emp Id', 'Emp Name', 'Iqama Number', 'Expiry Date', 'Company']
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)
        worksheet.set_row(row, 20)
        row += 1
        
        for company_name, records in companies_data.items():
            worksheet.merge_range(f'A{row+1}:E{row+1}', f'Company: {company_name}', company_format)
            worksheet.set_row(row, 18)
            row += 1
            
            for rec in records:
                worksheet.write(row, 0, rec.employee_id.id if rec.employee_id else rec.id, data_format)
                worksheet.write(row, 1, rec.employee_name or '', data_format)
                worksheet.write(row, 2, rec.identification_id or '', data_format)
                if rec.identification_expiry_date:
                    worksheet.write_datetime(row, 3, rec.identification_expiry_date, date_format)
                else:
                    worksheet.write(row, 3, '', data_format)
                worksheet.write(row, 4, company_name, data_format)
                worksheet.set_row(row, 16)
                row += 1
        
        workbook.close()
        
        with open(temp_file.name, 'rb') as f:
            file_data = base64.b64encode(f.read())
        
        attachment = self.env['ir.attachment'].create({
            'name': f'Document_Expiry_Report_{datetime.date.today().strftime("%Y%m%d")}.xlsx',
            'type': 'binary',
            'datas': file_data,
            'res_model': 'document.renewal',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        
        # Send email to group users
        self._send_report_email(attachment)
    
    def _send_report_email(self, attachment):
        """Send email with Excel report to group users"""
        group = self.env.ref('saddad.group_saddad_pending_to_renew', raise_if_not_found=False)
        if not group:
            return
        
        recipients = [user.partner_id.email for user in group.users if user.partner_id.email]
        if not recipients:
            return
        
        mail_values = {
            'subject': f'Document Expiry Report - {datetime.date.today().strftime("%B %d, %Y")}',
            'body_html': f'''
                <p>Dear Team,</p>
                <p>Please find attached the Document Expiry Report for {datetime.date.today().strftime("%B %d, %Y")}.</p>
                <p>This report contains employees whose documents are expiring soon and require renewal.</p>
                <p>Best regards,<br/>System Administrator</p>
            ''',
            'email_to': ','.join(recipients),
            'attachment_ids': [(4, attachment.id)]
        }
        
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()

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
            'state': 'draft',
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
        return document_renew_expense

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
                expense = self.create_expense(rec)
                expense.action_confirm()
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

