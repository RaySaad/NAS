# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import calendar
from odoo.exceptions import UserError, ValidationError


MONTHS = [
    ('01', 'January'), ('02', 'February'), ('03', 'March'), ('04', 'April'),
    ('05', 'May'), ('06', 'June'), ('07', 'July'), ('08', 'August'),
    ('09', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
]

class Periods(models.Model):
    _name = 'periods'
    _description = "Periods"
    _inherit = ['mail.thread', ]
    _rec_name = 'code'

    year_id = fields.Many2one('fiscal.year', 'Fiscal year')
    name = fields.Selection(MONTHS, string='Period name')
    code = fields.Char('Code', compute="_get_code", store=True)  #
    date_start = fields.Date('Date Start', compute='get_dates', store=True)  #
    date_end = fields.Date('Date End', compute='get_dates', store=True)  #
    state = fields.Selection([('new', 'New'), ('active', 'Active'), ('freeze', 'Freeze'), ('close', 'Close')],
                             string='Status', default='new', )

    lock_date_access = fields.Selection([('for_all', 'For All'), ('for_non_advisers', 'For Non Advisers')],string="Lock Dates", default='for_all', tracking=True)
    lock_journal_ids = fields.Many2many('account.journal', string="Lock Journals", tracking=True)

    note = fields.Html('Notes')
    company_id = fields.Many2one('res.company', related='year_id.company_id', store=True)

    def name_get(self, arab=False):
        result = []
        for record in self:
            name = "%s- %s" % (record.company_id.name or '', record.read()[0]['name'])
            result.append((record.id, name))
        return result

    @api.model
    def get_default_period(self, date, company_id):
        periods = self.search([['date_start', '<=', date], ['date_end', '>=', date], ['state', 'in', ['active', 'freeze', 'close']], ['company_id', '=', company_id.id]])
        if date and periods:
            return periods[0]
        else:
            return False

    def active_all(self):
        for rec in self:
            rec.active()

    def active(self):
        self.state = 'active'

    def freeze(self):
        self.state = 'freeze'

    def close(self):
        self.state = 'close'

    def reactive(self):
        self.state = 'active'

    @api.depends('year_id')
    def get_dates(self):
        for rec in self:
            if rec and rec.year_id and rec.name:
                rec.date_start = str(rec.year_id.name) + '-' + str(rec.name) + '-01'
                last_date = calendar.monthrange(int(rec.year_id.name), int(rec.name))[1]
                rec.date_end = str(rec.year_id.name) + '-' + str(rec.name) + '-' + str(rec.decimal(last_date))
            else:
                rec.date_end = False

    def decimal(self, n):
        for c in str(n):
            if str(c) not in '0123456789':
                raise ValidationError(_("Programming Error"))
        return len(str(n)) == 2 and str(n) or ('0' + str(n))

    def _get_code(self):
        self.code = str(self.year_id.name) + "/" + str(self.name)

    def copy(self):
        raise ValidationError(_("Duplicate Disabled in this window"))
