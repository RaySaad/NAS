# -*- coding: utf-8 -*-
from odoo import models, fields, api


class EmployeeRecord(models.Model):
    _name = 'employee.record'
    _description = 'Employee Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'employee_name'

    identification_id = fields.Char(string="Iqama Number")
    start_date = fields.Date()
    identification_expiry_date = fields.Date(tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    employee_name = fields.Char()
    employee_type = fields.Selection([
        ('internal', 'Internal'),
        ('external', 'External')
    ])
    employee_id = fields.Many2one('hr.employee')
    sponsor_id = fields.Char(string="Sponsor Name")

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.employee_name = self.employee_id.name
            self.identification_id = self.employee_id.identification_id

    def sync_employees_from_hr(self):
        employees = self.env['hr.employee'].search([('identification_id','!=', False)])
        existing_employee_ids = self.search([('identification_id','!=', False)]).mapped('employee_id.id')
        
        for employee in employees:
            if employee.id not in existing_employee_ids:
                self.create({
                    'employee_id': employee.id,
                    'employee_name': employee.name,
                    'identification_id': employee.identification_id,
                    'employee_type': 'internal',
                })

    @api.model
    def action_pull_employees(self):
        self.sync_employees_from_hr()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_update_from_hr(self):
        if not self.employee_id:
            return
        
        employee = self.employee_id
        update_vals = {}
        
        if self.employee_name != employee.name:
            update_vals['employee_name'] = employee.name
        
        if self.identification_id != (employee.identification_id or ''):
            update_vals['identification_id'] = employee.identification_id or ''
        
        if update_vals:
            self.write(update_vals)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Record updated successfully!',
                    'type': 'success',
                    'next': {
                        'type': 'ir.actions.client',
                        'tag': 'reload',
                    }
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No changes found to update.',
                    'type': 'danger',
                }
            }

    _sql_constraints = [
        ('unique_identification_id', 'unique(identification_id)', 'Identification ID must be unique!'),
        ('unique_employee_id', 'unique(employee_id)', 'Employee must be unique!'),
    ]