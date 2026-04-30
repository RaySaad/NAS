# -*- coding: utf-8 -*-
from odoo import models, fields, exceptions, api, _
from datetime import date
from odoo.exceptions import ValidationError

try:
    from hijri_converter import Gregorian
except ImportError:
    Gregorian = None


def convert_to_hijri(gregorian_date):
    """Convert Gregorian date to Hijri format"""
    if not gregorian_date:
        return False
    try:
        hijri_date = Gregorian(gregorian_date.year, gregorian_date.month, gregorian_date.day).to_hijri()
        return f"{hijri_date.day:02d}/{hijri_date.month:02d}/{hijri_date.year:04d}"
    except:
        return False


class EmployeeRecord(models.Model):
    _name = 'employee.record'
    _description = 'Employee Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'employee_id'
    _rec_names_search = ['employee_name', 'employee_number']

    identification_id = fields.Char(string="Iqama Number")
    start_date = fields.Date(tracking=True)
    start_date_hijri = fields.Char(string="Start Date (Hijri)", tracking=True)
    identification_expiry_date = fields.Date(tracking=True)
    identification_expiry_date_hijri = fields.Char(string="Expiry Date (Hijri)", tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    employee_name = fields.Char()
    employee_type = fields.Selection([
        ('internal', 'Internal'),
        ('external', 'External')
    ])
    employee_id = fields.Many2one('hr.employee')
    # sponsor_id = fields.Char(string="Sponsor Name")
    employee_number = fields.Char(string="Employee Number")

    operating_unit_id = fields.Many2one(
        comodel_name="operating.unit",
        string="Operating Unit",
        check_company=True,
    )

    @api.onchange('start_date', 'identification_expiry_date')
    def _onchange_dates(self):
        if self.start_date and self.identification_expiry_date and self.identification_expiry_date <= self.start_date:
            raise ValidationError("Identification expiry date must be greater than start date")

        self.start_date_hijri = convert_to_hijri(self.start_date) if self.start_date else False
        self.identification_expiry_date_hijri = convert_to_hijri(
            self.identification_expiry_date) if self.identification_expiry_date else False

    # @api.onchange('employee_id')
    # def _onchange_employee_id(self):
    #     if self.employee_id:
    #         self.employee_name = self.employee_id.display_name
    #         self.employee_number = self.employee_id.registration_number
    #         self.company_id = self.employee_id.company_id.id
    #         self.identification_id = self.employee_id.identification_id
    #         self.operating_unit_id = self.employee_id.operating_unit_id
    #         # self.sponsor_id = self.employee_id.sponsor.identification_no if self.employee_id.sponsor else None

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.employee_name = self.employee_id.display_name
            self.employee_number = self.employee_id.registration_number
            self.company_id = self.employee_id.company_id.id
            self.identification_id = self.employee_id.identification_id
            self.operating_unit_id = self.employee_id.operating_unit_id

    def sync_employees_from_hr(self):
        employees = self.env['hr.employee'].search([('identification_id', '!=', False)])
        existing_employee_ids = self.search([('identification_id', '!=', False)]).mapped('employee_id')

        for employee in employees:
            if employee.id not in existing_employee_ids.ids:
                self.create({
                    'employee_id': employee.id,
                    'employee_name': employee.display_name,
                    'identification_id': employee.identification_id,
                    'employee_type': 'internal',
                    # 'sponsor_id': employee.sponsor.identification_no if employee.sponsor else None,
                    'company_id': employee.company_id.id,
                    'employee_number': employee.registration_number
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
        update_vals['employee_name'] = employee.display_name
        update_vals['identification_id'] = employee.identification_id or ''
        # update_vals['sponsor_id'] = employee.sponsor.identification_no if employee.sponsor else None
        update_vals['company_id'] = employee.company_id.id
        update_vals['employee_number'] = employee.registration_number

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

    def action_bulk_update_from_hr(self):
        updated_count = 0
        for record in self:
            if record.employee_id:
                employee = record.employee_id
                update_vals = {
                    'employee_name': employee.display_name,
                    'identification_id': employee.identification_id or '',
                    # 'sponsor_id': employee.sponsor.identification_no if employee.sponsor else None,
                    'company_id': employee.company_id.id,
                    'employee_number': employee.registration_number
                }
                record.write(update_vals)
                updated_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'{updated_count} records updated successfully!',
                'type': 'success',
            }
        }

    @api.constrains('identification_id')
    def identification_id_domain(self):
        for rec in self:
            old_rec = self.search([
                ('id', "!=", rec.id),
                ('identification_id', '=', rec.identification_id),
                ('company_id', '=', rec.company_id.id)
            ])
            if old_rec:
                raise exceptions.ValidationError(_('Identification ID must be unique!'))

    @api.constrains('employee_id')
    def _constrains_employee_id(self):
        for rec in self:
            old_rec = self.search([
                ('id', "!=", rec.id),
                ('employee_id', '=', rec.employee_id.id)
            ])
            if old_rec:
                raise exceptions.ValidationError(_('Employee must be unique!'))
