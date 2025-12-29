import json
import re
import logging
from odoo.http import request
from odoo import http

_logger = logging.getLogger(__name__)


class SimpleEmployeeAPI(http.Controller):

    @http.route('/api/employee/create', type='json', auth='public', methods=['POST'], csrf=False)
    def create_employee(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('employee_code'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Employee Code is required',
                    'data': {}
                }

            if request.env['hr.employee'].sudo().search([('employee_code', '=', post['employee_code'])]):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Employee code already exists',
                    'data': {}
                }

            if post.get('crm_id'):
                existing_crm = request.env['hr.employee'].sudo().search([
                    ('crm_id', '=', post['crm_id'])
                ], limit=1)
                if existing_crm:
                    return {
                        'success': False,
                        'error': True,
                        'message': 'CRM ID already exists',
                        'data': {
                            'existing_employee': existing_crm.employee_code,
                            'suggestion': 'Use update API to modify existing record'
                        }
                    }

            operating_unit_id = post.get('operating_unit_id', False)
            operating_unit = request.env['operating.unit'].sudo().search([('code', '=', operating_unit_id)])
            if operating_unit_id and len(operating_unit)== 0:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Wrong code in Operation Unit',
                    'data': {}
                }

            existing = request.env['partner.subscription'].sudo().search([
                ('name', '=', post.get('customer_account'))
            ], limit=1)

            emp_data = {
                'employee_code': post['employee_code'],
                'name': post.get('name'),
                'department_id': self.get_department_id(post.get('department_id')),
                'operating_unit_id': operating_unit.id,
                'job_title': post.get('job_title'),
                'customer_account': existing.id if existing else False,
                'employee_section': post.get('employee_section'),
                'job_number': post.get('job_number'),
                'project_code': post.get('project_code'),
                'border_number': post.get('border_number'),
                'profession_id': post.get('profession_id'),
                'identification_id': post.get('identification_no'),
                'country_code': post.get('country_code'),
                'employee_type': post.get('employee_type', '1'),
                'passport_id': post.get('passport_id'),
                'birthday': post.get('birthday'),
                'gender': self.get_gender(post.get('gender')),
                'marital': self.get_marital(post.get('marital')),
                'crm_id': post.get('crm_id'),
                'user_name': post.get('user_name'),
                'company_id': request.env.company.id
            }

            if post.get('arrival_date'):
                emp_data['arrival_date'] = post['arrival_date']
            if post.get('project_joining_date'):
                emp_data['project_joining_date'] = post['project_joining_date']

            emp = request.env['hr.employee'].sudo().create(emp_data)
            return {
                'success': True,
                'error': False,
                'message': "Employee created successfully",
                'data': {
                    'employee_id': emp.id,
                    'employee_code': emp.employee_code
                }
            }

        except Exception as e:
            _logger.error("Error creating employee: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/employee/read', type='json', auth='public', methods=['POST'], csrf=False)
    def read_employee(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('employee_code'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Employee Code is required',
                    'data': {}
                }

            emp = request.env['hr.employee'].sudo().search_read(
                [('employee_code', '=', post['employee_code'])],
                fields=['id', 'employee_code', 'name', 'department_id', 'operating_unit_id', 'job_title',
                        'work_email', 'work_phone', 'crm_id', 'user_name', 'employee_section',
                        'job_number', 'project_code', 'border_number',
                        'arrival_date', 'profession_id', 'identification_id','customer_account',
                        'country_code', 'project_joining_date', 'employee_type'],
                limit=1
            )

            if not emp:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Employee not found',
                    'data': {}
                }

            # Convert False values to None in the employee data
            emp_data = emp[0]
            for key in emp_data:
                if emp_data[key] is False:
                    emp_data[key] = None

            if emp_data.get('operating_unit_id', False):
                oui = re.search(r'\[([^\]]+)\]', emp_data.get('operating_unit_id', False)[1])
                if oui:
                    emp_data['operating_unit_id'] = oui.group(1)

            return {
                'success': True,
                'error': False,
                'message': 'Employee retrieved successfully',
                'data': emp_data
            }

        except Exception as e:
            _logger.error("Error reading employee: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/employee/update', type='json', auth='public', methods=['POST'], csrf=False)
    def update_employee(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('employee_code'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Employee Code is required',
                    'data': {}
                }

            emp = request.env['hr.employee'].sudo().search(
                [('employee_code', '=', post['employee_code'])],
                limit=1
            )
            if not emp:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Employee not found',
                    'data': {}
                }

            allowed_fields = [
                'name', 'department_id', 'operating_unit_id', 'job_title', 'work_email', 'work_phone',
                'crm_id', 'employee_section', 'job_number', 'project_code',
                'border_number', 'country_code', 'arrival_date', 'profession_id','customer_account',
                'identification_id', 'country_code', 'project_joining_date', 'employee_type'
            ]

            update_data = {}
            for field in allowed_fields:
                if field in post and field == 'department_id':
                    update_data[field] = self.get_department_id(post[field])
                elif field in post and field == 'customer_account':
                    existing = request.env['partner.subscription'].sudo().search([
                        ('name', '=', post.get('customer_account'))
                    ], limit=1)
                    update_data[field] = existing.id if existing else False
                elif field in post and field == 'operating_unit_id':
                    update_data[field] = self.get_operating_unit_id(post[field])
                elif field in post:
                    update_data[field] = post[field]

            if not update_data:
                return {
                    'success': False,
                    'error': True,
                    'message': 'No valid fields provided for update',
                    'data': {}
                }

            emp.write(update_data)
            return {
                'success': True,
                'error': False,
                'message': 'Employee updated successfully',
                'data': {
                    'employee_code': emp.employee_code,
                    'updated_fields': list(update_data.keys())
                }
            }

        except Exception as e:
            _logger.error("Error updating employee: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/employee/delete', type='json', auth='public', methods=['POST'], csrf=False)
    def delete_employee(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('employee_code'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Employee Code is required',
                    'data': {}
                }

            emp = request.env['hr.employee'].sudo().search(
                [('employee_code', '=', post['employee_code'])],
                limit=1
            )
            if not emp:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Employee not found',
                    'data': {}
                }

            emp.unlink()
            return {
                'success': True,
                'error': False,
                'message': 'Employee deleted successfully',
                'data': {}
            }
        except Exception as e:
            _logger.error("Error deleting employee: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/department/create', type='json', auth='public', methods=['POST'], csrf=False)
    def create_department(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('crm_id'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'CRM ID is required',
                    'data': {}
                }
            if not post.get('name'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Department name is required',
                    'data': {}
                }

            if request.env['hr.department'].sudo().search([('crm_id', '=', post['crm_id'])]):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Department with this CRM ID already exists',
                    'data': {}
                }

            dept_data = {
                'name': post['name'],
                'user_name': post['user_name'],
                'crm_id': str(post['crm_id']),
                'manager_id': self.get_employee_code(post.get('manager_id')),
                'parent_id': self.get_department_id(post.get('parent_id')),
                'company_id': request.env.company.id
            }
            department = request.env['hr.department'].sudo().create(dept_data)
            return {
                'success': True,
                'error': False,
                'message': 'Department created successfully',
                'data': {
                    'department_id': int(department.id),
                    'crm_id': int(department.crm_id)
                }
            }

        except Exception as e:
            _logger.error("Error creating department: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/department/read', type='json', auth='public', methods=['POST'], csrf=False)
    def get_department(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('crm_id'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'CRM ID is required',
                    'data': {}
                }

            department = request.env['hr.department'].sudo().search_read(
                [('crm_id', '=', str(post['crm_id']))],
                fields=['id', 'name', 'crm_id', 'manager_id', 'parent_id', 'company_id'],
                limit=1
            )

            if not department:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Department not found',
                    'data': {}
                }

            # Convert False values to None in the department data
            dept_data = department[0]
            for key in dept_data:
                if dept_data[key] is False:
                    dept_data[key] = None

            # Special handling for crm_id to ensure it's an integer
            crm_id = dept_data.get("crm_id")
            if crm_id:
                dept_data["crm_id"] = int(crm_id)

            return {
                'success': True,
                'error': False,
                'message': 'Department retrieved successfully',
                'data': dept_data
            }

        except Exception as e:
            _logger.error("Error reading department: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/department/update', type='json', auth='public', methods=['POST'], csrf=False)
    def update_department(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('crm_id'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'CRM ID is required',
                    'data': {}
                }

            department = request.env['hr.department'].sudo().search(
                [('crm_id', '=', post['crm_id'])],
                limit=1
            )

            if not department:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Department not found',
                    'data': {}
                }

            update_data = {}
            allowed_fields = ['name', 'manager_id', 'parent_id', 'company_id', 'user_name']

            for field in post:
                if field in allowed_fields and field != 'crm_id' and field == 'parent_id':
                    update_data[field] = self.get_department_id(post[field])
                if field in allowed_fields and field != 'crm_id' and field == 'manager_id':
                    update_data[field] = self.get_employee_code(post[field])
                if field in allowed_fields and field != 'crm_id' and field != 'parent_id' and field != 'manager_id':
                    update_data[field] = post[field]

            if not update_data:
                return {
                    'success': False,
                    'error': True,
                    'message': 'No valid fields provided for update',
                    'data': {}
                }

            department.write(update_data)
            return {
                'success': True,
                'error': False,
                'message': 'Department updated successfully',
                'data': {
                    'crm_id': department.crm_id,
                    'updated_fields': list(update_data.keys())
                }
            }

        except Exception as e:
            _logger.error("Error updating department: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/department/delete', type='json', auth='public', methods=['POST'], csrf=False)
    def delete_department(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('crm_id'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'CRM ID is required',
                    'data': {}
                }

            department = request.env['hr.department'].sudo().search(
                [('crm_id', '=', post['crm_id'])],
                limit=1
            )
            if not department:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Department not found',
                    'data': {}
                }
            department.unlink()
            return {
                'success': True,
                'error': False,
                'message': 'Department deleted successfully',
                'data': {}
            }
        except Exception as e:
            _logger.error("Error deleting department: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    def get_department_id(self, crm_id):
        department = request.env['hr.department'].sudo().search([('crm_id', '=', str(crm_id))])
        if department and department.exists():
            return department.id
        else:
            return False

    def get_operating_unit_id(self, operating_unit_id):
        operating_unit = request.env['operating.unit'].sudo().search([('code', '=', operating_unit_id)])
        if operating_unit and operating_unit.exists():
            return operating_unit.id
        else:
            return False

    def get_employee_code(self, code):
        employee = request.env['hr.employee'].sudo().search([('employee_code', '=', code)])
        if employee and employee.exists():
            return employee.id
        else:
            return False

    def get_gender(self, gender_no):
        if gender_no == 1:
            return 'male'
        elif gender_no == 2:
            return 'female'
        elif gender_no == 3:
            return 'other'
        else:
            return False

    def get_marital(self, marital_no):
        if marital_no == 1:
            return 'single'
        elif marital_no == 2:
            return 'married'
        elif marital_no == 3:
            return 'other'
        else:
            return False

    @http.route('/api/employee/sections/create', type='json', auth='public', methods=['POST'], csrf=False)
    def create_employee_sections(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('name'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Section name is required',
                    'data': {}
                }

            dept_data = {
                'name': post['name'],
                'company_id': request.env.company.id
            }
            section = request.env['employee.section'].sudo().create(dept_data)
            return {
                'success': True,
                'error': False,
                'message': 'Section created successfully',
                'data': {
                    'section_id': section.id
                }
            }

        except Exception as e:
            _logger.error("Error creating section: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/employee/sections/read', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_sections(self, **kw):
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return request.make_response(json.dumps({
                'success': False,
                'error': True,
                'message': "Unauthorized Access!",
                'data': {}
            }), headers=[('Content-Type', 'application/json')])
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return request.make_response(json.dumps({
                'success': False,
                'error': True,
                'message': "Unauthorized Access!",
                'data': {}
            }), headers=[('Content-Type', 'application/json')])

        try:
            sections = request.env['employee.section'].sudo().search_read(
                [],
                fields=['id', 'name']
            )

            if not sections:
                return request.make_response(json.dumps({
                    'success': False,
                    'error': True,
                    'message': 'Section not found',
                    'data': {}
                }), headers=[('Content-Type', 'application/json')])

            # Convert False values to None in all sections data
            for section in sections:
                for key in section:
                    if section[key] is False:
                        section[key] = None

            return request.make_response(json.dumps({
                'success': True,
                'error': False,
                'message': 'Sections retrieved successfully',
                'data': sections
            }), headers=[('Content-Type', 'application/json')])

        except Exception as e:
            _logger.error("Error reading sections: %s", str(e))
            return request.make_response(json.dumps({
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }), headers=[('Content-Type', 'application/json')])
        
    @http.route('/api/employee/sections/update', type='json', auth='public', methods=['POST'], csrf=False)
    def update_employee_sections(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('section_id'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Section ID is required',
                    'data': {}
                }

            section = request.env['employee.section'].sudo().search(
                [('id', '=', post['section_id'])],
                limit=1
            )

            if not section:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Section not found',
                    'data': {}
                }

            update_data = {}
            allowed_fields = ['name']

            for field in post:
                if field in allowed_fields and field != 'section_id':
                    update_data[field] = post[field]

            if not update_data:
                return {
                    'success': False,
                    'error': True,
                    'message': 'No valid fields provided for update',
                    'data': {}
                }

            section.write(update_data)
            return {
                'success': True,
                'error': False,
                'message': 'Section updated successfully',
                'data': {
                    'section_id': section.id,
                    'updated_fields': list(update_data.keys())
                }
            }

        except Exception as e:
            _logger.error("Error updating section: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/employee/sections/delete', type='json', auth='public', methods=['POST'], csrf=False)
    def delete_employee_sections(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        provided_authorization = headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

        if not provided_authorization:
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }
        if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('section_id'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Section ID is required',
                    'data': {}
                }

            section = request.env['employee.section'].sudo().search(
                [('id', '=', post['section_id'])],
                limit=1
            )
            if not section:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Section not found',
                    'data': {}
                }
            section.unlink()
            return {
                'success': True,
                'error': False,
                'message': 'Section deleted successfully',
                'data': {}
            }
        except Exception as e:
            _logger.error("Error deleting section: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }
