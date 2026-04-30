# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplateExt(models.Model):
    _inherit = 'product.template'

    renewal_item = fields.Boolean(string="Renewal Item", help="Renewal Item")
    renewal_type = fields.Selection([
        ('iqama_renewal', 'Iqama Renewal'),
        ('work_permit_renewal', 'Work Permit Renewal')
    ])
