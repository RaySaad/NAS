# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError
from lxml import etree
from markupsafe import Markup


class SaddadServices(models.Model):
    _name = 'saddad.services'
    _description = "Saddad Services"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'serial_number'
    _order = 'id desc'

    @api.depends('service_line_ids')
    def _compute_price(self):
        total_value = 0
        vat = 0
        for rec in self.service_line_ids:
            total_value += rec.unit_price
            vat += rec.price_tax
        self.unit_price = total_value
        self.vat_amount = vat
        self.total_amount = vat + total_value

    @api.depends('service_line_ids')
    def _compute_product(self):
        if self.service_line_ids and len(self.service_line_ids) == 1:
            self.product_id = self.service_line_ids.product_id.name
        if self.service_line_ids and len(self.service_line_ids) > 1:
            self.product_id = self.service_line_ids[0].product_id.name + ' ' + 'Count' + ' ' + '[' + str(
                len(self.service_line_ids)) + ']'

    @api.depends('service_line_ids')
    def _compute_remarks(self):
        for rec in self:
            all_remarks = ' '
            for service in rec.service_line_ids:
                if service.remarks:
                    all_remarks = all_remarks + ' ' + service.remarks
            rec.remarks = all_remarks

    def compute_attachment_number(self):
        for rec in self:
            attachments = self.env['ir.attachment'].search(
                [('res_model', '=', 'saddad.services'),
                 ('res_id', '=', rec.id)])
            if attachments:
                rec.attachment_number = len(attachments)
            else:
                rec.attachment_number = 0

    def default_bank_journal(self):
        bank_mapping = self.env['default.journal.mapping'].search([('company_id', '=', self.env.company.id)])
        if bank_mapping:
            return bank_mapping.bank_journal_id.id

    name = fields.Char(string="Description", required=True)
    serial_number = fields.Char()
    payment_type = fields.Selection([
        ('direct_payment', 'Direct Payment'),
        ('with_jv', 'With JV')
    ], string='Payment Type', required=True, default='direct_payment')
    account_id = fields.Many2one('account.account', string='Account')
    biller_id = fields.Many2one('billers', ondelete='restrict')
    bank_journal_id = fields.Many2one('account.journal', 'Account Journal',
                                      domain=[('type', '=', 'bank')], default=default_bank_journal)
    date = fields.Date(readonly=True, default=fields.Date.context_today,
                       string="Date")
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True,
                                  default=lambda self: self.env.company.currency_id)

    unit_price = fields.Monetary("Untaxed Amount", store=True, currency_field='currency_id',
                                 compute='_compute_price')
    total_amount = fields.Monetary("Total Amount", store=True, currency_field='currency_id',
                                   compute='_compute_price')
    vat_amount = fields.Monetary("Tax Amount", store=True, currency_field='currency_id',
                                 compute='_compute_price')
    product_id = fields.Char(string="Product", store=True, compute='_compute_product')
    service_line_ids = fields.One2many('saddad.services.line', 'service_id')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id)
    attachment_number = fields.Integer('Attachment Number', compute='compute_attachment_number')
    account_move_id = fields.Many2one('account.move', ondelete='cascade')
    payment_id = fields.Many2one('account.payment', ondelete='cascade')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('reviewed', 'Reviewed'),
        ('financial_approval', 'Financial Approval'),
        ('gm', 'GM'),
        ('pending_payment', 'Pending Payment'),
        ('refused', 'Refused'),
        ('done', 'Done'),
        ('posted', 'Posted'),
        ('cancel', 'Canceled'),
    ], default='draft', tracking=True)
    record_url = fields.Char(string="URL")
    is_gm_user = fields.Boolean(string='Is GM User', compute="_compute_gm_user")
    remarks = fields.Char(compute="_compute_remarks", store=True)

    def _compute_gm_user(self):
        if self.env.user.has_group('saddad.group_saddad_gm'):
            self.is_gm_user = True
        else:
            self.is_gm_user = False

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(SaddadServices, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                          submenu=submenu)
        if self.env.user.has_group('saddad.group_saddad_accountant') and not self.env.user.has_group(
                'base.group_system'):
            root = etree.fromstring(res['arch'])
            root.set('create', 'false')
            res['arch'] = etree.tostring(root)
        return res

    def attach_document(self, **kwargs):
        pass

    def action_confirm(self):
        self.write({
            'state': 'reviewed'
        })

    def action_review(self):
        self.write({
            'state': 'financial_approval'
        })
        gm_group = self.env.ref('saddad.group_saddad_financial_approval', raise_if_not_found=False)
        if gm_group:
            self.send_approval_email(gm_group)


    def action_financial_approval(self):
        self.write({
            'state': 'gm'
        })
        gm_group = self.env.ref('saddad.group_saddad_gm', raise_if_not_found=False)
        if gm_group:
            self.send_approval_email(gm_group)

    def gm_approval(self):
        self.write({
            'state': 'pending_payment'
        })
        accountant_group = self.env.ref('saddad.group_saddad_accountant', raise_if_not_found=False)
        if accountant_group:
            self.send_approval_email(accountant_group)

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

        template = self.env.ref('saddad.saddad_services_email_template', raise_if_not_found=False)
        if template:
            template.sudo().email_to = ','.join(recipients)
            template.sudo().send_mail(self.id, force_send=True)

        # Post message in chatter
        self.message_post(
            body=f'Notification sent to {email_group.name} group. Recipients: {", ".join(recipients)}',
            message_type='notification'
        )

    def action_cancel(self):
        # Check for related payments
        if self.payment_id and self.payment_id.state == 'draft':
            self.payment_id.action_cancel()
        elif self.payment_id and self.payment_id.state in ('in_process','posted', 'sent', 'reconciled'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Payment is in process. Cannot cancel the transaction.',
                    'type': 'warning',
                }
            }
        self.write({
            'state': 'cancel',
            'payment_id': False
        })
        self.service_line_ids.write({
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

    def action_open_journal_entry(self):
        """Open the related journal entry"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_get_attachment_view(self):
        res_ids = self.service_line_ids.mapped('id')
        res_ids.append(self.id)
        res = self.env['ir.actions.act_window']._for_xml_id('base.action_attachment')
        res['domain'] = [('res_model', 'in', ('saddad.services', 'saddad.services.line')),
                         ('res_id', 'in', res_ids)]
        res['context'] = {
            'create': False,
            'edit': False,
        }
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            name = self.env['ir.sequence'].next_by_code('saddad.services')
            vals.update({
                'serial_number': name,
            })
        records = super(SaddadServices, self).create(vals_list)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in records:
            record.record_url = f"{base_url}/web#id={record.id}&model={self._name}&view_type=form"
        return records

    def _create_move_lines(self):
        lines = []
        for line in self.service_line_ids:
            i = 1
            while (i != 3):
                if i == 1:
                    lines.append((0, 0, {
                        'account_id': line.product_id.property_account_expense_id.id,
                        'name': str(line.service_id.biller_id.name) + str(line.product_id.name),
                        'currency_id': line.currency_id.id,
                        'debit': line.total_amount,
                        'credit': 0.0,
                    }))
                else:
                    lines.append((0, 0, {
                        'account_id': self.bank_journal_id.default_account_id.id,
                        'name': str(line.service_id.biller_id.name) + str(line.product_id.name),
                        'currency_id': line.currency_id.id,
                        'debit': 0.0,
                        'credit': line.total_amount,
                    }))
                i += 1
        return lines

    def create_jv(self):
        """Create Journal Entry for With JV payment type"""
        if not self.account_id:
            raise ValidationError('Account is required for JV creation')
        
        available_lines = self.service_line_ids.filtered(lambda l: l.is_paid == True)
        if not available_lines:
            raise ValidationError('No paid lines available to create JV')
        
        move_lines = []
        for line in available_lines:
            # Credit entry - Product income account
            move_lines.append((0, 0, {
                'account_id': line.product_id.property_account_income_id.id or line.product_id.categ_id.property_account_income_categ_id.id,
                'name': f"{self.name} - {line.product_id.name}",
                'credit': line.total_amount,
                'debit': 0.0,
            }))
            
            # Debit entry - Selected account
            move_lines.append((0, 0, {
                'account_id': self.account_id.id,
                'name': f"{self.name} - {line.product_id.name}",
                'debit': line.total_amount,
                'credit': 0.0,
            }))
        
        # Create journal entry in draft state
        self.account_move_id = self.env['account.move'].create({
            'move_type': 'entry',
            'date': self.date,
            'ref': self.serial_number,
            'journal_id': self.env['account.journal'].search([('type', '=', 'general')], limit=1).id,
            'line_ids': move_lines,
        })
        
        # Return action to redirect to the journal entry
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def create_payment(self):
        if self.bank_journal_id:
            available_lines = self.service_line_ids.filtered(lambda l: l.payment_created == False and l.is_paid == True)
            if not available_lines:
                raise ValidationError('No Lines available to create payment')
            self.payment_id = self.env['account.payment'].create({
                'partner_id': self.biller_id.partner_id.id,
                'payment_type': 'outbound',
                'amount': sum(available_lines.mapped('total_amount')),
                'journal_id': self.bank_journal_id.id,
                'date': fields.Date.today(),
                'state': 'draft',
                'saddad_service_id': self.id
            }).id
        else:
            raise ValidationError('Bank Journal Missing')
        return {
            'name': self.payment_id.name,
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'account.payment',
            'domain': [('saddad_service_id', '=', self.id)],
        }

    def action_open_account_payment(self):
        self.ensure_one()
        return {
            'name': self.payment_id.name,
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'account.payment',
            'domain': [('saddad_service_id', '=', self.id)],

        }

    def unlink(self):
        """ Override unlink to stop the deletion on records if not in draft state. """
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError('You can delete record only in draft state')
        res = super(SaddadServices, self).unlink()
        return res


class SaddadServicesLines(models.Model):
    _name = 'saddad.services.line'
    _description = "Saddad Services Line"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _product_domain(self):
        return [
            '&',  # AND condition between the first condition and the result of the OR condition
            ('detailed_type', '=', 'service'),
            '|',  # OR condition for company_id
            ('company_id', '=', self.env.company.id),
            ('company_id', '=', False)
        ]

    date = fields.Date(readonly=True, default=fields.Date.context_today, string="Date")
    service_id = fields.Many2one('saddad.services', ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", ondelete='restrict', required=True)
    invoice_number = fields.Char('Invoice Number')
    analytic_account_id = fields.Many2one("account.analytic.account", string="Analytic Account")
    attachment_id = fields.Binary(string='Attachment')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    unit_price = fields.Float("Invoice Amount", required=True, store=True, readonly=False, tracking=True,
                              related='product_id.list_price')
    remarks = fields.Char()
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True,
                                  default=lambda self: self.env.company.currency_id)
    total_amount = fields.Monetary("Total", store=True, currency_field='currency_id',
                                   compute='_compute_amount')

    is_paid = fields.Boolean('Paid')
    vat_id = fields.Many2many('account.tax')
    attachment_number = fields.Integer('Attachment Number', compute='_compute_attachment_number')
    price_tax = fields.Float(compute='_compute_amount', string='Tax', store=True)
    payment_created = fields.Boolean(default=False)

    def _compute_attachment_number(self):
        attachment_data = self.env['ir.attachment'].read_group([
            ('res_model', '=', 'saddad.services.line'),
            ('res_id', 'in', self.ids)], ['res_id'], ['res_id'])
        attachment = dict((data['res_id'], data['res_id_count']) for data in attachment_data)
        for doc in self:
            doc.attachment_number = attachment.get(doc.id, 0)

    def action_get_attachment_view(self):
        self.ensure_one()
        res = self.env['ir.actions.act_window']._for_xml_id('base.action_attachment')
        res['domain'] = [('res_model', '=', 'saddad.services.line'), ('res_id', 'in', self.ids)]
        res['context'] = {'default_res_model': 'saddad.services.line', 'default_res_id': self.id}
        return res

    def service_paid(self):
        if not self.service_id.bank_journal_id:
            raise ValidationError('You need to select bank journal to process a payment')
        for rec in self:
            rec.is_paid = True
        if all(self.service_id.service_line_ids.mapped('is_paid')):
            self.service_id.state = 'done'

    @api.onchange('product_id')
    def change_product(self):
        if self.product_id:
            self.vat_id = self.product_id.taxes_id

    @api.depends('product_id', 'unit_price', 'vat_id')
    def _compute_amount(self):
        for line in self:
            taxes = line.vat_id.compute_all(**line._prepare_compute_all_values())
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'total_amount': taxes['total_included'],
            })

    def _prepare_compute_all_values(self):
        # Hook method to returns the different argument values for the
        # compute_all method, due to the fact that discounts mechanism
        # is not implemented yet on the purchase orders.
        # This method should disappear as soon as this feature is
        # also introduced like in the sales module.
        self.ensure_one()
        return {
            'price_unit': self.unit_price,
        }

    def write(self, vals):
        res = super(SaddadServicesLines, self).write(vals)
        self.env.cr.commit()
        # if set(vals) & set(self._get_tracked_fields()):
        #     self._track_changes(self.service_id)
        return res

    def _track_changes(self, field_to_track):
        message_id = field_to_track.message_post(
            body=f'{self._description} : {self.product_id.name} ').id
        trackings = self.env['mail.message'].search([('res_id', '=', self.id)]).filtered(
            lambda l: l.model == self.display_name.split(',')[0]).tracking_value_ids
        for tracking in trackings:
            tracking.write({
                'mail_message_id': message_id
            })

    def unlink(self):
        """ Override unlink to stop the deletion on records if not in draft state. """
        for rec in self:
            if rec.is_paid:
                raise ValidationError('You can delete record only if not paid')
        res = super(SaddadServicesLines, self).unlink()
        return res
