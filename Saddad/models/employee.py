from hijridate import Gregorian

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    saddad_iqama_expiry = fields.Date(string='Iqama Expiry Date (Gregorian)', groups='hr.group_hr_user', tracking=True)
    saddad_iqama_hijri = fields.Char(string='Iqama Expiry Date (Hijri)', compute='_compute_saddad_dates',
                                    groups='hr.group_hr_user')
    saddad_iqama_remaining_days = fields.Integer(string='Iqama Remaining Days', compute='_compute_saddad_dates',
                                                 search='_search_saddad_remaining_days',
                                                 groups='hr.group_hr_user', help='Negative values indicate an expired Iqama.')
    saddad_ptr_eligible = fields.Boolean(string='Include in PTR Automation', default=True, groups='hr.group_hr_user',
                                        help='Enable for employees whose Iqama renewals are managed in Saddad.')

    @api.model
    def _search_saddad_remaining_days(self, operator, value):
        from datetime import timedelta
        today = fields.Date.context_today(self)
        if operator in ('in', 'not in'):
            dates = [today + timedelta(days=int(v)) for v in value]
        else:
            dates = today + timedelta(days=int(value))
        return [('saddad_iqama_expiry', '!=', False), ('saddad_iqama_expiry', operator, dates)]

    @api.depends('saddad_iqama_expiry')
    @api.depends_context('tz')
    def _compute_saddad_dates(self):
        today = fields.Date.context_today(self)
        for employee in self:
            expiry = employee.saddad_iqama_expiry
            employee.saddad_iqama_remaining_days = (expiry - today).days if expiry else 0
            employee.saddad_iqama_hijri = False
            if expiry:
                try:
                    employee.saddad_iqama_hijri = Gregorian(expiry.year, expiry.month, expiry.day).to_hijri().isoformat()
                except (ValueError, OverflowError):
                    employee.saddad_iqama_hijri = _('Outside supported Hijri calendar range')

    @api.constrains('saddad_iqama_expiry')
    def _check_hijri_range(self):
        for employee in self:
            expiry = employee.saddad_iqama_expiry
            if expiry:
                try:
                    Gregorian(expiry.year, expiry.month, expiry.day).to_hijri()
                except (ValueError, OverflowError) as exc:
                    raise ValidationError(_('The Iqama expiry date is outside the supported Umm al-Qura calendar range (1924–2077).')) from exc
