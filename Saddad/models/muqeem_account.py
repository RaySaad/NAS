from odoo import api, models, Command, _
from odoo.exceptions import UserError, ValidationError


_BUILD_TOKEN = object()

class MuqeemAccounting(models.Model):
    _inherit = 'account.move'

    def _saddad_sources(self):
        return self.env['saddad.muqeem.expense'].sudo().search([('move_id', 'in', (self | self.deferred_original_move_ids).ids), ('state', '=', 'posted')])

    def _get_deferred_entries_method(self):
        if self.move_type == 'entry' and self.env['saddad.muqeem.expense'].sudo().search_count([('move_id', '=', self.id)]):
            return 'manual'
        return super()._get_deferred_entries_method()

    def button_draft(self):
        if self._saddad_sources():
            raise UserError(_('Posted Saddad entries cannot be reset independently of their expense.'))
        return super().button_draft()

    def button_cancel(self):
        if self._saddad_sources():
            raise UserError(_('Posted Saddad entries cannot be cancelled independently of their expense.'))
        return super().button_cancel()

    def unlink(self):
        if self._saddad_sources():
            raise UserError(_('Posted Saddad entries and schedules cannot be deleted.'))
        return super().unlink()

    def write(self, vals):
        if {'date', 'journal_id', 'company_id', 'line_ids', 'auto_post', 'deferred_original_move_ids', 'deferred_move_ids'}.intersection(vals) and self.env.context.get('_saddad_build') is not _BUILD_TOKEN and self._saddad_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        if vals.get('state') in ('draft', 'cancel') and self._saddad_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        return super().write(vals)

    def copy(self, default=None):
        if self._saddad_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        return super().copy(default)

    def _reverse_moves(self, default_values_list=None, cancel=False):
        if self._saddad_sources():
            raise UserError(_('A linked Saddad reversal requires an expense reversal workflow.'))
        return super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)


class MuqeemAccountingLine(models.Model):
    _inherit = 'account.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        moves = self.env['account.move'].browse([v['move_id'] for v in vals_list if v.get('move_id')])
        if self.env.context.get('_saddad_build') is not _BUILD_TOKEN and moves._saddad_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'account_id', 'debit', 'credit', 'balance', 'amount_currency', 'currency_id', 'partner_id', 'tax_ids', 'tax_repartition_line_id', 'deferred_start_date', 'deferred_end_date', 'deferred_expense_account_override_id', 'move_id'}.intersection(vals) and self.env.context.get('_saddad_build') is not _BUILD_TOKEN and self.move_id._saddad_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        return super().write(vals)

    def unlink(self):
        if self.move_id._saddad_sources():
            raise UserError(_('Posted Saddad accounting values are locked.'))
        return super().unlink()


class MuqeemDeferral(models.Model):
    _inherit = 'saddad.muqeem.expense'

    def _generate_deferrals(self):
        self.ensure_one()
        if self.state != 'posted' or not self.line_ids.filtered('defer_expense'):
            return
        move = self.move_id.sudo().with_company(self.company_id)
        if move.deferred_move_ids:
            raise UserError(_('Deferred entries already exist for this expense.'))
        journal = self.company_id.deferred_expense_journal_id.sudo()
        entries = self.env['account.move'].sudo().with_company(self.company_id).with_context(_saddad_build=_BUILD_TOKEN)
        for source in self.line_ids.filtered('defer_expense'):
            if not source.paid:
                raise ValidationError(_('Only paid lines can generate deferred entries.'))
            line = source.move_line_id.sudo().with_company(self.company_id)
            # Optional Deferred Expense Account by Product integration. Resolve on
            # the source line in its own company, once for the entire schedule.
            account = self.env['account.account'].sudo()
            if 'deferred_expense_account_override_id' in line._fields:
                account = line.deferred_expense_account_override_id
            product = line.product_id.product_tmpl_id
            if not account and product and 'property_deferred_expense_account_id' in product._fields:
                account = product.property_deferred_expense_account_id
                category = product.categ_id
                seen = set()
                while not account and category and category.id not in seen:
                    seen.add(category.id)
                    if 'property_deferred_expense_account_categ_id' in category._fields:
                        account = category.property_deferred_expense_account_categ_id
                    category = category.parent_id
            account = account or self.company_id.deferred_expense_account_id.sudo()
            if not account or not account.active or self.company_id not in account.company_ids or account.account_type not in ('asset_current', 'asset_prepayments', 'asset_non_current') or not journal or journal.company_id != self.company_id or journal.type != 'general' or not journal.active:
                raise ValidationError(_('Configure a valid active deferred asset account for the product or company and an active general journal for this company.'))
            periods = line._get_deferred_periods()
            if not periods:
                continue
            # Native Odoo computes periods and recognition amounts using company method.
            # Explicit expense direction avoids invoice-type inference on a direct JV.
            amounts = move._get_deferred_amounts_by_line(line, periods, 'expense')[0]
            ref = '%s / %s' % (self.name, source.id)
            def make_entry(date, commands):
                entry = entries.create({'move_type': 'entry', 'journal_id': journal.id, 'company_id': self.company_id.id,
                    'date': date, 'ref': ref, 'auto_post': 'at_date',
                    'deferred_original_move_ids': [Command.set(move.ids)]})
                # Native deferred linkage must exist before lines to suppress product taxes.
                entry.write({'line_ids': commands})
                return entry
            base = self.env['account.move.line'].sudo()
            transfer = [Command.create(base._get_deferred_lines_values(ac.id, sign * line.balance, ref, line.analytic_distribution, line))
                        for ac, sign in [(line.account_id, -1), (account, 1)]]
            pending = make_entry(move.date, transfer)
            remaining = line.balance
            for index, period in enumerate(periods):
                amount = remaining if index == len(periods)-1 else min(remaining, max(0, self.currency_id.round(amounts[period])))
                remaining = self.currency_id.round(remaining - amount)
                if self.currency_id.is_zero(amount):
                    continue
                pending |= make_entry(period[1], move._get_deferred_lines(line, account, 'expense', period, ref, force_balance=amount))
            pending._post(soft=True)
