# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PostponeRequest(models.TransientModel):
    _name = 'postpone.request'
    _description = 'Postpone Request'

    reason = fields.Char(string="Reason")
    adjustment_type = fields.Selection([('distribution', 'Distribution'), ('new_installment', 'New Installment')],
                                       string="Adjustment Type")
    loan_line_id = fields.Many2one('hr.salary.attachment.line')

    def action_submit(self):
        if self.adjustment_type == 'distribution':
            # Set current line state to postponed
            self.loan_line_id.write({'state': 'postponed'})
            # Get all other draft installments from the same attachment
            other_lines = self.loan_line_id.attachment_id.attachment_lines.filtered(
                lambda line: line.state == 'draft' and line.id != self.loan_line_id.id
            )
            if other_lines:
                # Distribute the postponed amount among other installments
                distribution_amount = self.loan_line_id.amount / len(other_lines)
                for line in other_lines:
                    line.write({'amount': line.amount + distribution_amount})
        
        elif self.adjustment_type == 'new_installment':
            # Set current line state to postponed
            self.loan_line_id.write({'state': 'postponed'})
            
            # Find the last installment date
            last_line = self.loan_line_id.attachment_id.attachment_lines.sorted('date', reverse=True)[0]
            from dateutil.relativedelta import relativedelta
            next_date = last_line.date + relativedelta(months=1)
            
            # Create a new installment with the same amount
            self.env['hr.salary.attachment.line'].create({
                'attachment_id': self.loan_line_id.attachment_id.id,
                'amount': self.loan_line_id.amount,
                'date': next_date,
                'state': 'draft'
            })
