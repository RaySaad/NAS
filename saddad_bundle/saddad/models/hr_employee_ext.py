# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.osv import expression


class Employee(models.Model):
    _inherit = "hr.employee"
    _rec_names_search = ['name', 'registration_number','id','identification_id']
