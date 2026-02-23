# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo import models, fields, api, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # =======================================
    # New Fields
    # =======================================
    arabic_name = fields.Char(required=True)
    sponsor = fields.Many2one('hr.sponsors', string='Sponsor')
    sponsor_id = fields.Char(related='sponsor.identification_no')

    # =======================================
    # Override Fields
    # =======================================

    registration_number = fields.Char('Registration Number of the Employee',
                                      groups="hr.group_hr_user", copy=False)

    # =======================================
    # Compute Methods
    # =======================================

    @api.depends('name')
    def _compute_display_name(self):
        for i in self:
            i.display_name = f"[{i.registration_number}] {i.name}"


    #=======================================
    # ORM Methods
    #=======================================

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [vals.copy() for vals in vals_list]

        for vals in vals_list:
            vals['registration_number'] = self.env['ir.sequence'].next_by_code('seq.employee.number')
            if self.search([('registration_number', '=', vals['registration_number'])]):
                raise ValidationError(_('This Employee number is already assigned to an Employee'))
        return super(HrEmployee, self).create(vals_list)
