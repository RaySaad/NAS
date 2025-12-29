# models/settings.py

from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	api_token = fields.Char(string="API Token", default="376a8202-9e40-4bdd-b8e5-0333f7e55c5b")

	def set_values(self):
		super(ResConfigSettings, self).set_values()
		self.env['ir.config_parameter'].sudo().set_param('employees_ext.hr_api_token', self.api_token)

	@api.model
	def get_values(self):
		res = super(ResConfigSettings, self).get_values()
		res.update(
			api_token=self.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')
		)
		return res