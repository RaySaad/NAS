# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.osv import expression


class Billers(models.Model):
    _name = 'billers'
    _description = 'Billers'

    def _partner_domain(self):
        return [('company_id', '=', self.env.company.id)]

    partner_id = fields.Many2one('res.partner', domain=_partner_domain, required=True)
    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            name = rec.name or ''
            rec.display_name = "[%s] %s" % (rec.code or '', name)

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if name:
            search_domain = ['|', ('name', operator, name), ('code', 'ilike', name)]
            domain = expression.AND([search_domain, domain])
        return self._search(domain, limit=limit, order=order)
