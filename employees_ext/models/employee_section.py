from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class EmployeeSection(models.Model):
	_name = 'employee.section'
	_description = 'HR Employee Sections'
	_inherit = ['mail.thread', 'mail.activity.mixin']

	name = fields.Char(string='Section Name', required=True, tracking=True, translate=True)
	company_id = fields.Many2one(
		'res.company', string='Company',
		default=lambda self: self.env.company,
		required=True
	)

	def unlink(self):
		for section in self:
			linked_employees = self.env['hr.employee'].sudo().search([('employee_section', '=', section.id)])
			if linked_employees:
				raise ValidationError(_('You cannot delete this Section because it is already being used by employees.'))
		return super(EmployeeSection, self).unlink()

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if 'name' in vals:
				existing_section = self.env['employee.section'].sudo().search([('name', '=', vals['name'])], limit=1)
				if existing_section:
					raise ValidationError(_('A Section with the same name already exists. Please choose a different name.'))
		return super(EmployeeSection, self).create(vals_list)

	def write(self, vals):
		if 'name' in vals:
			for section in self:
				existing_section = self.env['employee.section'].sudo().search(
					[('name', '=', vals['name']), ('id', '!=', section.id)],
					limit=1
				)
				if existing_section:
					raise ValidationError(_('A Section with the same name already exists. Please choose a different name.'))
		return super(EmployeeSection, self).write(vals)