# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountMoveExt(models.Model):
    _inherit = 'account.move'

    expense_id = fields.Many2one('document.renew.expense')
