import json
import logging
from odoo.http import request
from odoo import http
from odoo import api, models, fields, _
_logger = logging.getLogger(__name__)

class JVAPI(http.Controller):

	@http.route('/api/tax/read', type='json', auth='public', methods=['POST'], csrf=False)
	def read_tax(self, **kw):
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
			tax_ids = request.env['account.tax'].sudo().search_read([('type_tax_use', '=', 'sale')],
																	fields=['id', 'name', 'type_tax_use'])

			if not tax_ids:
				return {
					'success': False,
					'error': True,
					'message': 'Taxes not found',
					'data': {}
				}
			tax_data = tax_ids
			for dict in tax_data:
				for key in dict:
					if dict[key] is False:
						dict[key] = None

			return {
				'success': True,
				'error': False,
				'message': 'Taxes retrieved successfully',
				'data': tax_data
			}

		except Exception as e:
			_logger.error("Error reading taxes: %s", str(e))
			return {
				'success': False,
				'error': True,
				'message': str(e),
				'data': {}
			}

	@http.route('/api/jv/create', type='http', auth='public', methods=['POST'], csrf=False)
	def create_jv(self, **kw):
		posts = json.loads(request.httprequest.data.decode('utf-8'))
		headers = request.httprequest.headers
		provided_authorization = headers.get('Authorization')
		token = request.env['ir.config_parameter'].sudo().get_param('employees_ext.hr_api_token')

		if not provided_authorization:
			return request.make_json_response({"jsonrpc": "2.0","id":1,"result":{
				'success': False,
				'error': True,
				'message': 'Unauthorized Access!',
				'data': {}
		}})
		if not token or token != provided_authorization.replace('Bearer', '').replace(' ', ''):
			return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
				'success': False,
				'error': True,
				'message': 'Unauthorized Access!',
				'data': {}
		}})

		if not isinstance(posts, list):
			posts = [posts] if posts else []
		response = []
		for post in posts:
			if 'type' in post:
				if post['type'] == 'invoice':
					try:
						required_field = {
							'crm_number': "CRM Number is required",
							'customer_account': "Customer Contract is required",
							# 'operating_unit_id': "Operation Unit is required",
							'line_ids': "Line IDs are required"
						}
						for key, value in required_field.items():
							if not post.get(key):
								return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
									'success': False,
									'error': True,
									'message': f"{value}",
									'data': {}
								}})

						existing_crm = request.env['account.move'].sudo().search([
							('crm_number', '=', post['crm_number']), ('jv_type', '=', post['type'])
						], limit=1)

						if existing_crm:
							return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
								'success': False,
								'error': True,
								'message': 'CRM Number already exists',
								'data': {}
							}})

						existing = request.env['partner.subscription'].sudo().search([
							('name', '=', post['customer_account'])
						], limit=1)

						if not existing:
							return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
								'success': False,
								'error': True,
								'message': f"Partner having Customer Contract: {post['customer_account']} does not exists",
								'data': {}
							}})
						partner_id = existing.partner_id

						operating_unit_id = post.get('operating_unit_id', False)
						operating_unit = request.env['operating.unit'].sudo().search([('code', '=', operating_unit_id)])
						if operating_unit_id and len(operating_unit) == 0:
							return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
								'success': False,
								'error': True,
								'message': 'Wrong code in Operation Unit',
								'data': {}
							}})

						line_val = []
						for line in post['line_ids']:
							line_operating_unit_id = line.get('operating_unit_id', False)
							line_operating_unit = request.env['operating.unit'].sudo().search(
								[('code', '=', line_operating_unit_id)])
							if line_operating_unit_id and len(line_operating_unit) == 0:
								return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
									'success': False,
									'error': True,
									'message': 'Wrong code in Operation Unit',
									'data': {}
								}})

							if not request.env['account.account'].sudo().search([('code', '=', line['account_id'])]):
								return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
									'success': False,
									'error': True,
									'message': f"CoA have code: {line['account_id']} does not exist.",
									'data': {}
								}})

							analytic_dept = False
							if line.get('department'):
								analytic_dept = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['department'])
								], limit=1)
								if not analytic_dept:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Department Analytic account {line['department']} does not exist",
										'data': {}
									}})
							analytic_cost = False
							if line.get('cost_center'):
								analytic_cost = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['cost_center'])
								], limit=1)
								if not analytic_cost:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Cost Center Analytic account {line['cost_center']} does not exist",
										'data': {}
									}})
							branch = False
							if line.get('branch'):
								branch = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['branch'])
								], limit=1)
								if not branch:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Branch Analytic account {line['branch']} does not exist",
										'data': {}
									}})
							analytic_distribution = {}
							if analytic_dept:
								analytic_distribution[str(analytic_dept.id)] = 100.0
							if analytic_cost:
								analytic_distribution[str(analytic_cost.id)] = 100.0
							if branch:
								analytic_distribution[str(branch.id)] = 100.0

							vals = {
								'account_id': request.env['account.account'].sudo().search([
									('code', '=', line['account_id'])]).id,
								'name': line['name'],
								'tax_ids': [[4, line['tax_id']]] if line.get('tax_id', False) else [],
								'employee_code': line.get('employee_code', ''),
								"customer_account": existing.id,
								"customer_code": line.get('customer_code', ''),
								"operating_unit_id": line_operating_unit.id,
								'analytic_distribution': analytic_distribution or {},
								'debit': line['amount'] if line['type'] == 'debit' else 0,
								'credit': line['amount'] if line['type'] == 'credit' else 0
							}

							line_val.append((0, 0, vals))

						jv_data = {
							"partner_id": partner_id.id,
							"customer_code": partner_id.customer_code,
							"customer_account": existing.id,
							"operating_unit_id": operating_unit.id,
							"project_group_id": partner_id.project_group_id,
							"invoice_project_id": partner_id.invoice_project_id,
							"crm_number": post.get("crm_number"),
							"journal_id": request.env.ref('account.1_sale').id,
							"date": post['date'],
							'jv_type': post['type'],
							"line_ids": line_val
						}
						jv = request.env['account.move'].sudo().create(jv_data)
						response.append({
							'success': True,
							'error': False,
							'message': "JV created successfully",
							'data': {
								'contact_id': jv.id,
								'crm_number': jv.crm_number
							}
						})
					except Exception as e:
						_logger.error("Error creating JV: %s", str(e))
						return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
							'success': False,
							'error': True,
							'message': str(e),
							'data': {}
						}})

				elif post['type'] in ['multi-invoice', 'multi-payment']:
					try:
						required_field = {
							'line_ids': "Line IDs are required"
						}
						for key, value in required_field.items():
							if not post.get(key):
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"{value}",
									'data': {}
							}})
						operating_unit = False
						if post.get('operating_unit_id', False):
							operating_unit_id = post.get('operating_unit_id', False)
							operating_unit = request.env['operating.unit'].sudo().search([('code', '=', operating_unit_id)])
							if operating_unit_id and len(operating_unit) == 0:
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': 'Wrong code in Operation Unit',
									'data': {}
							}})

						line_val = []
						for line in post['line_ids']:
							if line.get('customer_account', False):
								existing = request.env['partner.subscription'].sudo().search([
									('name', '=', line['customer_account'])
								], limit=1)

								if not existing:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Partner having Customer Contract: {line['customer_account']} does not exists",
										'data': {}
									}})
							else:
								return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
									'success': False,
									'error': True,
									'message': f"Customer Contract is required.",
									'data': {}
								}})

							line_operating_unit_id = line.get('operating_unit_id', False)

							if line_operating_unit_id:
								line_operating_unit = request.env['operating.unit'].sudo().search(
									[('code', '=', line_operating_unit_id)])
								if line_operating_unit_id and len(line_operating_unit) == 0:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': 'Wrong code in Operation Unit',
										'data': {}
									}})
							analytic_dept = False
							if line.get('department'):
								analytic_dept = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['department'])
								], limit=1)
								if not analytic_dept:
									return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
										'success': False,
										'error': True,
										'message': f"Department Analytic account {line['department']} does not exist",
										'data': {}
								}})
							analytic_cost = False
							if line.get('cost_center'):
								analytic_cost = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['cost_center'])
								], limit=1)
								if not analytic_cost:
									return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
										'success': False,
										'error': True,
										'message': f"Cost Center Analytic account {line['cost_center']} does not exist",
										'data': {}
								}})
							branch = False
							if line.get('branch'):
								branch = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['branch'])
								], limit=1)
								if not branch:
									return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
										'success': False,
										'error': True,
										'message': f"Branch Analytic account {line['branch']} does not exist",
										'data': {}
									}})
							analytic_distribution = {}
							if analytic_dept:
								analytic_distribution[str(analytic_dept.id)] = 100.0
							if analytic_cost:
								analytic_distribution[str(analytic_cost.id)] = 100.0
							if branch:
								analytic_distribution[str(branch.id)] = 100.0

							account_id = False
							if line.get('account_id', False):
								account = request.env['account.account'].sudo().search([
									('code', '=', line['account_id'])
								], limit=1)

								if not account and not line.get('bank_id', False):
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"CoA have code: {line['account_id']} does not exist.",
										'data': {}
									}})
								else:
									account_id = account.id

							if line.get('bank_id', False):
								journal_id = request.env['account.journal'].sudo().search([
									('code', '=', line['bank_id'])
								], limit=1)

								if not journal_id:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Bank having Bank Identifier Code: {line['bank_id']} does not exists",
										'data': {}
									}})
								else:
									account_id = journal_id.default_account_id.id

							if not account_id:
								if line.get('account_id', False):
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"CoA have code: {line['account_id']} does not exist.",
										'data': {}
									}})
								else:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Need to add either valid Account ID or Bank Journal Code",
										'data': {}
									}})


							vals = {
								'account_id': account_id,
								'name': line['name'],
								'employee_code': line.get('employee_code', ''),
								"customer_account": existing.id,
								"partner_id": existing.partner_id.id,
								"customer_code": existing.partner_id.customer_code,
								"operating_unit_id": line_operating_unit.id,
								'analytic_distribution': analytic_distribution or {},
								'debit': line['amount'] if line['type'] == 'debit' else 0,
								'credit': line['amount'] if line['type'] == 'credit' else 0
							}

							if line.get('tax_tag_ids', False):
								vals["tax_tag_ids"] =[(6, 0, [line['tax_tag_ids']])]

							line_val.append((0, 0, vals))

						jv_data = {
							"operating_unit_id": operating_unit.id if operating_unit else operating_unit,
							"journal_id": request.env.ref('account.1_general').id,
							"date": post.get('date', False),
							'jv_type': post['type'],
							'ref': post.get('ref_number', False),
							"line_ids": line_val
						}
						jv = request.env['account.move'].sudo().create(jv_data)
						response.append({
							'success': True,
							'error': False,
							'message': "JV created successfully",
							'data': {
								'contact_id': jv.id,
								'crm_number': jv.crm_number
							}
						})
					except Exception as e:
						_logger.error("Error creating JV: %s", str(e))
						return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
							'success': False,
							'error': True,
							'message': str(e),
							'data': {}
						}})

				elif post['type'] == 'invoice_refund':
					try:
						required_field = {
							# 'crm_number': "CRM Number is required",
							'customer_account': "Customer Contract is required",
							# 'operating_unit_id': "Operation Unit is required",
							'line_ids': "Line IDs are required"
						}
						for key, value in required_field.items():
							if not post.get(key):
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"{value}",
									'data': {}
								}})

						existing = request.env['partner.subscription'].sudo().search([
							('name', '=', post['customer_account'])
						], limit=1)

						if not existing:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': f"Partner having Customer Contract: {post['customer_account']} does not exists",
								'data': {}
							}})
						partner_id = existing.partner_id

						operating_unit_id = post.get('operating_unit_id', False)
						operating_unit = request.env['operating.unit'].sudo().search([('code', '=', operating_unit_id)])
						if operating_unit_id and len(operating_unit) == 0:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'Wrong code in Operation Unit',
								'data': {}
							}})

						line_val = []
						for line in post['line_ids']:
							line_operating_unit_id = line.get('operating_unit_id', False)
							line_operating_unit = request.env['operating.unit'].sudo().search(
								[('code', '=', line_operating_unit_id)])
							if line_operating_unit_id and len(line_operating_unit) == 0:
								return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
									'success': False,
									'error': True,
									'message': 'Wrong code in Operation Unit',
									'data': {}
								}})

							if not request.env['account.account'].sudo().search([('code', '=', line['account_id'])]):
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"CoA have code: {line['account_id']} does not exist.",
									'data': {}
									}})
							analytic_dept = False
							if line.get('department',False):
								analytic_dept = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['department'])
								], limit=1)
								if not analytic_dept:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Department Analytic account {line['department']} does not exist",
										'data': {}
									}})
							analytic_cost = False
							if line.get('cost_center',False):
								analytic_cost = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['cost_center'])
								], limit=1)
								if not analytic_cost:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Cost Center Analytic account {line['cost_center']} does not exist",
										'data': {}
									}})
							branch = False
							if line.get('branch',False):
								branch = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['branch'])
								], limit=1)
								if not branch:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Branch Analytic account {line['branch']} does not exist",
										'data': {}
									}})
							analytic_distribution = {}
							if analytic_dept:
								analytic_distribution[str(analytic_dept.id)] = 100.0
							if analytic_cost:
								analytic_distribution[str(analytic_cost.id)] = 100.0
							if branch:
								analytic_distribution[str(branch.id)] = 100.0

							vals = {
								'account_id': request.env['account.account'].sudo().search([
									('code', '=', line['account_id'])]).id,
								'name': line['name'],
								'employee_code': line.get('employee_code', ''),
								"customer_code": line.get('customer_code', ''),
								"operating_unit_id": line_operating_unit.id,
								"customer_account": existing.id,
								'analytic_distribution': analytic_distribution or {},
								'tax_ids': [[4, line['tax_id']]] if line.get('tax_id', False) else [],
								'debit': line['amount'] if line['type'] == 'debit' else 0,
								'credit': line['amount'] if line['type'] == 'credit' else 0
							}

							line_val.append((0, 0, vals))

						jv_data = {
							"partner_id": partner_id.id,
							"customer_code": partner_id.customer_code,
							"customer_account": existing.id,
							"operating_unit_id": operating_unit.id,
							"project_group_id": partner_id.project_group_id,
							"invoice_project_id": partner_id.invoice_project_id,
							"crm_number": post.get("crm_number", False),
							"journal_id": request.env.ref('account.1_sale').id,
							"date": post['date'],
							'jv_type': post['type'],
							"line_ids": line_val
						}
						jv = request.env['account.move'].sudo().create(jv_data)
						response.append({
							'success': True,
							'error': False,
							'message': "JV created successfully",
							'data': {
								'contact_id': jv.id,
								'crm_number': jv.crm_number
							}
						})
					except Exception as e:
						_logger.error("Error creating JV: %s", str(e))
						return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
							'success': False,
							'error': True,
							'message': str(e),
							'data': {}
						}})

				elif post['type'] == 'payment':
					try:
						required_field = {
							'crm_number': "CRM Number is required",
							# 'customer_account': "Customer Contract is required",
							'operating_unit_id': "Operation Unit is required",
							'line_ids': "Line IDs are required",
							'bank_id': "Bank ID is required"
						}
						for key, value in required_field.items():
							if not post.get(key):
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"{value}",
									'data': {}
								}})

						existing_crm = request.env['account.move'].sudo().search([
							('crm_number', '=', post['crm_number']),('jv_type','=',post['type'])
						], limit=1)

						if existing_crm:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'CRM Number already exists',
								'data': {}
							}})
						partner_id = False
						existing = False
						if post.get('customer_account', False):
							existing = request.env['partner.subscription'].sudo().search([
								('name', '=', post['customer_account'])
							], limit=1)

							if not existing:
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"Partner having Customer Contract: {post['customer_account']} does not exists",
									'data': {}
								}})
							partner_id = existing.partner_id

						bank_id = request.env['account.journal'].sudo().search([
							('code', '=', post['bank_id'])
						], limit=1)

						if not bank_id:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': f"Bank having Bank Identifier Code: {post['bank_id']} does not exists",
								'data': {}
							}})

						operating_unit_id = post.get('operating_unit_id', False)
						operating_unit = request.env['operating.unit'].sudo().search([('code', '=', operating_unit_id)])
						if operating_unit_id and len(operating_unit) == 0:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'Wrong code in Operation Unit',
								'data': {}
							}})

						side = set(rec['type'] for rec in post['line_ids'])
						amount = sum(rec['amount'] for rec in post['line_ids'])
						if len(side) != 1:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'All lines as Journal Items should either be debit or credit.',
								'data': {}
							}})

						line_val=[]
						for line in post['line_ids']:
							line_operating_unit_id = line.get('operating_unit_id', False)
							line_operating_unit = request.env['operating.unit'].sudo().search(
								[('code', '=', line_operating_unit_id)])
							if line_operating_unit_id and len(line_operating_unit) == 0:
								return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
									'success': False,
									'error': True,
									'message': 'Wrong code in Operation Unit',
									'data': {}
								}})

							if not request.env['account.account'].sudo().search([('code', '=', line['account_id'])]):
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"CoA have code: {line['account_id']} does not exist.",
									'data': {}
								}})

							analytic_dept = False
							if line.get('department', False):
								analytic_dept = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['department'])
								], limit=1)
								if not analytic_dept:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Department Analytic account {line['department']} does not exist",
										'data': {}
									}})
							analytic_cost = False
							if line.get('cost_center', False):
								analytic_cost = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['cost_center'])
								], limit=1)
								if not analytic_cost:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Cost Center Analytic account {line['cost_center']} does not exist",
										'data': {}
									}})
							branch = False
							if line.get('branch', False):
								branch = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['branch'])
								], limit=1)
								if not branch:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Branch Analytic account {line['branch']} does not exist",
										'data': {}
									}})
							analytic_distribution = {}
							if analytic_dept:
								analytic_distribution[str(analytic_dept.id)] = 100.0
							if analytic_cost:
								analytic_distribution[str(analytic_cost.id)] = 100.0
							if branch:
								analytic_distribution[str(branch.id)] = 100.0

							existing_employee = False
							if line.get('employee_code'):
								employee_code = str(line['employee_code'])
								existing_employee = request.env['hr.employee'].sudo().search([
									('employee_code', '=', employee_code), ('active', '=', True)
								], limit=1)
								if not existing_employee:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': 'Employee does not exists with code (%s)' % (employee_code),
										'data': {}
									}})

							vals = {
								'account_id': request.env['account.account'].sudo().search([
									('code', '=', line['account_id'])]).id,
								'name': line['name'],
								'employee_id': existing_employee.id if existing_employee else False,
								'employee_code': line.get('employee_code', ''),
								"customer_code": line.get('customer_code', ''),
								"operating_unit_id": line_operating_unit.id,
								"customer_account": existing.id if existing else False,
								'analytic_distribution': analytic_distribution or {},
								'tax_ids': [[4, line['tax_id']]] if line.get('tax_id', False) else [],
								'debit': line['amount'] if line['type'] == 'debit' else 0,
								'credit': line['amount'] if line['type'] == 'credit' else 0
							}

							line_val.append((0, 0, vals))

						auto_line = [
							(0, 0, {
								'account_id': bank_id.default_account_id.id,
								'name': post['line_ids'][0]['name'],
								"customer_account": existing.id if existing else False,
								'debit': amount if list(side)[0] != 'debit' else 0,
								'credit': amount if list(side)[0] != 'credit' else 0
							})]
						line_id = line_val + auto_line
						jv_data = {}
						if partner_id:
							jv_data = {**jv_data, **{
								"partner_id": partner_id.id,
								"customer_code": partner_id.customer_code,
								"project_group_id": partner_id.project_group_id,
								"invoice_project_id": partner_id.invoice_project_id,
								"customer_account": existing.id
							}}

						jv_data = {**jv_data, **{
							"operating_unit_id": operating_unit.id,
							"crm_number": post.get("crm_number"),
							"journal_id": bank_id.id,
							"date": post['date'],
							'jv_type': post['type'],
							"line_ids": line_id
						}}
						jv = request.env['account.move'].sudo().create(jv_data)
						response.append({
							'success': True,
							'error': False,
							'message': "JV created successfully",
							'data': {
								'contact_id': jv.id,
								'crm_number': jv.crm_number
							}
						})

					except Exception as e:
						_logger.error("Error creating JV: %s", str(e))
						return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
							'success': False,
							'error': True,
							'message': str(e),
							'data': {}
						}})

				elif post['type'] == 'insurance_payment':
					try:
						required_field = {
							'crm_number': "CRM Number is required",
							'customer_account': "Customer Contract is required",
							'operating_unit_id': "Operation Unit is required",
							'line_ids': "Line IDs are required",
							'bank_id': "Bank ID is required"
						}
						for key, value in required_field.items():
							if not post.get(key):
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"{value}",
									'data': {}
								}})
						existing_crm = request.env['account.move'].sudo().search([
							('crm_number', '=', post['crm_number']),('jv_type','=',post['type'])
						], limit=1)
						if existing_crm:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'CRM Number already exists',
								'data': {}
							}})
						existing = request.env['partner.subscription'].sudo().search([
							('name', '=', post['customer_account'])
						], limit=1)
						if not existing:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': f"Partner having Customer Contract: {post['customer_account']} does not exists",
								'data': {}
							}})
						partner_id = existing.partner_id

						bank_id = request.env['account.journal'].sudo().search([
							('code', '=', post['bank_id'])
						], limit=1)
						if not bank_id:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': f"Bank having Bank Identifier Code: {post['bank_id']} does not exists",
								'data': {}
							}})

						operating_unit_id = post.get('operating_unit_id', False)
						operating_unit = request.env['operating.unit'].sudo().search([('code', '=', operating_unit_id)])
						if operating_unit_id and len(operating_unit) == 0:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'Wrong code in Operation Unit',
								'data': {}
							}})
						debit_side = sum([rec['amount'] for rec in post['line_ids'] if rec['type'] == 'debit'])
						credit_side = sum([rec['amount'] for rec in post['line_ids'] if rec['type'] == 'credit'])

						if debit_side == credit_side:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'You are sending balance amount already. So, no room for bank account.',
								'data': {}
							}})

						line_val = []
						for line in post['line_ids']:
							line_operating_unit_id = line.get('operating_unit_id', False)
							line_operating_unit = request.env['operating.unit'].sudo().search(
								[('code', '=', line_operating_unit_id)])
							if line_operating_unit_id and len(line_operating_unit) == 0:
								return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
									'success': False,
									'error': True,
									'message': 'Wrong code in Operation Unit',
									'data': {}
								}})

							if not request.env['account.account'].sudo().search([('code', '=', line['account_id'])]):
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"CoA have code: {line['account_id']} does not exist.",
									'data': {}
								}})
							analytic_dept = False
							if line.get('department', False):
								analytic_dept = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['department'])
								], limit=1)
								if not analytic_dept:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Department Analytic account {line['department']} does not exist",
										'data': {}
									}})
							analytic_cost = False
							if line.get('cost_center', False):
								analytic_cost = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['cost_center'])
								], limit=1)
								if not analytic_cost:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Cost Center Analytic account {line['cost_center']} does not exist",
										'data': {}
									}})
							branch = False
							if line.get('branch', False):
								branch = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['branch'])
								], limit=1)
								if not branch:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Branch Analytic account {line['branch']} does not exist",
										'data': {}
									}})
							analytic_distribution = {}
							if analytic_dept:
								analytic_distribution[str(analytic_dept.id)] = 100.0
							if analytic_cost:
								analytic_distribution[str(analytic_cost.id)] = 100.0
							if branch:
								analytic_distribution[str(branch.id)] = 100.0

							vals = {
								'account_id': request.env['account.account'].sudo().search([
									('code', '=', line['account_id'])]).id,
								'name': line['name'],
								'employee_code': line.get('employee_code', ''),
								"customer_account": existing.id,
								"customer_code": line.get('customer_code', ''),
								"operating_unit_id": line_operating_unit.id,
								'analytic_distribution': analytic_distribution or {},
								'tax_ids': [[4, line['tax_id']]] if line.get('tax_id', False) else [],
								'debit': line['amount'] if line['type'] == 'debit' else 0,
								'credit': line['amount'] if line['type'] == 'credit' else 0
							}

							line_val.append((0, 0, vals))

						auto_line = [
							(0, 0, {
								'account_id': bank_id.default_account_id.id,
								'name': '',
								"customer_account": existing.id,
								'debit': credit_side - debit_side if credit_side > debit_side else 0,
								'credit': debit_side - credit_side if debit_side > credit_side else 0
							})]
						line_ids = line_val + auto_line
						jv_data = {
							"partner_id": partner_id.id,
							"customer_code": partner_id.customer_code,
							"customer_account": existing.id,
							"operating_unit_id": operating_unit.id,
							"project_group_id": partner_id.project_group_id,
							"invoice_project_id": partner_id.invoice_project_id,
							"crm_number": post.get("crm_number"),
							"journal_id": bank_id.id,
							"date": post.get('date', fields.Date.today()),
							"line_ids": line_ids,
							"move_type": "entry",
							'jv_type': post['type']
						}
						jv = request.env['account.move'].sudo().create(jv_data)
						response.append({
							'success': True,
							'error': False,
							'message': "Insurance JV created successfully",
							'data': {
								'jv_id': jv.id,
								'crm_number': jv.crm_number
							}
						})
					except Exception as e:
						_logger.error("Error creating Insurance JV: %s", str(e))
						return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
							'success': False,
							'error': True,
							'message': str(e),
							'data': {}
						}})

				elif post['type'] == 'cost_invoice':
					try:
						required_field = {
							'crm_number': "CRM Number is required",
							'customer_account': "Customer Contract is required",
							'line_ids': "Line IDs are required",
							'operating_unit_id': "Operating unit is required"
						}
						for key, value in required_field.items():
							if not post.get(key):
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"{value}",
									'data': {}
								}})
						existing_crm = request.env['account.move'].sudo().search([
							('crm_number', '=', post['crm_number']),('jv_type','=',post['type'])
						], limit=1)
						if existing_crm:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'CRM Number already exists',
								'data': {}
							}})
						existing = request.env['partner.subscription'].sudo().search([
							('name', '=', post['customer_account'])
						], limit=1)
						if not existing:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': f"Partner having Customer Contract: {post['customer_account']} does not exists",
								'data': {}
							}})
						partner_id = existing.partner_id

						operating_unit_id = post.get('operating_unit_id', False)
						if not operating_unit_id:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'Operation Unit Not Provided',
								'data': {}
							}})

						operating_unit = request.env['operating.unit'].sudo().search([('code', '=', operating_unit_id)])
						if operating_unit_id and len(operating_unit) == 0:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'Wrong code in Operation Unit',
								'data': {}
							}})
						line_val=[]
						for line in post['line_ids']:
							line_operating_unit_id = line.get('operating_unit_id', False)
							line_operating_unit = request.env['operating.unit'].sudo().search(
								[('code', '=', line_operating_unit_id)])
							if line_operating_unit_id and len(line_operating_unit) == 0:
								return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
									'success': False,
									'error': True,
									'message': 'Wrong code in Operation Unit',
									'data': {}
								}})

							if not request.env['account.account'].sudo().search([('code', '=', line['account_id'])]):
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"CoA have code: {line['account_id']} does not exist.",
									'data': {}
								}})
							if 'employee_code' in line:
								employee_code = str(line['employee_code'])
								existing_employee = request.env['hr.employee'].sudo().search([
									('employee_code', '=', employee_code), ('active', '=', True)
								], limit=1)
								if not existing_employee:
									return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
										'success': False,
										'error': True,
										'message': 'Employee does not exists with code (%s)' % (employee_code),
										'data': {}
									}})
								line['employee_id'] = existing_employee.id

							analytic_dept = False
							if line.get('department', False):
								analytic_dept = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['department'])
								], limit=1)
								if not analytic_dept:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Department Analytic account {line['department']} does not exist",
										'data': {}
									}})
							analytic_cost = False
							if line.get('cost_center', False):
								analytic_cost = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['cost_center'])
								], limit=1)
								if not analytic_cost:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Cost Center Analytic account {line['cost_center']} does not exist",
										'data': {}
									}})
							branch = False
							if line.get('branch', False):
								branch = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['branch'])
								], limit=1)
								if not branch:
									return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
										'success': False,
										'error': True,
										'message': f"Branch Analytic account {line['branch']} does not exist",
										'data': {}
									}})
							analytic_distribution = {}
							if analytic_dept:
								analytic_distribution[str(analytic_dept.id)] = 100.0
							if analytic_cost:
								analytic_distribution[str(analytic_cost.id)] = 100.0
							if branch:
								analytic_distribution[str(branch.id)] = 100.0

							vals = {
								'account_id': request.env['account.account'].sudo().search([
									('code', '=', line['account_id'])]).id,
								'name': line['name'],
								'employee_id': line.get('employee_id', False),
								'employee_code': line.get('employee_code', ''),
								"customer_account": existing.id,
								"customer_code": line.get('customer_code', ''),
								"operating_unit_id": line_operating_unit.id,
								'analytic_distribution': analytic_distribution or {},
								'tax_ids': [[4, line['tax_id']]] if line.get('tax_id', False) else [],
								'debit': line['amount'] if line['type'] == 'debit' else 0,
								'credit': line['amount'] if line['type'] == 'credit' else 0
							}

							line_val.append((0, 0, vals))

						jv_data = {
							"partner_id": partner_id.id,
							'contract_type': partner_contract.contract_type if partner_contract else '',
							"customer_code": partner_id.customer_code,
							"customer_account": existing.id,
							"operating_unit_id": operating_unit.id,
							"project_group_id": partner_id.project_group_id,
							"invoice_project_id": partner_id.invoice_project_id,
							"crm_number": post.get("crm_number"),
							"journal_id": request.env.ref('account.1_sale').id,
							"date": post['date'],
							'jv_type': post['type'],
							"line_ids": line_val
						}
						jv = request.env['account.move'].sudo().create(jv_data)
						response.append({
							'success': True,
							'error': False,
							'message': "Cost Invoice created successfully",
							'data': {
								'contact_id': jv.id,
								'crm_number': jv.crm_number
							}
						})
					except Exception as e:
						_logger.error("Error creating Cost Invoice: %s", str(e))
						return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
							'success': False,
							'error': True,
							'message': str(e),
							'data': {}
						}})

				elif post['type'] == 'payroll':
					try:
						required_field = {
							'crm_number': "CRM Number is required",
							'line_ids': "Line IDs are required",
							'operating_unit_id': "Operating unit is required"
						}

						for key, value in required_field.items():
							if not post.get(key):
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"{value}",
									'data': {}
								}})
						journal_id = request.env['account.journal'].sudo().search([('name', '=', 'Payroll'), ('active', '=', True)],limit=1)
						if not journal_id:
							journal_id = request.env['account.journal'].sudo().search(
								[('name', 'ilike', 'Payroll'), ('active', '=', True)], limit=1)
						if not journal_id:
							journal_id = request.env['account.journal'].sudo().search([('active', '=', True)]).filtered(
								lambda m: 'payroll' in str(m.name).lower())
						if not journal_id:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'Payroll related journal does not exists',
								'data': {}
							}})
						else:
							journal_id = journal_id[0]
						if not journal_id.default_account_id:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'Payroll journal does not have any default account set.',
								'data': {}
							}})

						operating_unit_id = post.get('operating_unit_id', False)
						if not operating_unit_id:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'Operation Unit Not Provided',
								'data': {}
							}})
						operating_unit = request.env['operating.unit'].sudo().search([('code', '=', operating_unit_id)])
						if operating_unit_id and len(operating_unit) == 0:
							return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
								'success': False,
								'error': True,
								'message': 'Wrong code in Operation Unit',
								'data': {}
							}})
						line_vals = []
						for line in post['line_ids']:
							line_operating_unit_id = line.get('operating_unit_id', False)
							line_operating_unit = request.env['operating.unit'].sudo().search(
								[('code', '=', line_operating_unit_id)])
							if line_operating_unit_id and len(line_operating_unit) == 0:
								return request.make_json_response({"jsonrpc": "2.0", "id": 1, "result": {
									'success': False,
									'error': True,
									'message': 'Wrong code in Operation Unit',
									'data': {}
								}})

							for field in ['account_id', 'amount', 'type']:
								if not line.get(field):
									return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
										'success': False,
										'error': True,
										'message': f"{field.replace('_', ' ').title()} is required on each line",
										'data': {}
									}})
							account = request.env['account.account'].sudo().search([
								('code', '=', line['account_id'])
							], limit=1)
							if not account:
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"CoA have code: {line['account_id']} does not exist.",
									'data': {}
								}})
							existing_employee = False
							if line.get('employee_code'):
								employee_code = str(line['employee_code'])
								existing_employee = request.env['hr.employee'].sudo().search([
									('employee_code', '=', employee_code), ('active', '=', True)
								], limit=1)
								if not existing_employee:
									return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
										'success': False,
										'error': True,
										'message': 'Employee does not exists with code (%s)' % (employee_code),
										'data': {}
									}})
							partner_contract = False
							if line.get('customer_account'):
								partner_contract = request.env['partner.subscription'].sudo().search([
									('name', '=', line['customer_account'])
								], limit=1)
							if not partner_contract:
								return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
									'success': False,
									'error': True,
									'message': f"Partner having Customer Contract: {line['customer_account']} does not exists",
									'data': {}
								}})
							analytic_dept = False
							if line.get('department'):
								analytic_dept = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['department'])
								], limit=1)
								if not analytic_dept:
									return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
										'success': False,
										'error': True,
										'message': f"Department Analytic account {line['department']} does not exist",
										'data': {}
									}})
							analytic_cost = False
							if line.get('cost_center'):
								analytic_cost = request.env['account.analytic.account'].sudo().search([
									('code', '=', line['cost_center'])
								], limit=1)
								if not analytic_cost:
									return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
										'success': False,
										'error': True,
										'message': f"Cost Center Analytic account {line['cost_center']} does not exist",
										'data': {}
									}})
							analytic_distribution = {}
							if analytic_dept:
								analytic_distribution[str(analytic_dept.id)] = 100.0
							if analytic_cost:
								analytic_distribution[str(analytic_cost.id)] = 100.0

							vals = {
								'account_id': account.id,
								'name': line.get('name', ''),
								'employee_id': existing_employee.id if existing_employee else False,
								'employee_code': line.get('employee_code', ''),
								'partner_id': existing_employee.work_contact_id.id if existing_employee else partner_contract.partner_id.id,
								'debit': line['amount'] if line['type'] == 'debit' else 0,
								'credit': line['amount'] if line['type'] == 'credit' else 0,
								"operating_unit_id": line_operating_unit.id,
								'analytic_distribution': analytic_distribution or {},
								'customer_code': partner_contract.partner_id.customer_code,
								'customer_account': partner_contract.id if partner_contract else False,
								'contract_type': partner_contract.contract_type if partner_contract else '',
							}

							line_vals.append((0, 0, vals))

						jv_data = {
							"crm_number": post.get("crm_number"),
							"partner_id": partner_contract.partner_id.id,
							"journal_id": journal_id.id,
							"date": post.get('date') or fields.date.today(),
							"operating_unit_id": operating_unit.id if operating_unit else False,
							"line_ids": line_vals,
							'jv_type': post['type']
						}
						jv = request.env['account.move'].sudo().create(jv_data)
						response.append({
							'success': True,
							'error': False,
							'message': "Payroll Journal Entry created successfully",
							'data': {
								'contact_id': jv.id,
								'crm_number': jv.crm_number
							}
						})
					except Exception as e:
						_logger.error("Error creating Payroll Journal Entry: %s", str(e))
						return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
							'success': False,
							'error': True,
							'message': str(e),
							'data': {}
						}})

				else:
					return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
						'success': False,
						'error': True,
						'message': "Type Related Action Not Found",
						'data': {}
					}})
			else:
				return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{
					'success': False,
					'error': True,
					'message': "Type Not Provided",
					'data': {}
				}})
		if len(response) != 0:
			return request.make_json_response({"jsonrpc": "2.0", "id":1,"result": response}) if len(response) > 1 else request.make_json_response({"jsonrpc": "2.0", "id":1,"result": response[0]})
		else:
			return request.make_json_response({"jsonrpc": "2.0", "id":1,"result":{}})
