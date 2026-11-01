# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductCategoryExt(models.Model):
    _inherit = 'product.category'

    type = fields.Selection([
        ('traffic_violation', 'Traffic Violation'),
        ('driving_licence', 'Driving Licence'),
        ('motor_vehicle', 'Motor Vehicle'),
        ('muqeem_expenses', 'Muqeem Expenses')
    ])
