"""Resident snapshots and human-verified renewal cycles; no external API execution."""
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


def identity(value):
    return ''.join(str(value or '').translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')).split())


class Establishment(models.Model):
    _name = 'saddad.establishment'
    _description = 'Muqeem Establishment'
    name = fields.Char(required=True)
    number = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    pending_days = fields.Integer(default=7, required=True)
    warning_days = fields.Integer(default=30, required=True)
    _number_unique = models.Constraint('UNIQUE(number)', 'Map an employer number to only one company.')

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([dict(v, number=identity(v.get('number'))) for v in vals_list])

    def write(self, vals):
        if 'number' in vals:
            vals = dict(vals, number=identity(vals['number']))
        if {'number', 'company_id'}.intersection(vals) and self.env['saddad.resident'].search_count([('establishment_id', 'in', self.ids)]):
            raise UserError(_('An establishment with resident history cannot be reassigned.'))
        return super().write(vals)

    @api.constrains('number', 'pending_days', 'warning_days')
    def _check_values(self):
        if any(not r.number.isdigit() or r.pending_days < 0 or r.warning_days < 0 for r in self):
            raise ValidationError(_('Enter a numeric employer number and non-negative alert thresholds.'))


class Resident(models.Model):
    _name = 'saddad.resident'
    _description = 'Muqeem Resident Profile'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'employee_id'
    _check_company_auto = True
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, index=True)
    employee_id = fields.Many2one('hr.employee', required=True, check_company=True, ondelete='restrict')
    establishment_id = fields.Many2one('saddad.establishment', required=True, check_company=True, ondelete='restrict')
    employer_number = fields.Char(related='establishment_id.number', string='Employer Number')
    iqama = fields.Char(required=True, index=True)
    reported_name = fields.Char()
    sex = fields.Char()
    nationality = fields.Char()
    occupation = fields.Char()
    passport = fields.Char()
    passport_expiry = fields.Date()
    iqama_issue = fields.Date()
    reported_expiry = fields.Date(string='Imported Muqeem Expiry', tracking=True)
    birth_date = fields.Date()
    outside_kingdom = fields.Char()
    reported_hijri = fields.Char()
    snapshot_date = fields.Date(required=True)
    source_batch_id = fields.Many2one('saddad.resident.import', ondelete='restrict')
    employee_expiry = fields.Date(related='employee_id.saddad_iqama_expiry', string='Current Employee Expiry')
    expiry_comparison = fields.Selection([('missing', 'Expiry Missing'), ('older', 'Imported Date Is Older'),
        ('same', 'Dates Match'), ('newer', 'Imported Date Is Newer')], compute='_compute_expiry_comparison', string='Expiry Comparison')
    renewal_ids = fields.One2many('saddad.renewal', 'resident_id')
    latest_permit_valid_until = fields.Date(compute='_compute_permit', string='Latest Verified Work Permit Valid Till')
    latest_permit_confirmed_on = fields.Date(compute='_compute_permit', string='Work Permit Verified On')
    _employee_unique = models.Constraint('UNIQUE(employee_id)', 'An employee can have only one resident profile.')
    _identity_unique = models.Constraint('UNIQUE(company_id, iqama)', 'Duplicate resident Iqama in this company.')

    @api.depends('reported_expiry', 'employee_expiry')
    def _compute_expiry_comparison(self):
        for rec in self:
            rec.expiry_comparison = ('missing' if not rec.reported_expiry else
                'newer' if not rec.employee_expiry or rec.reported_expiry > rec.employee_expiry else
                'same' if rec.reported_expiry == rec.employee_expiry else 'older')

    @api.depends('renewal_ids.permit_confirmed_on', 'renewal_ids.permit_valid_until')
    def _compute_permit(self):
        for rec in self:
            confirmed = rec.renewal_ids.filtered('permit_confirmed_on').sorted(lambda r: (r.permit_valid_until or fields.Date.to_date('1900-01-01'), r.permit_confirmed_on, r.id), reverse=True)[:1]
            rec.latest_permit_valid_until = confirmed.permit_valid_until
            rec.latest_permit_confirmed_on = confirmed.permit_confirmed_on

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Resident profiles are maintained through reviewed imports.'))

    def write(self, vals):
        if set(vals) - {'message_follower_ids', 'message_partner_ids'}:
            raise AccessError(_('Resident profiles are maintained through reviewed imports.'))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_('Resident history cannot be deleted.'))

    def action_review_expiry(self):
        self.ensure_one()
        self.check_access('read')
        if self.expiry_comparison == 'older':
            raise UserError(_('The imported Muqeem expiry (%(reported)s) is older than the current employee expiry (%(current)s). Import a fresh Muqeem report. The employee expiry will not be changed.', reported=self.reported_expiry, current=self.employee_expiry))
        if not self.reported_expiry:
            raise UserError(_('Import a Muqeem report containing an expiry date first.'))
        wizard = self.env['saddad.resident.expiry'].create({
            'resident_id': self.id, 'expected_expiry': self.employee_id.saddad_iqama_expiry,
            'new_expiry': self.reported_expiry, 'snapshot_date': self.snapshot_date})
        return {'type': 'ir.actions.act_window', 'res_model': wizard._name, 'res_id': wizard.id, 'view_mode': 'form', 'target': 'new'}


