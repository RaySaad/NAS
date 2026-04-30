# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError


class FleetVehicleExt(models.Model):
    _inherit = "fleet.vehicle"

    def _compute_morror_all(self):
        morror = self.env['morror']
        for record in self:
            record.morro_count = morror.search_count([('fleet_id', '=', record.id)])

    morro_count = fields.Integer(compute="_compute_morror_all", string='morror Count')

    def action_open_morror(self):
        return {
            'name': _('Morror'),
            'view_mode': 'list,form,kanban,graph,pivot,activity',
            'res_model': 'morror',
            'type': 'ir.actions.act_window',
            "context": {'default_fleet_id': self.id, 'default_expense_type': 'traffic_violation',
                        'default_employee_id': self.custom_driver_id.id if self.custom_driver_id else False,
                        'default_deduction_date': fields.date.today(),
                        'default_fleet_readonly': True},
            'domain': [('fleet_id', '=', self.id)],
        }
