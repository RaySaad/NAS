from odoo import models, fields, api, _
from odoo import fields, Command

class EmployeeExt(models.Model):
	_inherit = 'hr.employee'

	identification_id = fields.Char(string='Iqama No', groups="hr.group_hr_user", tracking=True)
	employee_section = fields.Many2one('employee.section', string="Employee Section", tracking=True)
	job_number = fields.Char(string="Job Number", tracking=True, translate=True)
	project_code = fields.Char(string="Project Code", tracking=True, translate=True)
	border_number = fields.Char(string="Border Number", tracking=True, translate=True)
	country_code = fields.Char(string="Country Code.", tracking=True, translate=True)
	employee_code = fields.Char(string="Employee Code", tracking=True, required=True)
	arrival_date = fields.Date(string="Arrival Date", tracking=True)
	profession_id = fields.Char("Profession for Employee")
	project_joining_date = fields.Date("Joining Date", tracking=True)
	job_title = fields.Char("Job Title", tracking=True)
	crm_id = fields.Char(string="CRM ID", readonly=True, tracking=True)
	user_name = fields.Char(string="User Name", readonly=True, tracking=True)
	customer_account = fields.Many2one('partner.subscription',string='Customer Contract', tracking=True)
	marital = fields.Selection(
		selection='_get_marital_status_selection',
		string='Marital Status',
		groups="hr.group_hr_user",
		default='single',
		required=True,
		tracking=True
	)

	def _get_marital_status_selection(self):
		return [
			('single', _('Single')),
			('married', _('Married')),
			('cohabitant', _('Legal Cohabitant')),
			('widower', _('Widower')),
			('divorced', _('Divorced')),
			('other', 'Other')
		]

	_sql_constraints = [
		('employee_code_unique', 'unique(employee_code)', 'Employee Code must be unique!')
	]

	@api.model
	def _selection_employee_state(self):
		return [
			('1', '1'),
			('2', '2'),
			('3', '3'),
			('4', '4'),
			('5', '5'),
		]

	employee_type = fields.Selection(
		selection=_selection_employee_state,
		string="Employee Sector",
		default='1'
	)

	operating_unit_id = fields.Many2one(
		comodel_name="operating.unit",
		string="Operating Unit",
		check_company=True,
	)

	@api.model
	def name_search(self, name='', args=None, operator='ilike', limit=100):
		domain = args or []
		results = []
		if name:
			results = super(EmployeeExt, self).name_search(name, args, operator, limit)
			if not results:
				clean_name = name.replace(',', '').replace(' ', '')
				code_domain = [('employee_code', operator, clean_name)]
				partners = self.search(domain + code_domain, limit=limit)
				results = [(p.id, p.display_name) for p in partners]
		else:
			results = super(EmployeeExt, self).name_search(name, args, operator, limit)
		return results

class DepartmentExt(models.Model):
	_inherit = 'hr.department'

	crm_id = fields.Char(string="CRM ID", readonly=True, tracking=True)
	user_name = fields.Char(string="User Name", readonly=True, tracking=True)

	_sql_constraints = [
		('crm_id_unique', 'unique (crm_id)', 'The Department with the same CRM ID already exists!'),
	]
