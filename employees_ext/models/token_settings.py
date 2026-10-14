# models/settings.py

from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	api_token = fields.Char(string="API Token", default="376a8202-9e40-4bdd-b8e5-0333f7e55c5b")

	def iap_action_view_my_services(self):
		"""Support retained pre-19 IAP settings views using the native 19 action.

		Odoo 19 replaced this object button with an action button. Older database
		views can still call it until the core IAP module's XML is upgraded.
		"""
		return self.env['ir.actions.actions']._for_xml_id('iap.iap_account_action')

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