class Employee(models.Model):
    _inherit = 'hr.employee'
    saddad_resident_ids = fields.One2many('saddad.resident', 'employee_id', groups='Saddad.group_resident_hr')
    saddad_resident_id = fields.Many2one('saddad.resident', compute='_compute_resident_profile', compute_sudo=False, groups='Saddad.group_resident_hr')

    saddad_muqeem_establishment_id = fields.Many2one(related='saddad_resident_id.establishment_id', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_employer_number = fields.Char(related='saddad_resident_id.employer_number', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_iqama = fields.Char(related='saddad_resident_id.iqama', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_reported_name = fields.Char(related='saddad_resident_id.reported_name', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_sex = fields.Char(related='saddad_resident_id.sex', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_nationality = fields.Char(related='saddad_resident_id.nationality', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_occupation = fields.Char(related='saddad_resident_id.occupation', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_passport = fields.Char(related='saddad_resident_id.passport', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_passport_expiry = fields.Date(related='saddad_resident_id.passport_expiry', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_iqama_issue = fields.Date(related='saddad_resident_id.iqama_issue', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_reported_expiry = fields.Date(related='saddad_resident_id.reported_expiry', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_reported_hijri = fields.Char(related='saddad_resident_id.reported_hijri', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_birth_date = fields.Date(related='saddad_resident_id.birth_date', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_outside_kingdom = fields.Char(related='saddad_resident_id.outside_kingdom', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_snapshot_date = fields.Date(related='saddad_resident_id.snapshot_date', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_latest_permit_valid_until = fields.Date(related='saddad_resident_id.latest_permit_valid_until', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_latest_permit_confirmed_on = fields.Date(related='saddad_resident_id.latest_permit_confirmed_on', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')
    saddad_muqeem_expiry_comparison = fields.Selection(related='saddad_resident_id.expiry_comparison', readonly=True, compute_sudo=False, groups='Saddad.group_resident_hr')

    @api.depends('saddad_resident_ids')
    def _compute_resident_profile(self):
        for employee in self:
            employee.saddad_resident_id = employee.saddad_resident_ids[:1]

    def action_open_resident_profile(self):
        self.ensure_one()
        self.check_access('read')
        profile = self.saddad_resident_id
        if not profile:
            raise UserError(_('Import the employee Muqeem resident profile first.'))
        profile.check_access('read')
        return {'type': 'ir.actions.act_window', 'res_model': profile._name, 'res_id': profile.id, 'view_mode': 'form', 'target': 'current'}

    def _apply_verified_expiry(self, expected, new, evidence):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('Saddad.group_resident_hr'):
            raise AccessError(_('Resident HR access is required.'))
        self.env.cr.execute('SELECT id FROM hr_employee WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset(['saddad_iqama_expiry'])
        current = self.saddad_iqama_expiry
        if not new:
            raise ValidationError(_('A verified expiry date is required.'))
        if current and new < current:
            raise UserError(_('This update would shorten the employee expiry. Review the source instead of applying an older date.'))
        if current not in (expected, new):
            raise UserError(_('Expiry conflict. Original: %(old)s; current: %(current)s; proposed: %(new)s. Review the employee record first.', old=expected, current=current, new=new))
        if current != new:
            self.write({'saddad_iqama_expiry': new})
        self.message_post(body=_('Verified expiry: %(old)s → %(new)s. Evidence: %(evidence)s. Already updated: %(same)s', old=current, new=new, evidence=evidence, same=current == new))


class ExpiryReview(models.TransientModel):
    _name = 'saddad.resident.expiry'
    _description = 'Review Muqeem Expiry Update'
    resident_id = fields.Many2one('saddad.resident', required=True)
    expected_expiry = fields.Date(string='Current Employee Expiry', readonly=True)
    new_expiry = fields.Date(string='Imported Muqeem Expiry', readonly=True, required=True)
    snapshot_date = fields.Date(readonly=True, required=True)
    verified = fields.Boolean(string='I verified this expiry against Muqeem')

    def action_apply(self):
        self.ensure_one()
        profile = self.resident_id
        profile.check_access('read')
        if not self.verified:
            raise UserError(_('Verify the expiry before applying it.'))
        self.env.cr.execute('SELECT id FROM saddad_resident WHERE id = %s FOR UPDATE', [profile.id])
        profile.invalidate_recordset()
        if self.new_expiry != profile.reported_expiry or self.snapshot_date != profile.snapshot_date:
            raise UserError(_('The resident snapshot changed. Reopen the expiry review.'))
        profile.employee_id._apply_verified_expiry(self.expected_expiry, self.new_expiry, str(profile.snapshot_date))
        return {'type': 'ir.actions.act_window_close'}


class Renewal(models.Model):
    _name = 'saddad.renewal'
    _description = 'Iqama Renewal Follow-up'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _rec_name = 'employee_id'
    resident_id = fields.Many2one('saddad.resident', required=True, check_company=True, ondelete='restrict')
    company_id = fields.Many2one(related='resident_id.company_id', store=True)
    employee_id = fields.Many2one(related='resident_id.employee_id', store=True)
    expense_line_id = fields.Many2one('saddad.muqeem.line', check_company=True, ondelete='restrict')
    qiwa_line_id = fields.Many2one('saddad.qiwa.line', check_company=True, ondelete='restrict')
    original_expiry = fields.Date(required=True, readonly=True)
    period = fields.Selection([('3', '3 Months'), ('6', '6 Months'), ('9', '9 Months'), ('12', '12 Months')], required=True, default='3')
    new_expiry = fields.Date(required=True, tracking=True)
    owner_id = fields.Many2one('res.users', required=True, default=lambda s: s.env.user)
    evidence = fields.Char(string='Renewal Evidence / Reference')
    state = fields.Selection([('pending', 'Pending Renewal'), ('done', 'Renewal Completed')], default='pending', readonly=True, tracking=True)
    blocker = fields.Selection([('employee', 'Employee Issue'), ('company', 'Company Issue'), ('other', 'Other')], tracking=True)
    notes = fields.Text()
    permit_valid_until = fields.Date(related='qiwa_line_id.permit_valid_until')
    permit_confirmed_on = fields.Date(readonly=True, copy=False)
    permit_renewal_date = fields.Date(string='Actual Work Permit Renewal Date', default=fields.Date.context_today)
    permit_evidence = fields.Char(string='Work Permit Renewal Evidence')
    completed_at = fields.Datetime(readonly=True, copy=False)
    completed_by = fields.Many2one('res.users', readonly=True, copy=False)
    pending_alerted = fields.Boolean(readonly=True, copy=False)
    expiry_alerted = fields.Boolean(readonly=True, copy=False)
    alert_activity_ids = fields.Many2many('mail.activity', readonly=True, copy=False)
    _line_unique = models.Constraint('UNIQUE(expense_line_id)', 'This expense line already has a renewal follow-up.')
    _qiwa_unique = models.Constraint('UNIQUE(qiwa_line_id)', 'This work permit already has a renewal follow-up.')
    _open_employee = models.UniqueIndex('(employee_id) WHERE state = \'pending\'', 'Resolve the existing pending renewal for this employee first.')

    @api.onchange('resident_id', 'period', 'expense_line_id')
    def _onchange_dates(self):
        old = self.resident_id.employee_id.saddad_iqama_expiry
        if self.expense_line_id:
            line = self.expense_line_id
            old = line.ptr_line_id.request_id.expiry_date if line.ptr_line_id else line.renewal_original_expiry or old
        self.original_expiry = old
        self.new_expiry = old + relativedelta(months=int(self.period)) if old and self.period else False

    def _lock(self):
        self.check_access('write')
        if not self.env.user.has_group('Saddad.group_resident_hr'):
            raise AccessError(_('Resident HR access is required.'))
        self.env.cr.execute('SELECT id FROM saddad_renewal WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
        self.invalidate_recordset()

    @api.model
    def _open_for_employee(self, employee, expense_line=None, qiwa_line=None):
        employee.check_access('read')
        if not self.env.user.has_group('Saddad.group_resident_hr'):
            raise AccessError(_('Resident HR access is required.'))
        source = expense_line or qiwa_line
        key = 'expense_line_id' if expense_line else 'qiwa_line_id'
        existing = self.search([(key, '=', source.id)], limit=1)
        if not existing:
            existing = self.search([('employee_id', '=', employee.id), ('state', '=', 'pending')], limit=1)
            if existing:
                if existing[key] and existing[key] != source:
                    raise UserError(_('Resolve the existing linked renewal before starting another one.'))
                existing.write({key: source.id})
            else:
                resident = self.env['saddad.resident'].search([('employee_id', '=', employee.id)], limit=1)
                if not resident:
                    raise UserError(_('Import the employee Muqeem resident profile first.'))
                existing = self.create({'resident_id': resident.id, key: source.id, 'period': source.period})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': existing.id, 'view_mode': 'form', 'target': 'current'}

    @api.model_create_multi
    def create(self, vals_list):
        protected = {'state', 'completed_at', 'completed_by', 'permit_confirmed_on', 'pending_alerted', 'expiry_alerted', 'alert_activity_ids', 'original_expiry'}
        prepared = []
        for vals in vals_list:
            if protected.intersection(vals):
                raise AccessError(_('Use renewal actions for protected fields.'))
            profile = self.env['saddad.resident'].browse(vals.get('resident_id'))
            profile.check_access('read')
            old = profile.employee_id.saddad_iqama_expiry
            line = self.env['saddad.muqeem.line'].browse(vals.get('expense_line_id'))
            if line:
                line.check_access('read')
                old = line.ptr_line_id.request_id.expiry_date if line.ptr_line_id else line.renewal_original_expiry
                if not old:
                    raise UserError(_('This legacy expense has no original expiry snapshot. Reconcile its renewal history before using automatic expiry confirmation.'))
            if not old:
                raise ValidationError(_('Set the employee original Iqama expiry before preparing renewal.'))
            prepared.append(dict(vals, state='pending', permit_confirmed_on=False, completed_at=False,
                completed_by=False, pending_alerted=False, expiry_alerted=False, alert_activity_ids=False,
                original_expiry=old, new_expiry=vals.get('new_expiry') or old + relativedelta(months=int(vals.get('period', '3')))))
        return super().create(prepared)

    def write(self, vals):
        self._lock()
        if {'state', 'original_expiry', 'resident_id', 'completed_at', 'completed_by', 'permit_confirmed_on', 'pending_alerted', 'expiry_alerted', 'alert_activity_ids'}.intersection(vals):
            raise AccessError(_('Use renewal actions for protected fields.'))
        if any(r.state == 'done' for r in self):
            raise UserError(_('Completed renewal history cannot be changed.'))
        if {'qiwa_line_id', 'permit_evidence', 'permit_renewal_date', 'period'}.intersection(vals) and any(r.permit_confirmed_on for r in self):
            raise UserError(_('A confirmed work permit link cannot be changed.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Renewal history cannot be deleted.'))

    @api.constrains('resident_id', 'expense_line_id', 'qiwa_line_id', 'new_expiry', 'period', 'owner_id')
    def _validate_links(self):
        for rec in self:
            if rec.new_expiry <= rec.original_expiry:
                raise ValidationError(_('The new expiry must be after the original expiry.'))
            if rec.expense_line_id and (rec.expense_line_id.employee_id != rec.employee_id or rec.expense_line_id.period != rec.period):
                raise ValidationError(_('The Iqama expense must match this employee and period.'))
            if rec.expense_line_id:
                line = rec.expense_line_id
                original = line.ptr_line_id.request_id.expiry_date if line.ptr_line_id else line.renewal_original_expiry
                if not original:
                    raise ValidationError(_('This legacy expense has no original expiry snapshot. Reconcile its renewal history before using automatic expiry confirmation.'))
                if original and original != rec.original_expiry:
                    raise ValidationError(_('This expense belongs to a different original expiry. Review the renewal cycle before linking it.'))
            if rec.qiwa_line_id and (rec.qiwa_line_id.employee_id != rec.employee_id or rec.qiwa_line_id.period != rec.period):
                raise ValidationError(_('The Qiwa line must match this employee and period.'))
            if rec.company_id not in rec.owner_id.company_ids or not rec.owner_id.has_group('Saddad.group_resident_hr') or not rec.owner_id.active:
                raise ValidationError(_('Assign an active Resident HR user authorized for this company.'))

    def action_confirm_permit(self):
        self.ensure_one()
        self._lock()
        if self.state != 'pending' or self.permit_confirmed_on:
            raise UserError(_('This work permit confirmation is already recorded or the renewal is complete.'))
        if not self.qiwa_line_id or self.qiwa_line_id.batch_id.state != 'confirmed' or not self.permit_valid_until or not (self.permit_evidence or '').strip():
            raise UserError(_('Select a confirmed Qiwa line with Valid Till and enter evidence of actual work permit renewal.'))
        if not self.permit_renewal_date or self.permit_renewal_date > fields.Date.context_today(self):
            raise UserError(_('Enter the actual work permit renewal date, no later than today.'))
        super().write({'permit_confirmed_on': fields.Date.context_today(self)})
        self.message_post(body=_('HR verified actual work permit renewal. Evidence: %s', self.permit_evidence))

    def action_confirm_renewal(self):
        self.ensure_one()
        self._lock()
        if self.state == 'done':
            raise UserError(_('This renewal is already complete.'))
        line = self.expense_line_id
        if not line:
            raise UserError(_('Link a paid Iqama expense line first.'))
        line.expense_id._lock()
        line.invalidate_recordset()
        mapping = self.env['saddad.service.mapping'].search_count([('company_id', '=', self.company_id.id), ('product_id', '=', line.product_id.id), ('period', '=', self.period), ('service_type', '=', 'iqama')])
        if not line.paid or not mapping or not (self.evidence or '').strip():
            raise UserError(_('Confirmation requires a paid Iqama service line and renewal evidence.'))
        self.employee_id._apply_verified_expiry(self.original_expiry, self.new_expiry, self.evidence)
        super().write({'state': 'done', 'completed_at': fields.Datetime.now(), 'completed_by': self.env.uid})
        self.alert_activity_ids.action_feedback(feedback=_('Iqama renewal completed.'))
        self.message_post(body=_('Iqama renewal confirmed. Verified new expiry: %s', self.new_expiry))

    @api.model
    def _cron_alerts(self):
        today = fields.Date.today()
        for rec in self.search([('state', '=', 'pending'), ('permit_confirmed_on', '!=', False)]):
            self.env.cr.execute('SELECT id FROM saddad_renewal WHERE id = %s FOR UPDATE', [rec.id])
            rec.invalidate_recordset()
            if rec.state != 'pending':
                continue
            settings = rec.resident_id.establishment_id
            pending = (today - (rec.permit_renewal_date or rec.permit_confirmed_on)).days >= settings.pending_days and not rec.pending_alerted
            expiry = rec.permit_valid_until and (rec.permit_valid_until - today).days <= settings.warning_days and not rec.expiry_alerted
            if not (pending or expiry):
                continue
            owner = rec.owner_id
            if not owner.active or rec.company_id not in owner.company_ids or not owner.has_group('Saddad.group_resident_hr'):
                continue
            note = _('Iqama renewal is incomplete. Work permit valid until: %s. Review the blocker and complete the renewal.', rec.permit_valid_until)
            activity = rec.activity_schedule('mail.mail_activity_data_todo', user_id=owner.id, summary=_('Iqama renewal follow-up'), note=note)
            self.env['mail.mail'].create({'subject': _('Iqama renewal follow-up'), 'body_html': '<p>' + note + '</p>', 'recipient_ids': [(4, owner.partner_id.id)]})
            super(Renewal, rec).write({'pending_alerted': rec.pending_alerted or pending, 'expiry_alerted': rec.expiry_alerted or bool(expiry), 'alert_activity_ids': [(4, activity.id)]})


class MuqeemLine(models.Model):
    _inherit = 'saddad.muqeem.line'
    renewal_original_expiry = fields.Date(readonly=True, copy=False, string='Original Expiry for Renewal')

    def action_renewal_followup(self):
        self.ensure_one()
        self.check_access('read')
        mapping = self.env['saddad.service.mapping'].search_count([('company_id', '=', self.company_id.id), ('product_id', '=', self.product_id.id), ('period', '=', self.period), ('service_type', '=', 'iqama')])
        if not mapping:
            raise UserError(_('Choose an Iqama renewal service line.'))
        return self.env['saddad.renewal']._open_for_employee(self.employee_id, expense_line=self)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            if 'renewal_original_expiry' in vals:
                raise AccessError(_('Original expiry is captured from the employee automatically.'))
            employee = self.env['hr.employee'].browse(vals.get('employee_id'))
            employee.check_access('read')
            prepared.append(dict(vals, renewal_original_expiry=employee.saddad_iqama_expiry))
        return super().create(prepared)

    def write(self, vals):
        if 'renewal_original_expiry' in vals:
            raise AccessError(_('Original expiry cannot be edited.'))
        if 'employee_id' in vals:
            employee = self.env['hr.employee'].browse(vals['employee_id'])
            employee.check_access('read')
            vals = dict(vals, renewal_original_expiry=employee.saddad_iqama_expiry)
        return super().write(vals)

    def action_unmark_paid(self):
        self.expense_id._lock()
        if self.env['saddad.renewal'].sudo().search_count([('expense_line_id', 'in', self.ids), ('state', '=', 'done')]):
            raise UserError(_('Payment cannot be reversed after Iqama renewal confirmation.'))
        return super().action_unmark_paid()


class QiwaLine(models.Model):
    _inherit = 'saddad.qiwa.line'

    def action_renewal_followup(self):
        self.ensure_one()
        self.check_access('read')
        if self.batch_id.state != 'confirmed':
            raise UserError(_('Confirm the Qiwa batch before preparing renewal follow-up.'))
        return self.env['saddad.renewal']._open_for_employee(self.employee_id, qiwa_line=self)
