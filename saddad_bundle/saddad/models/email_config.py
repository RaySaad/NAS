# -*- coding: utf-8 -*-
from odoo import fields, models  #

'''imported models and fields classed to extend 
the functionality of those classes fields to extend fields class and create new 
fields and models class to create new models in database'''


class EmailConfigExt(models.Model):
    _inherit = "email.config"

    type = fields.Selection(
        selection_add=[
            ('pending_to_renew', 'Pending To Renew'), ('muqeem_expenses', 'Muqeem Expenses'), ('morror', 'Morror'), (
                'saddad_services', 'Saddad Services')])
    pending_to_renew_email_state = fields.Selection([
        ('hr_assistant_approval', 'Send Approval Email To Hr Assistant'),
        ('hr_approval', 'Send Approval Email To Hr'),
        ('gm_approval', 'Send Approval Email To GM'),
    ], string='Email State')
    muqeem_expense_email_state = fields.Selection([
        ('hr_assistant_approval', 'Send Approval Email To Hr Assistant'),
        ('hr_approval', 'Send Approval Email To Hr'),
        ('gm_approval', 'Send Approval Email To GM'),
        ('pending_payment', 'Send Approval Email To Payment Team'),
        ('expense_validation', 'Send Approval Email To Muqeem Validation Group'),
        ('post_entries', 'Send Approval Email To Post Entries Team')
    ], string='Email State')
    morror_email_state = fields.Selection([
        ('fleet_manager_approval', 'Send Approval Email To Fleet Manager'),
        ('gm_approval', 'Send Approval Email To GM'),
        ('pending_payment', 'Send Approval Email To Payment Team'),
        ('post_entries', 'Send Approval Email To Post Entries Team')
    ], string='Email State')
    saddad_services_email_state = fields.Selection([
        ('reviews', 'Send Approval Email For Review'),
        ('financial_approval', 'Send Approval Email For Financial Approval'),
        ('gm_approval', 'Send Approval Email To GM'),
        ('pending_payment', 'Send Approval Email To Payment Team'),
        ('create_payments', 'Send Notification To Create Payment Team')
    ], string='Email State')
    saddad_approval_company_ids = fields.Many2many('res.company', 'saddad_approval_companies')
