# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import re


class RenewalDocumentType(models.Model):
    _name = 'renewal.document.type'
    _description = 'Renewal Document Type'

    name = fields.Char('Name', required=True, copy=False, default='Iqama Renewal')
    amount = fields.Float('Amount')
    employee_emails_ids = fields.Many2many('hr.employee', string='Email', domain="[('work_email', '!=', False)]")
    period = fields.Selection([
        ('3month', '3 Months'),
        ('6month', '6 Months'),
        ('9month', '9 Months'),
        ('1year', '1 year')], string='Period')

    type = fields.Selection([
        ('work_permit', 'Work Permit'),
        ('iqama_renewal', 'Iqama Renewal'),
        ('other', 'Other')], string='Type')

    @api.onchange('type', 'period')
    def onchange_type(self):
        if self.type == 'iqama_renewal':
            self.name = 'Iqama Renewal'

        if self.name and self.type == 'iqama_renewal' and self.period:
            self.name = "Iqama Renewal (for " + self.period + ")"

        if self.type == 'work_permit':
            self.name = 'Work Permit'

        if self.name and self.type == 'work_permit' and self.period:
            self.name = "Work Permit (for " + self.period + ")"

        if self.type == 'other':
            self.name = 'Fee For Family Iqama'
        if self.name and self.type == 'other' and self.period:
            self.name = "Fee For Family Iqama (for " + self.period + ")"
