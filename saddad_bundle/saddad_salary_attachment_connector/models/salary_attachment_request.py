# -*- coding: utf-8 -*-
from odoo import models, fields


class HrSalaryAttachmentRequest(models.Model):
    _inherit = 'hr.salary.attachment.request'

    morror_id = fields.Many2one('morror', string="Morror Id")
    show_morror_button = fields.Boolean(default=False)

    def action_get_morror_view(self):
        morror = self.env['morror'].search([('loan_advance_request_id', '=', self.id)], limit=1)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Mirror View',
            'res_model': 'morror',
            'view_mode': 'form',
            'res_id': morror.id,
        }