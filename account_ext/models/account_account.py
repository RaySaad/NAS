# -*- coding:utf-8 -*-

import logging
from odoo.exceptions import ValidationError
from odoo import api, models, fields, _

_logger = logging.getLogger(__name__)

class AccountAccount(models.Model):
    _inherit = 'account.account'

    account_type = fields.Selection(selection_add=[
        ('main_account', 'Main')
    ], ondelete={
        'main_account': 'cascade'
    })

    internal_group = fields.Selection(selection_add=[
        ('main', 'Main')
    ], ondelete={
        'main': 'cascade'
    })
    parent_account = fields.Many2one('account.account', domain="[('account_type', '=', 'main_account')]")
    level = fields.Integer('Account Level', compute="_compute_level", store=True)


    @api.depends('parent_account')
    def _compute_level(self):
        for rec in self:
            parent_level = rec.parent_account.level or 0
            rec.level = parent_level + 1

    @api.onchange('account_type')
    def _onchange_account_type(self):
        super(AccountAccount, self)._onchange_account_type()
        if self.internal_group == 'main':
            self.tax_ids = False
        if self.account_type == 'main_account':
            self.parent_account = False
