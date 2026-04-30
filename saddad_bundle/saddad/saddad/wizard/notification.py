from odoo import models, fields


class Notifications(models.TransientModel):
    _name = 'show.notification'
    _description = 'Show Notification Wizard'

    name = fields.Char(string="Name")
    active_model_id = fields.Integer(string="Active Model ID")
    active_model_name = fields.Char(string="Active Model Name")

    def close_wizard(self):
        # Close the wizard
        return {'type': 'ir.actions.act_window_close'}
