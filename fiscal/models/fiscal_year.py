# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import datetime
from odoo.exceptions import UserError, ValidationError


class FiscalYear(models.Model):
    _name = 'fiscal.year'
    _description = "Fiscal year"
    _inherit = ['mail.thread', ]

    state = fields.Selection([('new', 'New'), ('active', 'Active'), ('freeze', 'Freeze'), ('close', 'Close')],
                             string="Status", default='new')
    name = fields.Char('Fiscal Year name', default=lambda s: datetime.datetime.now().year)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    code = fields.Char('Code', compute="_get_dates", store=True)
    start_date = fields.Date('Date Start', compute="_get_dates", store=True)
    start_end = fields.Date('Date End', compute="_get_dates", store=True)
    period_ids = fields.One2many('periods', 'year_id', 'Periods')
    note = fields.Html('Notes')
    open_journal_id = fields.Many2one('account.move', 'Opening Journal Entry')
    close_move_id = fields.Many2one('account.move', 'Close Journal Entry')
    close_journal_id = fields.Many2one('account.journal', 'Close Journal')
    close_account_id = fields.Many2one('account.account', 'Close Account')

    open_journal_lines_ids = fields.One2many('account.move.line', 'year_open_id', 'Opening Journal Lines')
    close_journal_lines_ids = fields.One2many('account.move.line', 'year_close_id', 'Closing Journal Lines')

    periods_count = fields.Integer('Number of periods', compute='no_of_periods')
    total_expenses = fields.Float('Total expenses', compute='_get_net_profit')
    total_income = fields.Float('Total Income', compute='_get_net_profit')
    net_profit = fields.Float('Net profit', compute='_get_net_profit')

    _sql_constraints = [('name', 'unique(name, company_id)', 'Period must be unique per company.')]

    def name_get(self, arab=False):
        result = []
        for record in self:
            name = "%s- %s" % (record.company_id.short_name or '', record.name)
            result.append((record.id, name))
        return result

    @api.model
    def where_cluster(self):
        return " parent_state = 'posted' and date >='%s' and date <='%s'" % (self.start_date, self.start_end)

    def _get_net_profit(self):
        for rec in self:
            accounts_in = self.env['account.account'].search([['account_type', 'in', ['income']]])
            accounts_ex = self.env['account.account'].search([['account_type', 'in', ['expense']]])
            total_ex = total_in = 0
            if accounts_in:
                Accounts = [str(a.id) for a in accounts_in]
                Accounts = ','.join(Accounts)
                sql_in = "select sum(credit - debit), sum(credit), sum(debit) from account_move_line where account_id in(%s) and %s" % (
                    Accounts, rec.where_cluster())
                rec.env.cr.execute(sql_in)
                rows = rec.env.cr.fetchall()
                total_in = rows[0][0] or 0
                rec.total_income = total_in
            else:
                rec.total_income = 0
            if accounts_ex:
                Accounts = [str(a.id) for a in accounts_ex]
                Accounts = ','.join(Accounts)
                sql_ex = "SELECT sum(debit)- sum(credit) FROM account_move_line WHERE account_id in(%s) AND %s" % (
                    Accounts, rec.where_cluster())
                rec.env.cr.execute(sql_ex)
                rows = rec.env.cr.fetchall()
                total_ex = rows[0][0] or 0
                rec.total_expenses = total_ex
            else:
                rec.total_expenses = 0
            rec.net_profit = total_in - total_ex

    def generate_close_move(self):
        accounts = self.env['account.account'].search([['account_type', 'in', ['income', 'expense']]])
        if not accounts:
            raise ValidationError(_("No Income or expense account"))
        if not self.close_account_id:
            raise ValidationError(_("Please assign Close Account to close Profit and loss in it"))
        if not self.close_journal_id:
            raise ValidationError(_("Please specify Close Journal"))
        Accounts = [str(a.id) for a in accounts]
        Accounts = ','.join(Accounts)
        sql = """SELECT account_id, SUM(debit) , SUM(credit)
                 FROM account_move_line
                 WHERE account_id IN(%s) AND %s AND NOT (debit=0 AND credit=0)
                 GROUP BY account_id
                 ORDER BY account_id """ % (Accounts, self.where_cluster())
        self.env.cr.execute(sql)
        rows = self.env.cr.fetchall()
        ctx = dict(self.env.context.copy(), check_move_validity=False)
        total = 0
        lines = []
        seq = 0
        for row in rows:
            seq += 1
            debit = row[1]
            credit = row[2]
            balance = abs(debit - credit)
            new_debit = (credit > debit) and balance or 0
            new_credit = (debit > credit) and balance or 0
            total = total + new_debit - new_credit
            vals = {
                # 'move_id': move.id,
                'sequence': seq,
                'name': 'Close %s' % self.name,
                'debit': new_debit,
                'credit': new_credit,
                'account_id': row[0],
                # 'analytic_account_id': row[3],
                'date': _(self.start_end),
                'date_maturity': _(self.start_end),
            }
            lines.append((0, 0, vals))

        if total:
            diff_vals = {
                'sequence': seq + 1,
                'name': 'Close %s' % self.name,
                'account_id': self.close_account_id.id,
                'debit': total < 0 and total or 0.0,
                'credit': total > 0 and total or 0.0,
                # 'analytic_account_id': False,
                'date': _(self.start_end),
                'date_maturity': _(self.start_end),
            }
            lines.append((0, 0, diff_vals))
        move_vals = {
            'journal_id': self.close_journal_id.id,
            'date': _(self.start_end),
            'ref': 'Close %s' % self.name,
            'line_ids': lines
        }
        move = self.with_context(ctx).env['account.move'].create(move_vals)
        self.close_move_id = move.id

    @api.onchange('name')
    def onchange_name(self):
        name = ''
        no_no = ''
        for c in self.name or '':
            if c in '0123456789':
                name += c
            else:
                no_no += c
        self.name = self.code = name
        if name and (float(name) > 2100 or float(name) < 2000):
            raise ValidationError(_("Financial year must be between 2000 and 2100"))
        if no_no != '':
            return {'warning': {'title': _('Name Error'),
                                'message': _('You can not user this (%s) in period name.' % no_no)}}

    @api.depends('name')
    def _get_dates(self):
        for rec in self:
            if rec.name:
                rec.code = rec.name
                rec.start_date = str(rec.name) + '-01-01'
                rec.start_end = str(rec.name) + '-12-31'

    @api.depends('period_ids')
    def no_of_periods(self):
        for rec in self:
            rec.periods_count = len(rec.period_ids)

        def active(self):
            self.state = 'active'
            for month in range(1, 12):
                self.env['periods'].create({
                    'name': self.period_ids.decimal(month),
                    # len(str(month)) == 1 and '0' + str(month) or str(month),
                    'year_id': self.id
                })

    def active(self):
        if self.state == 'active':
            raise ValidationError(_("You can't active fiscal year more than one time"))
        self.state = 'active'
        for month in range(1, 13):
            period = self.env['periods'].create({
                'name': self.period_ids.decimal(month),
                'year_id': self.id,
                'state': 'new',
            })
            period.get_dates()
            period._get_code()

    def freeze(self):
        self.state = 'freeze'

    def reactive(self):
        self.state = 'active'

    def close(self):
        for period in self.period_ids:
            if period.state != 'close':
                raise ValidationError(
                    _("In order to close this financial year, you have to close all periods which belong to this year"))
        if self.env['account.move'].search([['period_id', '=', self.id]]) and not self.close_move_id:
            raise ValidationError(_(
                "We found that this financial year contains some transactions. You have to create journal entry to close those accounts"))
        self.state = 'close'

    def set_to_draft(self):
        if self.env['account.move'].search([['period_id', '=', self.id]]):
            raise ValidationError(_(
                "This financial year contains some journal entries and cannot be set as a )new financial year( in order to set this financial year to new , you have to delete all transactions related to this year."))
        self.period_ids.unlink()
        self.state = 'new'

    def unlink(self):
        if self.state != 'new':
            raise ValidationError(_("Financial year state must be in (New) in order to delete it"))
        return super(FiscalYear, self).unlink()

    def copy(selfs):
        raise ValidationError(_("Duplicate Disabled in this window"))
