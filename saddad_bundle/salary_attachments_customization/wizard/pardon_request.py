# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PardonRequest(models.TransientModel):
    _name = 'pardon.request'
    _description = 'Pardon Request'

    reason = fields.Char(string="Reason")
    attachment_id = fields.Many2one('hr.salary.attachment')
    loan_line_id = fields.Many2one('hr.salary.attachment.line')

    def action_submit(self):
        attachment_id = self.env['hr.salary.attachment.request'].browse(self._context.get('active_id'))
        attachment_id.write({
            'pardon_reason': self.reason,
            'state': 'requested_pardon'
        })

    def action_loan_line_pardon(self):
        loan_line_id = self.env['hr.salary.attachment.line'].browse(self._context.get('active_id'))
        loan_line_id.write({
            'pardon_reason': self.reason,
            'state': 'pardoned'
        })
        loan_line_id.attachment_id.write({
            'pardon_amount': self.loan_line_id.attachment_id.pardon_amount + loan_line_id.amount,
        })
