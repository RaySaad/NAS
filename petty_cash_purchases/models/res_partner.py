from odoo import api, fields, Command, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    petty_cash_account = fields.Boolean()