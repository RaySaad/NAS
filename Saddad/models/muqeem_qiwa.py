from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from .muqeem import MuqeemExpense, MuqeemLine


class QiwaMuqeem(models.Model):
    _inherit = 'saddad.qiwa.batch'
    muqeem_ids = fields.One2many('saddad.muqeem.expense', 'qiwa_batch_id', string='Muqeem Expenses')
    downstream_state = fields.Selection(selection_add=[('linked', 'Linked to Muqeem'), ('posted', 'Muqeem Posted')])

    @api.depends('state', 'muqeem_ids.state')
    def _compute_downstream(self):
        for rec in self:
            rec.downstream_state = 'posted' if rec.muqeem_ids.filtered(lambda e: e.state == 'posted') else 'linked' if rec.muqeem_ids else 'pending' if rec.state == 'confirmed' else 'not_ready'

    def _after_confirm(self):
        super()._after_confirm()
        for batch in self:
            batch._lock()
            if batch.state != 'confirmed':
                raise UserError(_('Confirm Qiwa before preparing a Muqeem expense.'))
            if batch.sudo().muqeem_ids:
                continue
            # Fixed, source-derived values only. Qiwa confirmation authorizes this bridge,
            # not arbitrary elevated expense creation or payment marking.
            model = self.env['saddad.muqeem.expense'].sudo().with_company(batch.company_id)
            expense = super(MuqeemExpense, model).create({'name': self.env['ir.sequence'].sudo().with_company(batch.company_id).next_by_code('saddad.muqeem.expense'),
                'company_id': batch.company_id.id, 'qiwa_batch_id': batch.id, 'reference': batch.reference,
                'journal_id': batch.company_id.saddad_bank_journal_id.id})
            for source in batch.line_ids:
                line = self.env['saddad.muqeem.line'].sudo().create({'expense_id': expense.id, 'employee_id': source.employee_id.id,
                    'product_id': source.product_id.id, 'period': source.period, 'amount': source.amount, 'tax_ids': [(5, 0, 0)]})
                super(MuqeemLine, line).write({'qiwa_line_id': source.id})
            expense._validate_lines()
            expense.message_post(body=_('Created from confirmed Qiwa batch %s. Payment marks require a separate authorized action.', batch.name))
            batch.message_post(body=_('Consolidated Muqeem expense created: %s.', expense.name))

    def action_prepare_muqeem(self):
        self._transition('confirm', 'confirmed')
        self._after_confirm()
        return self.action_open_muqeem() if len(self) == 1 else True

    def action_open_muqeem(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'res_model': 'saddad.muqeem.expense', 'view_mode': 'list,form',
                'domain': [('qiwa_batch_id', '=', self.id)]}
