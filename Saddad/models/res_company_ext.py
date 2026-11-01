# -*- coding: utf-8 -*-
from odoo import models, api, fields
from odoo.osv import expression


class ResCompanyExt(models.Model):
    _inherit = "res.company"

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if name:
            search_domain = [('name', operator, name)]
            domain = expression.AND([search_domain, domain])
        return self.sudo()._search(domain, limit=limit, order=order)

    @api.depends('name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name