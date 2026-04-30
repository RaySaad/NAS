# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountPaymentExt(models.Model):
    _inherit = 'account.payment'

    saddad_service_id = fields.Many2one('saddad.services')

