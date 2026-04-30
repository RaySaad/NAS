# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ProductCategoryMapping(models.Model):
    _name = 'product.category.mapping'
    _description = 'Product Category Mapping'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('name')
    morror_category_ids = fields.Many2many('product.category', relation='morror_product_category_rel',)
    # morror_expense_ids = fields.Many2many('product.category', 'expense')
