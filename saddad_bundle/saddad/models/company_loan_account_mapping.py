# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class CompanyLoanAccountMapping(models.Model):
    _name = 'company.loan.account.mapping'
    _description = "Company Loan Account Mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'company_id'

    def company_domain(self):
        domain = [('id', 'in', self.env.user.company_ids.ids)]
        return domain

    def account_domain(self):
        domain = [('debit_credit', '=', 'debit'), ('company_id', '=', self.env.company.id)]
        return domain

    loan_account_id = fields.Many2one('account.account', 'Account')
    company_id = fields.Many2one('res.company', 'Company', domain=company_domain, default=lambda l: l.env.company.id,
                                 readonly=True)

    _sql_constraints = [
        ('uniq_company_id', 'unique (company_id)',
         "Mapping for this company already done you can't assign same company two employee loan accounts!"),
    ]
