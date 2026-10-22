from odoo import api, models, _
from odoo.exceptions import UserError



class ServiceAccounting(models.Model):
    _inherit = 'account.move'

    def _saddad_services_sources(self):
        return self.env['saddad.service.request'].sudo().search([('move_id', 'in', (self | self.deferred_original_move_ids).ids), ('state', '=', 'posted')])

    def _get_deferred_entries_method(self):
        if self.move_type == 'entry' and self.env['saddad.service.request'].sudo().search_count([('move_id', '=', self.id)]):
            return 'manual'
        return super()._get_deferred_entries_method()

    def button_draft(self):
        if self._saddad_services_sources():
            raise UserError(_('Posted Saddad entries cannot be reset independently of their expense.'))
        return super().button_draft()

    def button_cancel(self):
        if self._saddad_services_sources():
            raise UserError(_('Posted Saddad entries cannot be cancelled independently of their expense.'))
        return super().button_cancel()

    def unlink(self):
        if self._saddad_services_sources():
            raise UserError(_('Posted Saddad entries and schedules cannot be deleted.'))
        return super().unlink()

    def write(self, vals):
        if {'date', 'journal_id', 'company_id', 'line_ids', 'auto_post', 'deferred_original_move_ids', 'deferred_move_ids'}.intersection(vals) and self._saddad_services_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        if vals.get('state') in ('draft', 'cancel') and self._saddad_services_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        return super().write(vals)

    def copy(self, default=None):
        if self._saddad_services_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        return super().copy(default)

    def _reverse_moves(self, default_values_list=None, cancel=False):
        if self._saddad_services_sources():
            raise UserError(_('A linked Saddad reversal requires an expense reversal workflow.'))
        return super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)


class ServiceAccountingLine(models.Model):
    _inherit = 'account.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        moves = self.env['account.move'].browse([v['move_id'] for v in vals_list if v.get('move_id')])
        if moves._saddad_services_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'analytic_distribution', 'product_id', 'account_id', 'debit', 'credit', 'balance', 'amount_currency', 'currency_id', 'partner_id', 'tax_ids', 'tax_repartition_line_id', 'deferred_start_date', 'deferred_end_date', 'deferred_expense_account_override_id', 'move_id'}.intersection(vals) and self.move_id._saddad_services_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        return super().write(vals)

    def unlink(self):
        if self.move_id._saddad_services_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        return super().unlink()


