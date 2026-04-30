# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class EmployeeDeductionsViolationsEXT(models.Model):
    _inherit = "employee.deductions.violations"

    morror_id = fields.Many2one('morror')

    def action_open_morror(self):
        return {
            'name': 'Morror',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'morror',
            'res_id': self.morror_id.id

        }

    def update_employee_deductions_violations(self):
        recs = self.env['employee.deductions.violations'].search([('morror_id', '!=', False)])
        for rec in recs:
            morror_recs = self.env['morror'].search([('id', '=', rec.morror_id.id)])
            for morror_rec in morror_recs:
                morror_lines = morror_rec.morror_line_ids.filtered(lambda l: l.product_id == rec.product_id)
                if len(morror_lines) == 1:
                    rec.update({
                        'total': morror_lines.total_amount,
                        'amount': morror_lines.total_amount
                    })
                    rec.env.cr.commit()
                if len(morror_lines) > 1:
                    product_id = morror_lines.mapped('product_id')
                    deduction_records = self.env['employee.deductions.violations'].search(
                        [('morror_id', '!=', False), ('product_id', '=', product_id[0].id),
                         ('morror_id', '=', morror_lines[0].morror_id.id)])
                    for deduction, morror_line in zip(deduction_records, morror_lines):
                        deduction.update({
                            'total': morror_line.total_amount,
                            'amount': morror_line.total_amount
                        })
                        deduction.env.cr.commit()
