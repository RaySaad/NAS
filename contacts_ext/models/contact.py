# -*- coding: utf-8 -*-

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_code = fields.Char(string='Customer Code', tracking=True)
    identification_number = fields.Char(string='Identification Number', tracking=True)
    country_code = fields.Char(string='Country Code', tracking=True)
    second_mobile = fields.Char(string='Mobile 2', tracking=True)
    job_title = fields.Char(string='Job Title', tracking=True)
    working_place = fields.Char(string='Job City', tracking=True)
    gender = fields.Selection(
        [('male', 'Male'),
         ('female', 'Female')],
        string='Gender',
        tracking=True
    )
    _sql_constraints = [
        ('identification_number_unique', 'unique(identification_number)', 'Identification Number must be unique!'),
    ]

    currency = fields.Char(string='Currency ', tracking=True)  # todo: need to remove this beacuse its already define
    lock_sale_currency = fields.Integer(string='Project Lock Sales Currency', tracking=True)
    forecast_invoice_frequency = fields.Integer(string='Forecast Invoice Frequency', tracking=True)
    project_group_id = fields.Char(string='Project Group ID', tracking=True)
    invoice_project_id = fields.Char(string='Project ID', tracking=True)
    labor_office_no = fields.Char(string='Labor Office No#', tracking=True)
    registration_no = fields.Char(string='Registration No#', tracking=True)
    subscription_id = fields.One2many('partner.subscription', 'partner_id')


class PartnersSubscriptions(models.Model):
    _name = 'partner.subscription'
    _description = "Partners Subscriptions"

    name = fields.Char("Customer Contract")
    partner_id = fields.Many2one('res.partner', ondelete='cascade')
    contract_name = fields.Char("Contract Name")
    contract_type = fields.Char("Contract Type")

    _sql_constraints = [('name_uniq', "unique(name)", "Customer Contract already exist.")]
