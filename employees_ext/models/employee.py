from odoo import models, fields, api, _
from odoo.fields import Domain


class EmployeeExt(models.Model):
    _inherit = 'hr.employee'

    identification_id = fields.Char(
        string='Iqama No', related='version_id.identification_id', inherited=True,
        store=False, readonly=False, groups="hr.group_hr_user",
    )
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
    customer_account = fields.Many2one('partner.subscription', string='Customer Contract', tracking=True)
    # Keep the legacy API name while using Odoo 19's version-backed field.
    gender = fields.Selection(string='Legacy Gender', related='sex', readonly=False, groups='hr.group_hr_user')
    marital = fields.Selection(
        related='version_id.marital', inherited=True, store=False, readonly=False,
        string='Marital Status',
        groups="hr.group_hr_user",
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

    _employee_code_unique = models.Constraint(
        'unique(employee_code)',
        'Employee Code must be unique!',
    )

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
    def name_search(self, name='', domain=None, operator='ilike', limit=100, *, args=None):
        # Odoo 19 sends `domain`; retain the legacy keyword for existing callers.
        domain = Domain(domain if domain is not None else (args or Domain.TRUE))
        results = super().name_search(name, domain, operator, limit)
        if name and not results:
            clean_name = name.replace(',', '').replace(' ', '')
            employees = self.search(
                domain & Domain('employee_code', operator, clean_name), limit=limit
            )
            results = [(employee.id, employee.display_name) for employee in employees]
        return results

    # cronjob for update field operating_unit_id based on formula
    def _cron_update_operating_unit(self):
        """
        Cron job: Update operating_unit_id on employees based on project_code.
        Reads mapping dynamically from pc.ou.mapping model.
        Special project_code values:

        """
        mapping_model = self.env['pc.ou.mapping']

        # Build a dict: {project_code: operating_unit_id}
        mappings = mapping_model.search([
            ('project_code', 'not in', ['DEFAULT', 'EMPTY'])
        ])
        code_map = {m.project_code: m.operating_unit_id for m in mappings}

        # Get default and empty fallbacks
        default_mapping = mapping_model.search([('project_code', '=', 'DEFAULT')], limit=1)

        default_ou = default_mapping.operating_unit_id if default_mapping else False

        employees = self.env['hr.employee'].search([])

        for employee in employees:
            code = (employee.project_code or '').strip()

            if not code:
                employee.operating_unit_id = False
            elif code in code_map:
                employee.operating_unit_id = code_map[code]
            else:
                employee.operating_unit_id = default_ou


class EmployeeVersionExt(models.Model):
    _inherit = 'hr.version'

    # Keep the customization on the actual Odoo 19 storage model rather than
    # shadowing its delegated employee field with a second database column.
    marital = fields.Selection(default='single', required=True, tracking=True)

    def _get_marital_status_selection(self):
        values = super()._get_marital_status_selection()
        if not any(key == 'other' for key, label in values):
            values = [*values, ('other', _('Other'))]
        return values


class DepartmentExt(models.Model):
    _inherit = 'hr.department'

    crm_id = fields.Char(string="CRM ID", readonly=True, tracking=True)
    user_name = fields.Char(string="User Name", readonly=True, tracking=True)

    _crm_id_unique = models.Constraint(
        'unique (crm_id)',
        'The Department with the same CRM ID already exists!',
    )
