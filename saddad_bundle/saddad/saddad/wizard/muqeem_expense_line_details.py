from odoo import models, fields


class MuqeemExpenseLineDetail(models.TransientModel):
    _name = 'muqeem.expense.line.details'
    _description = 'Same Invoice Expense Lines'

    expense_number = fields.Char(string="Expense Number")
    employee_id = fields.Many2one('hr.employee')
    identification_id = fields.Char(string='Iqama Number')
    company_id = fields.Many2one('res.company')
    status = fields.Char(string='Status')
    unit_price = fields.Float(string='Unit Price')
    remarks = fields.Char(string='Remarks')
