# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductTemplate(models.Model):

    _inherit = "product.template"


    expense_type_id = fields.Many2one("account.expense.type", string="Expense Type",
                                      domain="[('state', '=', 'confirmed')]")
