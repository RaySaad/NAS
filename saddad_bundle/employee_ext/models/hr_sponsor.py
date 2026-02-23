# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HRSponsors(models.Model):
    _name = 'hr.sponsors'
    _description = "HR Sponsors"

    name = fields.Char(string='Name(s)', required=True)
    identification_no = fields.Char(string='Identification Number(s)', required=True)
