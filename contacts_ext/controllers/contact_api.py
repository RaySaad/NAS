# -*- coding: utf-8 -*-

import json
import logging
from odoo.http import request
from odoo import http

_logger = logging.getLogger(__name__)


class ContactAPI(http.Controller):

    @http.route('/api/contact/create', type='json', auth='public', methods=['POST'], csrf=False)
    def create_contact(self, **kw):
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
            if not post.get('identification_number'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Identification Number is required',
                    'data': {}
                }

            existing_contact = request.env['res.partner'].sudo().search([
                ('identification_number', '=', post['identification_number'])
            ], limit=1)

            if existing_contact and not post.get('customer_account', False):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Identification Number already exists',
                    'data': {}
                }

            if post.get('customer_account', False):
                existing = request.env['partner.subscription'].sudo().search([
                    ('name', '=', post['customer_account'])
                ], limit=1)

                if existing:
                    return {
                        'success': False,
                        'error': True,
                        'message': f'Individual with Customer Contract: {existing.name} already exists',
                        'data': {}
                    }

            partner_exist = request.env['res.partner'].sudo().search([
                ('customer_code', '=', post['customer_code']),
                ('is_company', '=', False)
            ], limit=1)

            if partner_exist and post.get('customer_account', False):

                request.env['partner.subscription'].sudo().create({
                    'name': post.get('customer_account'),
                    'partner_id': partner_exist.id,
                    'contract_name': post.get('contract_name'),
                    'contract_type': post.get('contract_type')
                })

                return {
                    'success': True,
                    'error': False,
                    'message': f"New Account Number: {post.get('customer_account')} is successfully added on Existing Customer having Customer Code: {post['customer_code']}",
                    'data': {
                        'contact_id': partner_exist.id,
                        'customer_code': partner_exist.customer_code
                    }
                }
            else:
                contact_data = {
                    'name': post.get('name'),
                    'customer_code': post.get('customer_code'),
                    'identification_number': post.get('identification_number'),
                    'country_code': post.get('country_code'),
                    'country_id': self.get_country_id(post.get('country_code')),
                    'state_id': self.get_state_id(post.get('state')),
                    'mobile': post.get('mobile'),
                    'second_mobile': post.get('second_mobile'),
                    'job_title': post.get('job_title'),
                    'working_place': post.get('working_place'),
                    'gender': self.get_gender(post.get('gender')),
                    'street': post.get('street'),
                    'company_type': 'person',
                    'is_company': False
                }
                if post.get('customer_account', False):
                    contact_data['subscription_id'] = [(0, 0, {'name': post.get('customer_account'),
                                                'contract_name': post.get('contract_name'),
                                                'contract_type': post.get('contract_type')})]

                partner = request.env['res.partner'].sudo().create(contact_data)
                return {
                    'success': True,
                    'error': False,
                    'message': "Contact created successfully",
                    'data': {
                        'contact_id': partner.id,
                        'identification_number': partner.identification_number
                    }
                }

        except Exception as e:
            _logger.error("Error creating contact: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/contact/read', type='json', auth='public', methods=['POST'], csrf=False)
    def read_contact(self, **kw):
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
            if not post.get('identification_number'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Identification Number is required',
                    'data': {}
                }

            contact = request.env['res.partner'].sudo().search_read(
                [('identification_number', '=', post['identification_number'])],
                fields=[
                    'id', 'name', 'customer_code', 'identification_number', 'country_code',
                    'state_id', 'mobile', 'second_mobile', 'job_title', 'working_place',
                    'gender', 'street', 'is_company', 'company_type'
                ],
                limit=1
            )

            if not contact:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Contact not found',
                    'data': {}
                }

            # Convert False values to None in the contact data
            contact_data = contact[0]
            for key in contact_data:
                if contact_data[key] is False:
                    contact_data[key] = None

            return {
                'success': True,
                'error': False,
                'message': 'Contact retrieved successfully',
                'data': contact_data
            }

        except Exception as e:
            _logger.error("Error reading contact: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/contact/update', type='json', auth='public', methods=['POST'], csrf=False)
    def update_contact(self, **kw):
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
            if not post.get('identification_number'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Identification Number is required',
                    'data': {}
                }

            contact = request.env['res.partner'].sudo().search(
                [('identification_number', '=', post['identification_number'])],
                limit=1
            )

            if not contact:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Contact not found',
                    'data': {}
                }

            allowed_fields = [
                'name', 'customer_code', 'country_code', 'country_id', 'state_id', 'mobile',
                'second_mobile', 'job_title', 'working_place', 'gender', 'street'
            ]

            update_data = {}
            for field in allowed_fields:
                if field in post:
                    if field == 'gender':
                        update_data[field] = self.get_gender(post[field])
                    elif field == 'state_id':
                        update_data[field] = self.get_state_id(post[field])
                    elif field == 'country_code':
                        update_data[field] = post[field]
                        update_data['country_id'] = self.get_country_id(post[field])
                    else:
                        update_data[field] = post[field]

            if not update_data:
                return {
                    'success': False,
                    'error': True,
                    'message': 'No valid fields provided for update',
                    'data': {}
                }

            contact.write(update_data)
            if post.get('customer_account', False):
                existing = request.env['partner.subscription'].sudo().search([
                    ('name', '=', post['customer_account'])
                ], limit=1)

                if existing:
                    return {
                        'success': False,
                        'error': True,
                        'message': f'Customer Contract: {existing.name} already exists',
                        'data': {}
                    }

                request.env['partner.subscription'].sudo().create({
                    'name': post.get('customer_account'),
                    'partner_id': contact.id,
                    'contract_name': post.get('contract_name'),
                    'contract_type': post.get('contract_type')
                })
            return {
                'success': True,
                'error': False,
                'message': 'Contact updated successfully',
                'data': {
                    'identification_number': contact.identification_number,
                    'updated_fields': list(update_data.keys())
                }
            }

        except Exception as e:
            _logger.error("Error updating contact: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/contact/delete', type='json', auth='public', methods=['POST'], csrf=False)
    def delete_contact(self, **kw):
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
            if not post.get('identification_number'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Identification Number is required',
                    'data': {}
                }

            contact = request.env['res.partner'].sudo().search(
                [('identification_number', '=', post['identification_number'])],
                limit=1
            )

            if not contact:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Contact not found',
                    'data': {}
                }

            contact.unlink()
            return {
                'success': True,
                'error': False,
                'message': 'Contact deleted successfully',
                'data': {}
            }
        except Exception as e:
            _logger.error("Error deleting contact: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    def get_gender(self, gender_code):
        if gender_code == 1 or gender_code == '1':
            return 'male'
        elif gender_code == 2 or gender_code == '2':
            return 'female'
        return False

    def get_state_id(self, state_name):
        if state_name:
            state = request.env['res.country.state'].sudo().search([('code', '=', state_name)], limit=1)
            return state.id if state else False
        return False

    def get_country_id(self, code):
        if code:
            country = request.env['res.country'].sudo().search([('code', '=', code)], limit=1)
            return country.id if country else False
        return False

    @http.route('/api/countries/read', type='http', auth='public', methods=['GET'], csrf=False)
    def get_contacts_countries(self, **kw):
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
            countries = request.env['res.country'].sudo().search_read(
                [],
                fields=['id', 'name', 'code']
            )

            if not countries:
                return request.make_response(json.dumps({
                    'success': False,
                    'error': True,
                    'message': 'Country not found',
                    'data': {}
                }), headers=[('Content-Type', 'application/json')])

            return request.make_response(json.dumps({
                'success': True,
                'error': False,
                'message': 'Countries data retrieved successfully',
                'data': countries,
            }), headers=[('Content-Type', 'application/json')])

        except Exception as e:
            _logger.error("Error reading countries: %s", str(e))
            return request.make_response(json.dumps({
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }), headers=[('Content-Type', 'application/json')])

    @http.route('/api/states/read', type='http', auth='public', methods=['POST'], csrf=False)
    def get_contacts_states(self, **kwargs):
        post = json.loads(request.httprequest.data.decode('utf-8'))
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

        country_code = post.get('country_code')
        if not country_code:
            return request.make_response(json.dumps({
                'success': False,
                'error': True,
                'message': 'Country Code is required',
                'data': {}
            }), headers=[('Content-Type', 'application/json')])
        try:
            states = request.env['res.country.state'].sudo().search_read(
                [('country_id.code', '=', country_code)],
                fields=['id', 'name', 'code', 'country_id']
            )

            if not states:
                return request.make_response(json.dumps({
                    'success': False,
                    'error': True,
                    'message': 'State not found',
                    'data': {}
                }), headers=[('Content-Type', 'application/json')])
            return request.make_response(json.dumps({
                'success': True,
                'error': False,
                'message': 'States data retrieved successfully',
                'data': states,
            }), headers=[('Content-Type', 'application/json')])

        except Exception as e:
            _logger.error("Error reading states: %s", str(e))
            return request.make_response(json.dumps({
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }), headers=[('Content-Type', 'application/json')])


class CompanyAPI(http.Controller):

    @http.route('/api/company/create', type='json', auth='public', methods=['POST'], csrf=False)
    def create_company(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')
        provided_authorization = headers.get('Authorization')

        if not provided_authorization or token != provided_authorization.replace('Bearer', '').strip():
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            if not post.get('customer_account'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Customer Contract is required',
                    'data': {}
                }

            existing = request.env['partner.subscription'].sudo().search([
                ('name', '=', post['customer_account'])
            ], limit=1)

            if existing:
                return {
                    'success': False,
                    'error': True,
                    'message': f'Company with Customer Contract: {existing.name} already exists',
                    'data': {}
                }

            if not post.get('customer_code'):
                return {
                    'success': False,
                    'error': True,
                    'message': 'Customer Code is required',
                    'data': {}
                }

            partner_exist = request.env['res.partner'].sudo().search([
                ('customer_code', '=', post['customer_code']),
                ('is_company', '=', True)
            ], limit=1)

            if partner_exist:

                request.env['partner.subscription'].sudo().create({
                    'name': post.get('customer_account'),
                    'partner_id': partner_exist.id,
                    'contract_name': post.get('contract_name'),
                    'contract_type': post.get('contract_type')
                })

                return {
                    'success': True,
                    'error': False,
                    'message': f"New Account Number: {post.get('customer_account')} is successfully added on Existing Customer having Customer Code: {post['customer_code']}",
                    'data': {
                        'company_id': partner_exist.id,
                        'customer_code': partner_exist.customer_code
                    }
                }
            else:
                company_data = {
                    'name': post.get('name'),
                    'customer_code': post.get('customer_code'),
                    'email': post.get('email'),
                    'vat': post.get('vat'),
                    'is_company': True,
                    'currency': post.get('currency'),
                    'lock_sale_currency': post.get('lock_sale_currency'),
                    'forecast_invoice_frequency': post.get('forecast_invoice_frequency'),
                    'project_group_id': post.get('project_group_id'),
                    'invoice_project_id': post.get('invoice_project_id'),
                    'labor_office_no': post.get('labor_office_no'),
                    'registration_no': post.get('registration_no'),
                    'subscription_id': [(0, 0, {'name': post.get('customer_account'),
                                                'contract_name': post.get('contract_name'),
                                                'contract_type': post.get('contract_type')})]

                }

                company = request.env['res.partner'].sudo().create(company_data)
                return {
                    'success': True,
                    'error': False,
                    'message': "Company created successfully",
                    'data': {
                        'company_id': company.id,
                        'customer_code': company.customer_code
                    }
                }
        except Exception as e:
            _logger.error("Error creating company: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/company/read', type='json', auth='public', methods=['POST'], csrf=False)
    def read_company(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')
        provided_authorization = headers.get('Authorization')

        if not provided_authorization or token != provided_authorization.replace('Bearer', '').strip():
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            company = request.env['res.partner'].sudo().search_read(
                [('customer_code', '=', post.get('customer_code')), ('is_company', '=', True)],
                fields=[
                    'name', 'customer_code', 'email', 'vat', 'subscription_id',
                    'currency', 'lock_sale_currency', 'forecast_invoice_frequency',
                    'project_group_id', 'invoice_project_id', 'company_type',
                    'labor_office_no', 'registration_no'
                ],
                limit=1
            )

            if not company:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Company not found',
                    'data': {}
                }

            # Convert False values to None in the company data
            company_data = company[0]
            for key in company_data:
                if company_data[key] is False:
                    company_data[key] = None

            return {
                'success': True,
                'error': False,
                'message': 'Company retrieved successfully',
                'data': company_data
            }

        except Exception as e:
            _logger.error("Error reading company: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/company/update', type='json', auth='public', methods=['POST'], csrf=False)
    def update_company(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')
        provided_authorization = headers.get('Authorization')

        if not provided_authorization or token != provided_authorization.replace('Bearer', '').strip():
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            company = request.env['res.partner'].sudo().search(
                [('customer_code', '=', post.get('customer_code')),
                 ('is_company', '=', True)],
                limit=1
            )

            if not company:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Company not found',
                    'data': {}
                }

            update_fields = [
                'name', 'customer_code', 'email', 'vat',
                'currency', 'company_type', 'lock_sale_currency',
                'forecast_invoice_frequency', 'project_group_id',
                'invoice_project_id', 'labor_office_no', 'registration_no'
            ]

            update_data = {}
            for field in update_fields:
                if field in post:
                    update_data[field] = post[field]

            if not update_data:
                return {
                    'success': False,
                    'error': True,
                    'message': 'No valid fields to update',
                    'data': {}
                }

            company.write(update_data)
            return {
                'success': True,
                'error': False,
                'message': 'Company updated successfully',
                'data': {
                    'customer_code': company.customer_code,
                    'updated_fields': list(update_data.keys())
                }
            }

        except Exception as e:
            _logger.error("Error updating company: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }

    @http.route('/api/company/delete', type='json', auth='public', methods=['POST'], csrf=False)
    def delete_company(self, **kw):
        post = json.loads(request.httprequest.data.decode('utf-8'))
        headers = request.httprequest.headers
        token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')
        provided_authorization = headers.get('Authorization')

        if not provided_authorization or token != provided_authorization.replace('Bearer', '').strip():
            return {
                'success': False,
                'error': True,
                'message': 'Unauthorized Access!',
                'data': {}
            }

        try:
            company = request.env['res.partner'].sudo().search(
                [('customer_code', '=', post.get('customer_code')), ('is_company', '=', True)],
                limit=1
            )

            if not company:
                return {
                    'success': False,
                    'error': True,
                    'message': 'Company not found',
                    'data': {}
                }

            company.unlink()
            return {
                'success': True,
                'error': False,
                'message': 'Company deleted successfully',
                'data': {}
            }

        except Exception as e:
            _logger.error("Error deleting company: %s", str(e))
            return {
                'success': False,
                'error': True,
                'message': str(e),
                'data': {}
            }
