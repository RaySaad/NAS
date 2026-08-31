# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import datetime
from odoo.tools import format_date
from num2words import num2words
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    period_id = fields.Many2one('periods', 'Period', readonly=True, compute="get_period")
    year_open_id = fields.Many2one('fiscal.year', 'open year')
    year_close_id = fields.Many2one('fiscal.year', 'close year')
    fiscal_year_lock_date_message = fields.Char(
        help="Technical field used to display a message when the invoice's accounting date is prior of the fiscal year lock date.")


    def _post(self, soft=True):
        for move in self:
            date = move.date or fields.Date.context_today(move)
            if move.period_id:
                if move.period_id.state != 'active':
                    is_journal_in_year = move.journal_id in move.period_id.lock_journal_ids
                    is_date_in_period = move.period_id.date_start <= date <= move.period_id.date_end

                    if move.period_id.lock_journal_ids:
                        if is_journal_in_year and is_date_in_period:
                            lock_date_access = move.period_id.lock_date_access
                            if lock_date_access == 'for_all':
                                raise ValidationError(
                                    _("This entry cannot be post because the period %(period_name)s "
                                      "(from %(date_start)s to %(date_end)s) is locked.",
                                      period_name="%s - %s" % (move.company_id.name or '', move.period_id.name),
                                      date_start=format_date(move.env, move.period_id.date_start),
                                      date_end=format_date(move.env, move.period_id.date_end)
                                      )
                                )
                            else:
                                is_advisor = self.env.user.has_groups("account.group_account_manager")
                                if not is_advisor:
                                    raise ValidationError(
                                        _("This entry cannot be post because the period %(period_name)s "
                                          "(from %(date_start)s to %(date_end)s) is locked.",
                                          period_name="%s - %s" % (
                                          move.company_id.name or '', move.period_id.name),
                                          date_start=format_date(move.env, move.period_id.date_start),
                                          date_end=format_date(move.env, move.period_id.date_end)
                                          )
                                    )
                    else:
                        if is_date_in_period:
                            lock_date_access = move.period_id.lock_date_access
                            if lock_date_access == 'for_all':
                                raise ValidationError(
                                    _("This entry cannot be post because the period %(period_name)s "
                                      "(from %(date_start)s to %(date_end)s) is locked.",
                                      period_name="%s - %s" % (move.company_id.name or '', move.period_id.name),
                                      date_start=format_date(move.env, move.period_id.date_start),
                                      date_end=format_date(move.env, move.period_id.date_end)
                                      )
                                )
                            else:
                                is_advisor = self.env.user.has_groups("account.group_account_manager")
                                if not is_advisor:
                                    raise ValidationError(
                                        _("This entry cannot be post because the period %(period_name)s "
                                          "(from %(date_start)s to %(date_end)s) is locked.",
                                          period_name="%s - %s" % (
                                          move.company_id.name or '', move.period_id.name),
                                          date_start=format_date(move.env, move.period_id.date_start),
                                          date_end=format_date(move.env, move.period_id.date_end)
                                          )
                                    )
        res = super()._post(soft)
        return res

    def button_draft(self):
        for move in self:
            if move.period_id and move.period_id.state not in ['active']:
                date = move.date
                is_journal_in_year = move.journal_id in move.period_id.lock_journal_ids
                is_date_in_period = move.period_id.date_start <= date <= move.period_id.date_end

                if move.period_id.lock_journal_ids:
                    if is_journal_in_year and is_date_in_period:
                        lock_date_access = move.period_id.lock_date_access
                        if lock_date_access == 'for_all':
                            raise ValidationError(
                                _("This entry cannot be reset to draft because the period %(period_name)s "
                                  "(from %(date_start)s to %(date_end)s) is locked.",
                                  period_name="%s - %s" % (move.company_id.name or '', move.period_id.name),
                                  date_start=format_date(move.env, move.period_id.date_start),
                                  date_end=format_date(move.env, move.period_id.date_end)
                                  )
                            )
                        else:
                            is_advisor = self.env.user.has_groups("account.group_account_manager")
                            if not is_advisor:
                                raise ValidationError(
                                    _("This entry cannot be reset to draft because the period %(period_name)s "
                                      "(from %(date_start)s to %(date_end)s) is locked.",
                                      period_name="%s - %s" % (move.company_id.name or '', move.period_id.name),
                                      date_start=format_date(move.env, move.period_id.date_start),
                                      date_end=format_date(move.env, move.period_id.date_end)
                                      )
                                )
                else:
                    if is_date_in_period:
                        lock_date_access = move.period_id.lock_date_access
                        if lock_date_access == 'for_all':
                            raise ValidationError(
                                _("This entry cannot be reset to draft because the period %(period_name)s "
                                  "(from %(date_start)s to %(date_end)s) is locked.",
                                  period_name="%s - %s" % (move.company_id.name or '', move.period_id.name),
                                  date_start=format_date(move.env, move.period_id.date_start),
                                  date_end=format_date(move.env, move.period_id.date_end)
                                  )
                            )
                        else:
                            is_advisor = self.env.user.has_groups("account.group_account_manager")
                            if not is_advisor:
                                raise ValidationError(
                                    _("This entry cannot be reset to draft because the period %(period_name)s "
                                      "(from %(date_start)s to %(date_end)s) is locked.",
                                      period_name="%s - %s" % (move.company_id.name or '', move.period_id.name),
                                      date_start=format_date(move.env, move.period_id.date_start),
                                      date_end=format_date(move.env, move.period_id.date_end)
                                      )
                                )

        res = super(AccountMove, self).button_draft()
        return res

    @api.constrains('date')
    def check_period_for_this_date(self):
        for rec in self:
            period = self.env['periods'].search([['date_start', '<=', rec.date], ['date_end', '>=', rec.date],
                                                 ['company_id', '=', rec.company_id.id]])
            if not period:
                raise ValidationError(_(
                    "It seems that there is no active period for the selected date... In order to accept this transaction \
                    you have to communicate with your financial manager to create or activate a financial period for the \
                    selected date"))
            if period.year_id.state != 'active':
                raise ValidationError(_(
                    "It seems that there is no active financial year for the selected date... In order to accept this \
                    transaction you have to communicate with your financial manager to create or activate a financial \
                    period for the selected date"))

    @api.depends('invoice_date', 'date', 'invoice_payment_term_id')
    def get_period(self):
        for rec in self:
            period = self.env['periods'].get_default_period(rec.date, rec.company_id)
            rec.period_id = period and period.id or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            date = datetime.date.today()
            if 'date' in vals:
                if vals['date']:
                    periods = self.env['periods'].search(
                        [['date_start', '<=', vals['date']], ['date_end', '>=', vals['date']],
                         ['company_id', '=', self.env.company.id]])
                else:
                    periods = self.env['periods'].search(
                        [['date_start', '<=', date], ['date_end', '>=', date], ['company_id', '=', self.env.company.id]])
            else:
                periods = self.env['periods'].search(
                    [['date_start', '<=', date], ['date_end', '>=', date], ['company_id', '=', self.env.company.id]])
            period = False
            for p in periods:
                period = p
                break
            if period:
                vals['period_id'] = period.id
        return super(AccountMove, self).create(vals_list)

    def write(self, vals):
        res = super(AccountMove, self).write(vals)
        if 'tax_totals_json' not in vals:
            for move in self:
                if move.period_id:
                    if move.period_id.state != 'active':
                        date = move.date or fields.Date.context_today(move)
                        is_journal_in_year = move.journal_id in move.period_id.lock_journal_ids
                        is_date_in_period = move.period_id.date_start <= date <= move.period_id.date_end

                        if move.period_id.lock_journal_ids:
                            if is_journal_in_year and is_date_in_period:
                                lock_date_access = move.period_id.lock_date_access
                                if lock_date_access == 'for_all':
                                    raise ValidationError(
                                        _("This entry cannot be edit/save because the period %(period_name)s "
                                          "(from %(date_start)s to %(date_end)s) is locked. Please update the accounting date.",
                                          period_name="%s - %s" % (
                                          move.company_id.name or '', move.period_id.name),
                                          date_start=format_date(move.env, move.period_id.date_start),
                                          date_end=format_date(move.env, move.period_id.date_end)
                                          )
                                    )
                                else:
                                    is_advisor = self.env.user.has_groups("account.group_account_manager")
                                    if not is_advisor:
                                        raise ValidationError(
                                            _("This entry cannot be edit/save because the period %(period_name)s "
                                              "(from %(date_start)s to %(date_end)s) is locked. Please update the accounting date.",
                                              period_name="%s - %s" % (
                                              move.company_id.name or '', move.period_id.name),
                                              date_start=format_date(move.env, move.period_id.date_start),
                                              date_end=format_date(move.env, move.period_id.date_end)
                                              )
                                        )
                        else:
                            if is_date_in_period:
                                lock_date_access = move.period_id.lock_date_access
                                if lock_date_access == 'for_all':
                                    raise ValidationError(
                                        _("This entry cannot be edit/save because the period %(period_name)s "
                                          "(from %(date_start)s to %(date_end)s) is locked. Please update the accounting date.",
                                          period_name="%s - %s" % (
                                          move.company_id.name or '', move.period_id.name),
                                          date_start=format_date(move.env, move.period_id.date_start),
                                          date_end=format_date(move.env, move.period_id.date_end)
                                          )
                                    )
                                else:
                                    is_advisor = self.env.user.has_groups("account.group_account_manager")
                                    if not is_advisor:
                                        raise ValidationError(
                                            _("This entry cannot be edit/save because the period %(period_name)s "
                                              "(from %(date_start)s to %(date_end)s) is locked. Please update the accounting date.",
                                              period_name="%s - %s" % (
                                              move.company_id.name or '', move.period_id.name),
                                              date_start=format_date(move.env, move.period_id.date_start),
                                              date_end=format_date(move.env, move.period_id.date_end)
                                              )
                                        )
        return res

    def unlink(self):
        for rec in self:
            if rec.period_id.state != 'active' and not rec.env.context.get('force_edit', False):
                raise ValidationError(
                    _("You can't delete that journal entry %s because period '%s isn't active\nPlease open it first to ba able to edit in it" % (
                        rec.name, rec.period_id.code)))
        return super(AccountMove, self).unlink()






    # ----------------------------------------------------------------
