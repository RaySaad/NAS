# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from email.policy import default

from odoo import fields, models


class HrSalaryAttachmentType(models.Model):
    _inherit = 'hr.payslip.input.type'

    payment_type = fields.Selection([
        ('with_payment', 'With Payment'),
        ('without_payment', 'WithOut Payment'),
    ], default='with_payment', required=True, string='Type')
    company_id = fields.Many2one('res.company',default=lambda self: self.env.company)
    # employee_payment_type_id = fields.Many2one('employee.payment.type')
