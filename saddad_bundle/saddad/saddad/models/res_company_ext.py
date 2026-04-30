# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    ptr_days = fields.Integer(string="Pending To Renew Days")