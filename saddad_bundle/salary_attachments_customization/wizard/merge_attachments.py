from odoo import models, fields


class MergeAttachmentWizard(models.TransientModel):
    _name = 'merge.attachment.wizard'
    _description = "Merge Salary Attachment Wizard"

    old_attachment_id = fields.Many2one('hr.salary.attachment')
    current_attachment_id = fields.Many2one('hr.salary.attachment')

    def merge_attachment(self):
        attachment_lines = self.old_attachment_id.attachment_lines.filtered(lambda l: not l.payslip_id)
        attachment_line = attachment_lines[0] if attachment_lines else False
        current_attachment_amount = self.current_attachment_id.total_amount
        self.current_attachment_id.write({
            'total_amount': (
                                    self.old_attachment_id.total_amount - self.old_attachment_id.paid_amount) + current_attachment_amount,
            'state': 'open',
            'merge_note': f"This is a merged salary attachment and have remaining amount of salary attachment {self.old_attachment_id.description}",
            'old_attachment_id': self.old_attachment_id.id,
        })
        if self.current_attachment_id.other_input_type_id.payment_type == 'with_payment':
            self.current_attachment_id.write({
                'date_start': attachment_line.date if attachment_line else self.current_attachment_id.date_start
            })
            self.current_attachment_id._compute_estimated_end()

        if self.current_attachment_id.other_input_type_id.code == 'Morror':
            self.current_attachment_id.write({
                'monthly_amount': self.current_attachment_id.total_amount
            })
        if self.current_attachment_id.salary_attachment_request_id:
            self.current_attachment_id.salary_attachment_request_id.write({
                'total_amount': self.current_attachment_id.total_amount,
                'parent_request_id': self.old_attachment_id.salary_attachment_request_id.id if self.old_attachment_id.salary_attachment_request_id else False,
                'note': f"This salary attachment have been updated by the merge of {self.old_attachment_id.salary_attachment_request_id.loan_serial_number}",
            })
        if self.old_attachment_id.salary_attachment_request_id:
            self.old_attachment_id.salary_attachment_request_id.write({
                'state': 'completed',
                'active': False
            })

        self.old_attachment_id.write({
            'state': 'close',
            'pardon_amount': 0.0,
            'merge_note': f"This salary attachment have been merged to {self.current_attachment_id.description}",
            'active': False
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Salary Attachment',
            'res_model': 'hr.salary.attachment',
            'view_mode': 'form',
            'view_id': self.env.ref('hr_payroll.hr_salary_attachment_view_form').id,
            'target': 'current',
            'res_id': self.current_attachment_id.id,
        }

    def return_to_existing_attachment(self):
        pass
