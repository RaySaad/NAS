# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MuqeemGenerateExpenseWizard(models.TransientModel):
    _name = 'muqeem.generate.expense.wizard'
    _description = 'Generate Expenses Wizard'

    batch_id = fields.Many2one(
        'document.renew.expense.batch',
        string='Batch',
        required=True
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True
    )
    iqama_period = fields.Selection([
        ('3month', '3 Months'),
        ('6month', '6 Months'),
        ('9month', '9 Months'),
        ('1year', '1 Year'),
    ], string='Iqama Period', required=True)
    date = fields.Date(
        string='Default Date',
        required=True
    )
    line_ids = fields.One2many(
        'muqeem.generate.expense.wizard.line',
        'wizard_id',
        string='Employees'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        batch_id = self.env.context.get('default_batch_id')
        if batch_id:
            batch = self.env['document.renew.expense.batch'].browse(batch_id)
            # get employees who already have expenses in payment state
            # and not already in this batch
            expenses = self.env['document.renew.expense'].search([
                ('state', '=', 'payment'),
                ('batch_id', '=', False),
            ])
            lines = []
            for expense in expenses:
                lines.append((0, 0, {
                    'employee_id': expense.employee_id.id,
                    'identification_id': expense.identification_id,
                    'iqama_expiry_date': expense.iqama_expiry_date,
                    'expense_id': expense.id,
                    'selected': True,
                    'employee_code': expense.employee_id.employee_number,
                }))
            res['line_ids'] = lines
        return res

    def action_confirm(self):
        self.ensure_one()
        selected_lines = self.line_ids.filtered(lambda l: l.selected)
        if not selected_lines:
            raise ValidationError(_('Please select at least one employee.'))
        for line in selected_lines:
            line.expense_id.write({'batch_id': self.batch_id.id})
        return {'type': 'ir.actions.act_window_close'}


class MuqeemGenerateExpenseWizardLine(models.TransientModel):
    _name = 'muqeem.generate.expense.wizard.line'
    _description = 'Generate Expense Wizard Line'

    wizard_id = fields.Many2one(
        'muqeem.generate.expense.wizard',
        string='Wizard'
    )
    selected = fields.Boolean(
        string='Select',
        default=True
    )
    employee_id = fields.Many2one(
        'employee.record',
        string='Employee'
    )
    employee_code = fields.Char(
        string='Employee Code',
        related='employee_id.employee_number',
        store=True
    )
    identification_id = fields.Char(
        string='Iqama Number'
    )
    iqama_expiry_date = fields.Date(
        string='Iqama Expiry Date'
    )
    expense_id = fields.Many2one(
        'document.renew.expense',
        string='Expense'
    )
