# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MuqeemExpenseExportWizard(models.TransientModel):
    _name = 'muqeem.expense.export.wizard'
    _description = 'Muqeem Expense Export Wizard'

    date = fields.Date(required=True, default=fields.Date.today)
    expense_nature = fields.Selection([('prepaid', 'Prepaid'), ('accrual', 'Accrual')],
                                      string='Expense Nature', required=True,
                                      default="accrual")
    amortization_method = fields.Selection([('monthly', 'Monthly'), ('on_time', 'On Time')],
                                           string='Amortization Method', required=True)
    reference = fields.Char(required=True)
    journal_id = fields.Many2one("account.journal", string="Amortization Journal",
                                 domain="[('type', 'in', ['purchase', 'general']),('company_id','=',company_id)]",
                                 required=True)
    type_jv = fields.Selection([('all_line', 'JV for all line'), ('each_line', 'JV for each line')],
                               default='each_line')
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    expense_type_id = fields.Many2one("account.expense.type", string="Expense Type",
                                      domain=[('state', '=', 'confirmed')])
    wizard_line_ids = fields.One2many('muqeem.expense.export.wizard.line', 'wizard_id',
                                      string="Expense Lines")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Auto generate reference
        res['reference'] = f'MUQEEM-{fields.Date.today().strftime("%Y%m%d")}-{self.env.user.id}'
        # Auto set journal
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if journal:
            res['journal_id'] = journal.id
        return res

    @api.model
    def create(self, vals):
        """Create wizard"""
        res = super().create(vals)
        return res

    def action_confirm(self):
        """Confirm wizard and create Expense Transaction"""
        if not self.wizard_line_ids:
            raise ValidationError('No lines to export')

        expense_detail_lines = []
        for line in self.wizard_line_ids:
            # Validate required fields
            if not line.prepaid_expense_account_id:
                raise ValidationError(
                    f"Line '{line.description}' is missing Prepaid/Accrual Expense Account."
                )
            if not line.expense_account_id:
                raise ValidationError(
                    f"Line '{line.description}' is missing Expense Account."
                )

            expense_detail_lines.append((0, 0, {
                'description': line.description,
                'employee_id': line.employee_id.id if line.employee_id else False,
                'operating_unit_id': line.operating_unit_id.id if line.operating_unit_id else False,
                'prepaid_expense_account_id': line.prepaid_expense_account_id.id,
                'expense_account_id': line.expense_account_id.id,
                'analytic_distribution': line.analytic_distribution,
                'start_date': line.start_date,
                'end_date': line.end_date,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'price_total': line.price_total,
                'company_id': line.company_id.id if line.company_id else False,
                'expense_type_id': line.expense_type_id.id if line.expense_type_id else False,
            }))

        expense_transaction = self.env['account.expense.transaction'].create({
            'date': self.date,
            'expense_nature': self.expense_nature,
            'amortization_method': self.amortization_method,
            'reference': self.reference,
            'journal_id': self.journal_id.id,
            'type_jv': self.type_jv,
            'company_id': self.company_id.id,
            'expense_detail_ids': expense_detail_lines,
        })

        # Mark original lines as exported
        original_line_ids = self.wizard_line_ids.mapped('expense_line_id')
        original_line_ids.write({'exported_to_transaction': True})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.expense.transaction',
            'res_id': expense_transaction.id,
            'view_mode': 'form',
            # 'view_type': 'form',
            'target': 'new',
        }


class MuqeemExpenseExportWizardLine(models.TransientModel):
    _name = 'muqeem.expense.export.wizard.line'
    _description = 'Export Wizard Line'

    wizard_id = fields.Many2one('muqeem.expense.export.wizard', ondelete='cascade')
    description = fields.Char()
    expense_type_id = fields.Many2one("account.expense.type", string="Expense Type")
    employee_id = fields.Many2one('hr.employee', string='Employee')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    operating_unit_id = fields.Many2one('operating.unit', string='Operating Unit')
    expense_account_id = fields.Many2one("account.account", string="Expense Account")
    prepaid_expense_account_id = fields.Many2one("account.account", string="Prepaid/Accrual Expense Account")
    start_date = fields.Date("Start Date")
    end_date = fields.Date("End Date")
    quantity = fields.Float("Quantity")
    price_unit = fields.Float("Amount")
    price_total = fields.Float("Total")
    analytic_distribution = fields.Json()
    company_id = fields.Many2one('res.company', 'Company', related='wizard_id.company_id')
    expense_line_id = fields.Many2one('document.renew.expense.line', string='Expense Line')