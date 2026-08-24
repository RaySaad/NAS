# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import json


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    year_open_id = fields.Many2one('fiscal.year', 'open year')
    year_close_id = fields.Many2one('fiscal.year', 'close year')
