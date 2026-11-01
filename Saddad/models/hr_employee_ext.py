# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.osv import expression


class Employee(models.Model):
    _inherit = "hr.employee"

    # @api.model
    # def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
    #     args = args or []
    #     domain = []
    #     if name:
    #         domain = ['|', ('employee_english_name', operator, name), ('name', operator, name)]
    #     return self.sudo()._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

    # def name_get(self, arab=False):
    #     result = []
    #     for rec in self:
    #         lang = self._context.get('lang', False)
    #         name = rec.name
    #         if lang == 'ar_001' and rec.name:
    #             name = "[%s] %s" % (rec.employee_number or '', rec.name)
    #         if lang == 'en_US':
    #             name = "[%s] %s" % (rec.employee_number or '', rec.employee_english_name)
    #         result.append((rec.id, name))
    #
    #     return result

    def write(self, vals):
        res = super().write(vals)
        # extended write method of employee to delete the document renewal entry
        if 'iqama_expiry_date' in vals:
            renewal_request = self.env['document.renewal'].search(
                [('employee_id', '=', self.id), ('state', '=', 'draft')])
            if renewal_request:
                renewal_request.unlink()
        return res
