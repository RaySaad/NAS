import logging
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import api, fields, models, Command, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .configuration import PERIODS, SERVICES

_logger = logging.getLogger(__name__)


class PaymentTransferRequest(models.Model):
    _name = 'saddad.ptr'
    _description = 'Pending to Renew Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'expiry_date, id desc'

    name = fields.Char(default='/', required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, index=True)
    employee_id = fields.Many2one('hr.employee', required=True, check_company=True, ondelete='restrict', index=True)
    department_id = fields.Many2one(related='employee_id.department_id', readonly=True, store=True)
    iqama_number = fields.Char(string='Iqama / Identification No.', readonly=True)
    remaining_days = fields.Integer(string='Iqama Remaining Days', compute='_compute_remaining_days', search='_search_remaining_days')
    expiry_date = fields.Date(string='Iqama Expiry Snapshot', required=True, readonly=True, index=True)
    period = fields.Selection(PERIODS, required=True, default=lambda s: s.env.company.saddad_ptr_period or '3', tracking=True)
    product_id = fields.Many2one('product.product', compute='_compute_totals', store=True, string='First Service Product')
    line_ids = fields.One2many('saddad.ptr.line', 'request_id', string='Service Lines', copy=False)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)
    amount = fields.Monetary(string='Total Cost', compute='_compute_totals', store=True, tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('reviewed', 'Reviewed'), ('confirmed', 'Confirmed')],
                             default='draft', required=True, readonly=True, copy=False, index=True, tracking=True)
    auto_generated = fields.Boolean(readonly=True, copy=False)
    reviewed_by = fields.Many2one('res.users', readonly=True, copy=False)
    reviewed_at = fields.Datetime(readonly=True, copy=False)
    confirmed_by = fields.Many2one('res.users', readonly=True, copy=False)
    confirmed_at = fields.Datetime(readonly=True, copy=False)
    reset_by = fields.Many2one('res.users', readonly=True, copy=False, tracking=True)
    reset_at = fields.Datetime(readonly=True, copy=False, tracking=True)
    qiwa_handoff_state = fields.Selection([('not_ready', 'Not Ready'), ('pending', 'Pending Qiwa Integration')],
                                         default='not_ready', readonly=True, copy=False)
    notes = fields.Text()
    can_review = fields.Boolean(compute='_compute_actions')
    can_confirm = fields.Boolean(compute='_compute_actions')
    can_reset = fields.Boolean(compute='_compute_actions')

    @api.depends('state', 'company_id')
    @api.depends_context('uid')
    def _compute_actions(self):
        for rec in self:
            for action, state in [('review', 'draft'), ('confirm', 'reviewed'), ('reset', 'reviewed')]:
                rule = self.env['saddad.approval.rule']._for_transition(rec.company_id, action)
                rec['can_' + action] = bool(rule and rec.state == state and
                    (self.env.su or self.env.user in rule.group_id.all_user_ids))

    @api.depends('line_ids.amount', 'line_ids.product_id')
    def _compute_totals(self):
        for rec in self:
            rec.amount = sum(rec.line_ids.mapped('amount'))
            rec.product_id = rec.line_ids[:1].product_id

    @api.depends('expiry_date')
    @api.depends_context('tz')
    def _compute_remaining_days(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.remaining_days = (rec.expiry_date - today).days if rec.expiry_date else 0

    @api.onchange('employee_id', 'company_id')
    def _onchange_employee_snapshot(self):
        # Preview only: create/write still validate and take authoritative snapshots.
        # Keep these readonly fields out of the form's save payload.
        for rec in self:
            if rec.state != 'draft':
                continue
            employee = rec.employee_id
            if employee and employee.company_id == rec.company_id:
                rec.iqama_number = employee.identification_id
                rec.expiry_date = employee.saddad_iqama_expiry
            else:
                rec.iqama_number = False
                rec.expiry_date = False

    @api.model
    def _search_remaining_days(self, operator, value):
        today = fields.Date.context_today(self)
        dates = [today + timedelta(days=int(v)) for v in value] if operator in ('in', 'not in') else today + timedelta(days=int(value))
        return [('expiry_date', operator, dates)]

    _renewal_unique = models.Constraint('UNIQUE(company_id, employee_id, expiry_date)',
                                        'A PTR already exists for this employee and Iqama expiry date.')

    @api.model
    def _mapping_for(self, company, period=None):
        mappings = self.env['saddad.service.mapping']
        mapping = mappings.search([('company_id', '=', company.id), ('default_for_ptr', '=', True)], limit=1)
        if mapping and period and period != mapping.period:
            mapping = mappings.search([('company_id', '=', company.id),
                ('service_type', '=', mapping.service_type), ('period', '=', period)], limit=1)
        if not mapping:
            raise UserError(_('Mark an active service mapping as Default for PTR for this company.'))
        product = mapping.product_id
        if not product or not product.active or product.type != 'service' or (product.company_id and product.company_id != company):
            raise UserError(_('Configure an active service product for this company and renewal period.'))
        return mapping

    @api.model
    def _snapshot(self, employee, company):
        if not employee.active or employee.company_id != company or not employee.saddad_iqama_expiry or not (employee.identification_id or '').strip():
            raise ValidationError(_('Select an active employee in this company with an identification number and Iqama expiry date.'))
        return {'expiry_date': employee.saddad_iqama_expiry, 'iqama_number': employee.identification_id}

    @api.model_create_multi
    def create(self, vals_list):
        protected = {'expiry_date', 'product_id', 'amount', 'reviewed_by', 'reviewed_at',
                     'confirmed_by', 'confirmed_at', 'auto_generated', 'qiwa_handoff_state', 'iqama_number', 'reset_by', 'reset_at'}
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if protected.intersection(vals) or vals.get('state', 'draft') != 'draft' or vals.get('name', '/') != '/':
                raise AccessError(_('Workflow and snapshot fields are managed by Saddad.'))
            company = self.env['res.company'].browse(vals.get('company_id') or self.env.company.id)
            if company not in self.env.companies:
                raise AccessError(_('The company is not in your allowed companies.'))
            employee = self.env['hr.employee'].browse(vals.get('employee_id')).exists()
            employee.check_access('read')
            period = vals.get('period') or company.saddad_ptr_period or '3'
            vals.update(company_id=company.id, period=period)
            vals.update(self._snapshot(employee, company))
            if 'line_ids' not in vals:
                mapping = self._mapping_for(company, period)
                vals['line_ids'] = [Command.create({'mapping_id': mapping.id})]
            vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('saddad.ptr') or '/'
            prepared.append(vals)
        records = super().create(prepared)
        records._notify_transition('review')
        return records

    def write(self, vals):
        protected = {'state', 'name', 'expiry_date', 'product_id', 'amount', 'reviewed_by', 'reviewed_at',
                     'confirmed_by', 'confirmed_at', 'auto_generated', 'qiwa_handoff_state', 'iqama_number', 'reset_by', 'reset_at'}
        if protected.intersection(vals):
            raise AccessError(_('Use the workflow actions to change protected PTR fields.'))
        if {'employee_id', 'company_id', 'period', 'line_ids', 'notes'}.intersection(vals):
            self.check_access('write')
            self._lock_workflow()
            if any(rec.state != 'draft' for rec in self):
                raise UserError(_('Only draft PTRs can be edited.'))
            if 'company_id' in vals and any(rec.company_id.id != vals['company_id'] for rec in self):
                raise UserError(_('Create a new PTR to change its company.'))
            for rec in self:
                employee = self.env['hr.employee'].browse(vals.get('employee_id', rec.employee_id.id))
                employee.check_access('read')
                snapshot = rec._snapshot(employee, rec.company_id) if 'employee_id' in vals else {}
                if 'period' in vals:
                    if len(rec.line_ids) != 1:
                        raise UserError(_('Edit the period on individual service lines when a PTR has multiple lines.'))
                    mapping = rec._mapping_for(rec.company_id, vals['period'])
                    rec.line_ids.write({'mapping_id': mapping.id})
                super(PaymentTransferRequest, rec).write(dict(vals, **snapshot))
            return True
        return super().write(vals)

    def copy(self, default=None):
        raise UserError(_('PTRs cannot be duplicated. Create a request for a new expiry date.'))

    def unlink(self):
        self.check_access('unlink')
        self._lock_workflow()
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_('Only draft PTRs can be deleted.'))
        return super().unlink()

    def _lock_workflow(self):
        # Serialize review/confirm against concurrent actions in another transaction.
        if self.ids:
            self.env.cr.execute('SELECT id FROM saddad_ptr WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
            self.invalidate_recordset(['state'])

    def _check_transition(self, transition, expected_state, validate_employee=True):
        self.check_access('write')
        self._lock_workflow()
        for rec in self:
            rule = self.env['saddad.approval.rule']._for_transition(rec.company_id, transition)
            if not rule or (not self.env.su and self.env.user not in rule.group_id.all_user_ids):
                raise AccessError(_('You are not authorized by the configured approval rule.'))
            if rec.state != expected_state:
                raise UserError(_('The PTR is not in the required workflow state.'))
            if not validate_employee:
                continue
            if not rec.employee_id.active or rec.employee_id.company_id != rec.company_id:
                raise UserError(_('The employee is inactive or belongs to another company.'))
            if rec.expiry_date != rec.employee_id.saddad_iqama_expiry:
                raise UserError(_('The employee expiry date has changed. Resolve this request before proceeding.'))
            if not (rec.employee_id.identification_id or '').strip() or rec.iqama_number != rec.employee_id.identification_id:
                raise UserError(_('The employee identification number is missing or has changed. Reset to Draft and reselect the employee.'))

    def action_review(self):
        self._check_transition('review', 'draft')
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Add at least one service line before review.'))
            rec.line_ids._refresh_cost()
            super(PaymentTransferRequest, rec).write({'state': 'reviewed',
                'reviewed_by': self.env.uid, 'reviewed_at': fields.Datetime.now()})
        self._complete_workflow_activities()
        self._notify_transition('confirm')
        return True

    def action_confirm(self):
        self._check_transition('confirm', 'reviewed')
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Add at least one service line before confirmation.'))
            rec.line_ids._validate_products()
            super(PaymentTransferRequest, rec).write({'state': 'confirmed', 'confirmed_by': self.env.uid,
                'confirmed_at': fields.Datetime.now(), 'qiwa_handoff_state':
                'pending' if any(line.service_type == 'work_permit' for line in rec.line_ids) else 'not_ready'})
        self._complete_workflow_activities()
        self._after_confirm()
        return True

    def action_reset_draft(self):
        self._check_transition('reset', 'reviewed', validate_employee=False)
        for rec in self:
            snapshot = {}
            if rec.employee_id.active and rec.employee_id.company_id == rec.company_id and rec.employee_id.identification_id and rec.employee_id.saddad_iqama_expiry:
                snapshot = rec._snapshot(rec.employee_id, rec.company_id)
            super(PaymentTransferRequest, rec).write(dict(snapshot, state='draft', reset_by=self.env.uid, reset_at=fields.Datetime.now()))
        self._complete_workflow_activities()
        self._notify_transition('review')
        return True

    def _after_confirm(self):
        """Extension point: Phase 2 must create/link Qiwa batch idempotently here.

        Keep batch creation in this transaction so failures roll back confirmation.
        Phase 1 deliberately leaves the handoff visibly pending.
        """
        for rec in self:
            if rec.qiwa_handoff_state == 'pending':
                rec.message_post(body=_('PTR confirmed. Qiwa batch integration is pending a later phase.'))

    def _complete_workflow_activities(self):
        activity_type = self.env.ref('Saddad.activity_ptr_approval')
        self.sudo().activity_ids.filtered(lambda a: a.activity_type_id == activity_type).action_feedback()

    def _notify_transition(self, transition):
        template = self.env.ref('Saddad.mail_template_ptr_approval')
        activity_type = self.env.ref('Saddad.activity_ptr_approval')
        for rec in self:
            rule = self.env['saddad.approval.rule']._for_transition(rec.company_id, transition)
            if not rule:
                continue
            # Sudo only discovers recipients; explicit company and read-access checks
            # prevent notifications leaking records across company boundaries.
            users = rule.sudo().group_id.all_user_ids.filtered(
                lambda u: u.active and not u.share and rec.company_id in u.company_ids)
            for user in users:
                if not rec.with_user(user).with_context(allowed_company_ids=[rec.company_id.id]).has_access('read'):
                    continue
                if rule.notify_activity:
                    exists = rec.sudo().activity_ids.filtered(
                        lambda a: a.user_id == user and a.activity_type_id == activity_type)
                    if not exists:
                        rec.sudo().activity_schedule('Saddad.activity_ptr_approval', user_id=user.id,
                            summary=rec.with_context(lang=user.lang).env._('PTR approval required'),
                            date_deadline=fields.Date.context_today(rec))
                if rule.notify_email and user.email:
                    template.sudo().with_context(lang=user.lang).send_mail(rec.id, force_send=False,
                        email_values={'recipient_ids': [(6, 0, user.partner_id.ids)], 'email_to': False})

    @api.model
    def _cron_create_ptrs(self, batch_size=200):
        """Daily bounded batch; run as system, with an explicit company context."""
        self.env['hr.employee'].flush_model(['company_id', 'active', 'saddad_ptr_eligible', 'saddad_iqama_expiry'])
        self.env['hr.employee'].flush_model(['current_version_id'])
        self.env['hr.version'].flush_model(['identification_id'])
        self.flush_model(['company_id', 'employee_id', 'expiry_date'])
        companies = self.env['res.company'].sudo().search([('saddad_ptr_automation', '=', True)])
        for company in companies:
            model = self.sudo().with_company(company).with_context(allowed_company_ids=[company.id], tz='Asia/Riyadh')
            cutoff = fields.Date.context_today(model) + timedelta(days=company.saddad_ptr_threshold)
            try:
                model._mapping_for(company)
            except UserError:
                _logger.warning('Saddad PTR automation skipped company %s: configure a default product/mapping.', company.id)
                continue
            # Exclude all states for the same renewal to avoid duplicates and batch starvation.
            model.env.cr.execute('''
                SELECT e.id FROM hr_employee e JOIN hr_version v ON v.id = e.current_version_id
                 WHERE e.company_id = %s AND e.active AND e.saddad_ptr_eligible
                   AND NULLIF(TRIM(v.identification_id), '') IS NOT NULL
                   AND e.saddad_iqama_expiry <= %s
                   AND NOT EXISTS (SELECT 1 FROM saddad_ptr p WHERE p.employee_id = e.id
                       AND p.company_id = e.company_id AND p.expiry_date = e.saddad_iqama_expiry)
                 ORDER BY e.saddad_iqama_expiry, e.id LIMIT %s
            ''', (company.id, cutoff, batch_size))
            for (employee_id,) in model.env.cr.fetchall():
                try:
                    with model.env.cr.savepoint():
                        rec = model.create({'employee_id': employee_id, 'company_id': company.id})
                        super(PaymentTransferRequest, rec).write({'auto_generated': True})
                except IntegrityError as exc:
                    if exc.pgcode != '23505':
                        raise
                    _logger.info('Concurrent PTR creation skipped for employee %s.', employee_id)

    @api.model
    def _cron_cleanup_drafts(self, batch_size=200):
        """Synchronize all unprocessed drafts with the approved renewal conditions."""
        self.env['hr.employee'].flush_model(['company_id', 'active', 'saddad_ptr_eligible', 'saddad_iqama_expiry'])
        self.env['hr.employee'].flush_model(['current_version_id'])
        self.env['hr.version'].flush_model(['identification_id'])
        self.flush_model(['company_id', 'employee_id', 'expiry_date', 'state', 'auto_generated'])
        for company in self.env['res.company'].sudo().search([]):
            model = self.sudo().with_company(company).with_context(allowed_company_ids=[company.id], tz='Asia/Riyadh')
            cutoff = fields.Date.context_today(model) + timedelta(days=company.saddad_ptr_threshold)
            model.env.cr.execute('''
                SELECT p.id FROM saddad_ptr p JOIN hr_employee e ON e.id = p.employee_id
                  LEFT JOIN hr_version v ON v.id = e.current_version_id
                 WHERE p.company_id = %s AND p.state = 'draft'
                   AND (NOT e.active OR NOT e.saddad_ptr_eligible OR e.company_id != p.company_id
                        OR NULLIF(TRIM(v.identification_id), '') IS NULL
                        OR e.saddad_iqama_expiry IS DISTINCT FROM p.expiry_date
                        OR e.saddad_iqama_expiry > %s)
                 ORDER BY p.id LIMIT %s FOR UPDATE OF p SKIP LOCKED
            ''', (company.id, cutoff, batch_size))
            obsolete = model.browse([row[0] for row in model.env.cr.fetchall()])
            obsolete.invalidate_recordset(['state'])
            obsolete.unlink()


class RenewalRequestLine(models.Model):
    _name = 'saddad.ptr.line'
    _description = 'PTR Service Line'
    _check_company_auto = True
    _order = 'id'

    request_id = fields.Many2one('saddad.ptr', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='request_id.currency_id')
    mapping_id = fields.Many2one('saddad.service.mapping', string='Service Period Mapping', check_company=True)
    product_id = fields.Many2one('product.product', required=True, check_company=True, ondelete='restrict', domain="[('type', '=', 'service')]")
    service_type = fields.Selection(SERVICES, required=True, default='other')
    period = fields.Selection(PERIODS)
    amount = fields.Monetary(string='Cost Snapshot', readonly=True)

    def _check_draft(self):
        requests = self.request_id
        requests.check_access('write')
        requests._lock_workflow()
        if any(rec.state != 'draft' for rec in requests):
            raise UserError(_('Service lines can only be changed on a draft PTR.'))

    @api.onchange('mapping_id')
    def _onchange_mapping(self):
        if self.mapping_id:
            self.product_id = self.mapping_id.product_id
            self.period = self.mapping_id.period
            self.service_type = self.mapping_id.service_type

    @api.model
    def _line_values(self, vals, request, current=None):
        result = dict(vals)
        mapping = self.env['saddad.service.mapping'].browse(vals.get('mapping_id')) if 'mapping_id' in vals else current.mapping_id if current else self.env['saddad.service.mapping']
        if mapping:
            mapping.check_access('read')
            if not mapping.active or mapping.company_id != request.company_id:
                raise ValidationError(_('Choose an active mapping belonging to the PTR company.'))
            result.update(product_id=mapping.product_id.id, period=mapping.period, service_type=mapping.service_type)
        product = self.env['product.product'].browse(result.get('product_id') or (current.product_id.id if current else False))
        product.check_access('read')
        if not product or not product.active or product.type != 'service' or (product.company_id and product.company_id != request.company_id):
            raise ValidationError(_('Select an active service product available to the PTR company.'))
        result['amount'] = product.with_company(request.company_id).standard_price
        if result['amount'] < 0:
            raise ValidationError(_('The service product cost cannot be negative.'))
        return result

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            if {'amount', 'company_id', 'currency_id'}.intersection(vals):
                raise AccessError(_('Service line amounts and company are managed by Saddad.'))
            request = self.env['saddad.ptr'].browse(vals.get('request_id')).exists()
            if not request:
                raise ValidationError(_('A service line must belong to a PTR.'))
            request.check_access('write')
            request._lock_workflow()
            if request.state != 'draft':
                raise UserError(_('Service lines can only be changed on a draft PTR.'))
            prepared.append(self._line_values(vals, request))
        return super().create(prepared)

    def write(self, vals):
        if {'request_id', 'company_id', 'currency_id', 'amount'}.intersection(vals):
            raise AccessError(_('Service lines cannot be reassigned or their cost snapshots edited directly.'))
        self._check_draft()
        for line in self:
            super(RenewalRequestLine, line).write(self._line_values(vals, line.request_id, line))
        return True

    def unlink(self):
        self._check_draft()
        return super().unlink()

    def _validate_products(self):
        for line in self:
            product = line.product_id
            if not product.active or product.type != 'service' or (product.company_id and product.company_id != line.company_id):
                raise ValidationError(_('Select an active service product available to the PTR company.'))

    @api.constrains('service_type', 'period')
    def _check_period(self):
        if any(line.service_type in ('iqama', 'work_permit') and not line.period for line in self):
            raise ValidationError(_('Iqama and Work Permit lines require a renewal period.'))

    def _refresh_cost(self):
        self._validate_products()
        for line in self:
            cost = line.product_id.with_company(line.company_id).standard_price
            if cost < 0:
                raise ValidationError(_('The service product cost cannot be negative.'))
            super(RenewalRequestLine, line).write({'amount': cost})
