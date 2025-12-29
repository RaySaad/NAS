# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import json


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    expense_nature = fields.Selection([('normal', 'Normal'), ('prepaid', 'Prepaid')],
                                      string='Type Bills', required=True,
                                      default="normal")

    expense_type_id = fields.Many2one("account.expense.type",
                                      string="Expense Type",
                                      domain=[('state', '=', 'confirmed')])

    start_date = fields.Date("Start Date ")
    end_date = fields.Date("End Date ")

    @api.onchange('expense_nature')
    def onchange_expense_nature(self):
        for rec in self:
            if rec.expense_nature != 'prepaid':
                for invoice_line in rec:
                    invoice_line.end_date = False
                    invoice_line.start_date = False
                    invoice_line.expense_type_id = False
            if rec.expense_nature == 'prepaid':
                for invoice_line in rec:
                    invoice_line.account_id = invoice_line.product_id.expense_type_id.prepaid_expense_account_id.id
                    invoice_line.expense_type_id = invoice_line.product_id.expense_type_id.id

    @api.onchange('expense_type_id')
    def onchange_expense_type(self):
        for rec in self:
            if rec.expense_type_id:
                for invoice_line in rec:
                    invoice_line.account_id = invoice_line.expense_type_id.prepaid_expense_account_id.id

    @api.onchange('product_id')
    def onchange_product_id_expense(self):
        for rec in self:
            if rec.product_id and rec.expense_nature == 'prepaid':
                rec.expense_type_id = rec.product_id.expense_type_id.id
