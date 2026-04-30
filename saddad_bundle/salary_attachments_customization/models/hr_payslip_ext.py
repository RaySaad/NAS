from odoo import models, fields, api


class Payroll(models.Model):
    _inherit = "hr.payslip"

    def employee_domain(self):
        return ['|', ('company_id', '=', self.env.company.id), ('company_id', 'in', self.env.company.child_ids.ids)]
    


    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, domain=employee_domain)

    @api.depends('employee_id', 'contract_id', 'struct_id', 'date_from', 'date_to', 'struct_id')
    def _compute_input_line_ids(self):
        super()._compute_input_line_ids()
        for slip in self:
            if slip.employee_id and slip.date_from:
                attachment_lines = self.env['hr.salary.attachment.line'].search([
                    ('attachment_id.employee_ids', 'in', slip.employee_id.ids),
                    ('date', '=', slip.date_from)
                ])

                for line in attachment_lines:
                    input_type = line.attachment_id.other_input_type_id
                    existing_input = slip.input_line_ids.filtered(lambda x: x.input_type_id == input_type)

                    if line.state == 'draft' and existing_input:
                        existing_input = existing_input[0]
                        existing_input.write({
                            'amount': line.amount,
                            'name': existing_input.name + ' ' + line.attachment_id.salary_attachment_request_id.loan_serial_number if line.attachment_id.salary_attachment_request_id else existing_input.name})
                    elif line.state in ('postponed', 'pardoned') and existing_input:
                        slip['input_line_ids'] = False

    @api.model_create_multi
    def create(self, vals_list):
        """
           This method is to update salary slip id and paid amount on the relevant installment line in salary attachment
           """
        records = super(Payroll, self).create(vals_list)
        for res in records:
            if res.salary_attachment_ids:
                for attachment in res.salary_attachment_ids:
                    relevant_attachment_line = attachment.attachment_lines.filtered(lambda l: l.date == res.date_from)
                    if res.input_line_ids:
                        relevant_slip_line = res.input_line_ids.filtered(
                            lambda l: l.input_type_id.code == attachment.other_input_type_id.code)

                        relevant_attachment_line.update({
                            'payslip_id': res.id,
                            'paid_amount': relevant_slip_line.amount,
                            'input_line_id': relevant_slip_line.id,
                        })
        return records

    def _update_attachment_lines(self, payslip_id=False, paid_amount=0, input_line_id=False, state='draft'):
        """Helper method to update attachment lines"""
        for rec in self:
            if rec.salary_attachment_ids:
                for attachment in rec.salary_attachment_ids:
                    relevant_attachment_line = attachment.attachment_lines.filtered(lambda l: l.date == rec.date_from)
                    if rec.input_line_ids:
                        relevant_slip_line = rec.input_line_ids.filtered(
                            lambda l: l.input_type_id.code == attachment.other_input_type_id.code)

                        relevant_attachment_line.update({
                            'payslip_id': payslip_id,
                            'paid_amount': paid_amount,
                            'input_line_id': input_line_id,
                            'state':'draft'
                        })

    def action_payslip_cancel(self):
        res = super().action_payslip_cancel()
        self._update_attachment_lines()
        return res

    def action_payslip_draft(self):
        res = super().action_payslip_draft()
        for rec in self:
            if rec.state == 'draft' and rec.salary_attachment_ids and rec.input_line_ids:
                relevant_slip_line = rec.input_line_ids.filtered(
                    lambda l: l.input_type_id.code in rec.salary_attachment_ids.mapped('other_input_type_id.code'))
                if relevant_slip_line:
                    for line in relevant_slip_line:
                        rec._update_attachment_lines(
                            payslip_id=rec.id,
                            paid_amount=line.amount,
                            input_line_id=line.id,
                    )
        return res


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    def unlink(self):
        """
        This method is to remove salary slip id and paid amount on the relevant installment line in salary attachment
        """
        for rec in self:
            relevant_attachment_line = self.env['hr.salary.attachment.line'].search(
                [('input_line_id', '=', rec.id), ('date', '=', rec.payslip_id.date_from)])
            if relevant_attachment_line:
                relevant_attachment_line.update({
                    'payslip_id': False,
                    'paid_amount': 0,
                    'input_line_id': False,
                    'state': 'draft'
                })
        """ Override unlink to stop the deletion on records if not in draft state. """
        res = super(HrPayslipInput, self).unlink()
        return res

