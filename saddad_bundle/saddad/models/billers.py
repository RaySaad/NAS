# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.osv import expression


class Billers(models.Model):
    _name = 'billers'
    _description = 'Bullers'
    _rec_names_search = ['name', 'code']

    def _partner_domain(self):
        return [('company_id', '=', self.env.company.id)]

    partner_id = fields.Many2one('res.partner', domain=_partner_domain, required=True)
    name = fields.Char('Name', required=True, translate=True)

    code = fields.Char(string='Code', required=True, )

    def name_get(self, arab=False):
        result = []
        for rec in self:
            lang = self._context.get('lang', False)
            name = rec.name or rec.name
            if lang == 'ar_SY':
                name = rec.name or rec.name
            name = "[%s] %s" % (rec.code or '', name)
            result.append((rec.id, name))
        return result
