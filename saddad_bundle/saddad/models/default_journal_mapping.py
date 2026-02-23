# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class DefaultJournalMapping(models.Model):
    _name = 'default.journal.mapping'
    _description = "Default Bank Mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'company_id'

    def company_domain(self):
        domain = [('id', 'in', self.env.user.company_ids.ids)]
        return domain

    bank_journal_id = fields.Many2one('account.journal', 'Account Journal',
                                      domain=[('type', '=', 'bank')])
    company_id = fields.Many2one('res.company', 'Company', domain=company_domain, default=lambda l: l.env.company.id, readonly=True)
