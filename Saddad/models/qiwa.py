from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .configuration import PERIODS


class QiwaBatch(models.Model):
    _name = 'saddad.qiwa.batch'
    _description = 'Qiwa Work Permit Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'id desc'

    name = fields.Char(default='/', required=True, readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    reference = fields.Char(string='Qiwa SADAD Reference', copy=False, tracking=True, index=True)
    invoice_number = fields.Char(string='Qiwa Invoice Number', copy=False, tracking=True)
    issue_date = fields.Date(string='Reference Issue Date', tracking=True)
    due_date = fields.Date(string='Reference Due Date', tracking=True)
    document_payment_status = fields.Selection([('unknown', 'Not Specified'), ('unpaid', 'Unpaid in Qiwa'), ('paid', 'Paid in Qiwa')], default='unknown', required=True, tracking=True,
        help='Status reported by the Qiwa document; this does not record a payment in Saddad.')
    document_payment_date = fields.Date(string='Qiwa Payment Date', tracking=True)
    document_export_date = fields.Date(string='PDF Export Date')
    period = fields.Selection(PERIODS, string='Common Period', help='Leave empty for mixed-period batches.')
    line_ids = fields.One2many('saddad.qiwa.line', 'batch_id', string='Employee Lines', copy=False)
    total_amount = fields.Monetary(compute='_compute_total', store=True)
    state = fields.Selection([('draft', 'Draft'), ('reviewed', 'Reviewed'), ('confirmed', 'Confirmed')], default='draft', required=True, readonly=True, tracking=True, copy=False, index=True)
    reviewed_by = fields.Many2one('res.users', readonly=True, copy=False)
    reviewed_at = fields.Datetime(readonly=True, copy=False)
    confirmed_by = fields.Many2one('res.users', readonly=True, copy=False)
    confirmed_at = fields.Datetime(readonly=True, copy=False)
    notes = fields.Text()
    downstream_state = fields.Selection([('not_ready', 'Not Ready'), ('pending', 'Pending Muqeem Phase')], string='Muqeem Expense Status', compute='_compute_downstream')
    can_review = fields.Boolean(compute='_compute_actions')
    can_confirm = fields.Boolean(compute='_compute_actions')
    can_reset = fields.Boolean(compute='_compute_actions')

    _reference_unique = models.Constraint('UNIQUE(company_id, reference)', 'The Qiwa SADAD reference must be unique within a company.')

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    @api.depends('state')
    def _compute_downstream(self):
        for rec in self:
            rec.downstream_state = 'pending' if rec.state == 'confirmed' else 'not_ready'

    @api.depends('state', 'company_id')
    @api.depends_context('uid')
    def _compute_actions(self):
        for rec in self:
            for action, state in [('review', 'draft'), ('confirm', 'reviewed'), ('reset', 'reviewed')]:
                rule = self.env['saddad.approval.rule']._for_transition(rec.company_id, 'qiwa_' + action)
                rec['can_' + action] = bool(rule and rec.state == state and (self.env.su or self.env.user in rule.group_id.all_user_ids))

    def _lock(self):
        self.check_access('write')
        if self.ids:
            self.env.cr.execute('SELECT id FROM saddad_qiwa_batch WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
            self.invalidate_recordset()

    def _draft(self):
        self._lock()
        if any(r.state != 'draft' for r in self):
            raise UserError(_('Only draft Qiwa batches can be edited.'))

    @api.model
    def _normalize_reference(self, value):
        return ''.join((value or '').translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')).split()).upper() or False

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            if {'reviewed_by', 'reviewed_at', 'confirmed_by', 'confirmed_at', 'total_amount', 'downstream_state'}.intersection(vals) or vals.get('state', 'draft') != 'draft' or vals.get('name', '/') != '/':
                raise AccessError(_('Use Qiwa workflow actions to change protected fields.'))
            company = self.env['res.company'].browse(vals.get('company_id') or self.env.company.id)
            if company not in self.env.companies:
                raise AccessError(_('The company is not in your allowed companies.'))
            vals.update(company_id=company.id, reference=self._normalize_reference(vals.get('reference')),
                        name=self.env['ir.sequence'].with_company(company).next_by_code('saddad.qiwa.batch') or '/')
            prepared.append(vals)
        records = super().create(prepared)
        return records

    def write(self, vals):
        if {'state', 'name', 'reviewed_by', 'reviewed_at', 'confirmed_by', 'confirmed_at', 'total_amount', 'downstream_state'}.intersection(vals):
            raise AccessError(_('Use Qiwa workflow actions to change protected fields.'))
        if {'company_id', 'reference', 'invoice_number', 'issue_date', 'due_date', 'period', 'line_ids', 'notes',
            'document_payment_status', 'document_payment_date', 'document_export_date'}.intersection(vals):
            self._draft()
            if 'company_id' in vals and any(r.company_id.id != vals['company_id'] for r in self):
                raise UserError(_('Create a new Qiwa batch to change its company.'))
        if 'reference' in vals:
            vals = dict(vals, reference=self._normalize_reference(vals['reference']))
        return super().write(vals)

    def copy(self, default=None):
        raise UserError(_('Qiwa batches cannot be duplicated. Create a new batch.'))

    def unlink(self):
        self._draft()
        if self.line_ids.ptr_line_id or self.env['saddad.ptr'].search_count([('qiwa_batch_id', 'in', self.ids)]):
            raise UserError(_('A Qiwa batch linked to a PTR cannot be deleted.'))
        return super().unlink()

    @api.constrains('issue_date', 'due_date', 'document_payment_date')
    def _check_dates(self):
        if any(r.issue_date and r.due_date and r.due_date < r.issue_date for r in self):
            raise ValidationError(_('The reference due date cannot precede its issue date.'))
        if any(r.issue_date and r.document_payment_date and r.document_payment_date < r.issue_date for r in self):
            raise ValidationError(_('The Qiwa payment date cannot precede the issue date.'))

    def _transition(self, action, expected):
        self._lock()
        for rec in self:
            rule = self.env['saddad.approval.rule']._for_transition(rec.company_id, 'qiwa_' + action)
            if not rule or (not self.env.su and self.env.user not in rule.group_id.all_user_ids):
                raise AccessError(_('You are not authorized by the configured approval rule.'))
            if rec.state != expected:
                raise UserError(_('The Qiwa batch is not in the required workflow state.'))

    def _validate_ready(self):
        for rec in self:
            if not rec.reference or not rec.issue_date or not rec.line_ids:
                raise UserError(_('Enter the Qiwa reference, issue date and at least one employee line.'))
            if rec.document_payment_status == 'paid':
                if not rec.document_payment_date or rec.document_payment_date > fields.Date.context_today(rec):
                    raise UserError(_('A paid Qiwa document requires a payment date that is not in the future.'))
            elif not rec.due_date:
                raise UserError(_('An unpaid Qiwa document requires a reference due date.'))
            if rec.document_payment_status != 'paid' and rec.due_date < fields.Date.context_today(rec):
                raise UserError(_('The Qiwa payment reference has expired. Reset and correct the draft.'))
            if rec.issue_date > fields.Date.context_today(rec):
                raise UserError(_('The reference issue date cannot be in the future.'))
            rec.line_ids._validate_business()
            if rec.period and any(line.period != rec.period for line in rec.line_ids):
                raise ValidationError(_('Employee periods must match the common period, or leave Common Period empty.'))

    def action_review(self):
        self._transition('review', 'draft')
        self._validate_ready()
        for rec in self:
            super(QiwaBatch, rec).write({'state': 'reviewed', 'reviewed_by': self.env.uid, 'reviewed_at': fields.Datetime.now()})
        self._notify('qiwa_confirm')
        return True

    def action_confirm(self):
        self._transition('confirm', 'reviewed')
        self._validate_ready()
        for rec in self:
            super(QiwaBatch, rec).write({'state': 'confirmed', 'confirmed_by': self.env.uid, 'confirmed_at': fields.Datetime.now()})
            rec.message_post(body=_('Qiwa batch confirmed.'))
        self._complete_activities()
        self._after_confirm()
        return True

    def _after_confirm(self):
        """Muqeem extension must create one consolidated expense per batch, atomically."""

    def action_reset_draft(self):
        self._transition('reset', 'reviewed')
        super(QiwaBatch, self).write({'state': 'draft'})
        self._complete_activities()
        self.message_post(body=_('Qiwa batch reset to Draft.')) if len(self) == 1 else None
        return True

    def action_request_review(self):
        self._draft()
        self._validate_ready()
        self._notify('qiwa_review')
        return True

    def _complete_activities(self):
        activity = self.env.ref('Saddad.activity_qiwa_approval')
        self.sudo().activity_ids.filtered(lambda a: a.activity_type_id == activity).action_feedback()

    def _notify(self, transition):
        self._complete_activities()
        template = self.env.ref('Saddad.mail_template_qiwa_approval')
        activity = self.env.ref('Saddad.activity_qiwa_approval')
        for rec in self:
            rule = self.env['saddad.approval.rule']._for_transition(rec.company_id, transition)
            if not rule:
                continue
            users = rule.sudo().group_id.all_user_ids.filtered(lambda u: u.active and not u.share and rec.company_id in u.company_ids)
            for user in users:
                if not rec.with_user(user).with_context(allowed_company_ids=[rec.company_id.id]).has_access('read'):
                    continue
                if rule.notify_activity:
                    rec.sudo().activity_schedule('Saddad.activity_qiwa_approval', user_id=user.id,
                        summary=rec.with_context(lang=user.lang).env._('Qiwa approval required'), date_deadline=fields.Date.context_today(rec))
                if rule.notify_email and user.email:
                    template.sudo().with_context(lang=user.lang).send_mail(rec.id, force_send=False,
                        email_values={'recipient_ids': [(6, 0, user.partner_id.ids)], 'email_to': False})

    def action_import_pdf(self):
        self.ensure_one()
        self._draft()
        return {'type': 'ir.actions.act_window', 'name': _('Qiwa PDF Assistance'), 'res_model': 'saddad.qiwa.import',
                'view_mode': 'form', 'target': 'new', 'context': {'default_batch_id': self.id}}


class QiwaLine(models.Model):
    _name = 'saddad.qiwa.line'
    _description = 'Qiwa Employee Line'
    _check_company_auto = True

    batch_id = fields.Many2one('saddad.qiwa.batch', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='batch_id.company_id', store=True)
    currency_id = fields.Many2one(related='batch_id.currency_id')
    employee_id = fields.Many2one('hr.employee', required=True, check_company=True, ondelete='restrict')
    iqama_number = fields.Char(string='Iqama / Identification No.', readonly=True)
    mapping_id = fields.Many2one('saddad.service.mapping', required=True, check_company=True, ondelete='restrict', domain="[('service_type', '=', 'work_permit')]")
    product_id = fields.Many2one('product.product', readonly=True, check_company=True)
    period = fields.Selection(PERIODS, readonly=True)
    permit_valid_until = fields.Date(string='Work Permit Valid Until')
    amount = fields.Monetary(required=True)
    amount_source = fields.Selection([('cost', 'Product Cost'), ('external', 'External Amount'), ('ptr', 'Reviewed PTR Cost')], default='cost', required=True)
    external_reason = fields.Char(string='External Amount Explanation')
    ptr_line_id = fields.Many2one('saddad.ptr.line', readonly=True, copy=False, ondelete='restrict', check_company=True)
    ptr_id = fields.Many2one(related='ptr_line_id.request_id', store=True)
    downstream_state = fields.Selection(related='batch_id.downstream_state')

    _employee_unique = models.Constraint('UNIQUE(batch_id, employee_id)', 'An employee may appear only once in a Qiwa batch.')
    _ptr_unique = models.Constraint('UNIQUE(ptr_line_id)', 'This PTR service line already belongs to a Qiwa batch.')

    @api.onchange('mapping_id')
    def _onchange_mapping(self):
        self.product_id = self.mapping_id.product_id
        self.period = self.mapping_id.period
        if self.amount_source == 'cost':
            self.amount = self.product_id.with_company(self.company_id).standard_price

    @api.model
    def _prepare(self, vals, batch, current=None):
        result = dict(vals)
        employee = self.env['hr.employee'].browse(vals.get('employee_id', current.employee_id.id if current else False))
        mapping = self.env['saddad.service.mapping'].browse(vals.get('mapping_id', current.mapping_id.id if current else False))
        employee.check_access('read')
        mapping.check_access('read')
        if not employee or not employee.active or employee.company_id != batch.company_id or not (employee.identification_id or '').strip():
            raise ValidationError(_('Select an active employee in the batch company with an identification number.'))
        if not mapping or not mapping.active or mapping.company_id != batch.company_id or mapping.service_type != 'work_permit' or not mapping.product_id.active or mapping.product_id.type != 'service':
            raise ValidationError(_('Select an active work-permit mapping for the batch company.'))
        result.update(iqama_number=employee.identification_id, product_id=mapping.product_id.id, period=mapping.period)
        source = vals.get('amount_source', current.amount_source if current else 'cost')
        if source == 'cost':
            result['amount'] = mapping.product_id.with_company(batch.company_id).standard_price
        return result

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            if {'ptr_line_id', 'iqama_number', 'product_id', 'period', 'company_id', 'currency_id', 'ptr_id', 'downstream_state'}.intersection(vals) or vals.get('amount_source') == 'ptr':
                raise AccessError(_('Qiwa source links and snapshots are managed by Saddad.'))
            batch = self.env['saddad.qiwa.batch'].browse(vals.get('batch_id')).exists()
            if not batch:
                raise ValidationError(_('A Qiwa employee line must belong to a batch.'))
            batch._draft()
            prepared.append(self._prepare(vals, batch))
        return super().create(prepared)

    def write(self, vals):
        if {'batch_id', 'ptr_line_id', 'iqama_number', 'product_id', 'period', 'company_id', 'currency_id', 'ptr_id', 'downstream_state'}.intersection(vals) or vals.get('amount_source') == 'ptr':
            raise AccessError(_('Qiwa source links and snapshots are managed by Saddad.'))
        self.batch_id._draft()
        for line in self:
            if line.ptr_line_id and {'employee_id', 'mapping_id'}.intersection(vals):
                raise UserError(_('Employee and mapping on a PTR-linked line cannot be changed.'))
            if line.ptr_line_id and vals.get('amount_source') == 'cost':
                raise UserError(_('Use the reviewed PTR amount or an explained external amount on PTR-linked lines.'))
            if line.amount_source == 'ptr' and 'amount' in vals and vals.get('amount_source') != 'external':
                raise UserError(_('Select External Amount and enter an explanation to override the PTR amount.'))
            old_amount = line.amount
            super(QiwaLine, line).write(self._prepare(vals, line.batch_id, line))
            if old_amount != line.amount:
                line.batch_id.message_post(body=_('Employee fee changed for %(employee)s: %(old)s → %(new)s. %(reason)s',
                    employee=line.employee_id.name, old=old_amount, new=line.amount, reason=line.external_reason or ''))
        return True

    def unlink(self):
        self.batch_id._draft()
        if self.ptr_line_id:
            raise UserError(_('A PTR-linked Qiwa line cannot be deleted.'))
        return super().unlink()

    @api.constrains('amount', 'amount_source', 'external_reason')
    def _check_amount(self):
        if any(line.amount <= 0 for line in self):
            raise ValidationError(_('Qiwa employee amounts must be greater than zero.'))
        if any(line.amount_source == 'external' and not (line.external_reason or '').strip() for line in self):
            raise ValidationError(_('Explain each externally supplied amount.'))

    def _validate_business(self):
        for line in self:
            line._prepare({}, line.batch_id, line)
            if line.product_id != line.mapping_id.product_id or line.period != line.mapping_id.period:
                raise ValidationError(_('The service mapping changed. Reset to Draft and refresh the employee line.'))
            if line.employee_id.identification_id != line.iqama_number:
                raise ValidationError(_('Employee identification changed. Reset to Draft and refresh the employee line.'))
            if line.ptr_line_id and (line.ptr_id.state != 'confirmed' or line.ptr_id.company_id != line.company_id):
                raise ValidationError(_('Linked PTRs must be confirmed and belong to the batch company.'))
        self._check_amount()

    @api.model
    def _from_ptr(self, batch, source):
        """Private bridge: caller has checked confirmation permissions and locked PTR."""
        batch._draft()
        source.check_access('read')
        if source.request_id.state != 'confirmed' or source.company_id != batch.company_id or source.service_type != 'work_permit':
            raise ValidationError(_('Only confirmed work-permit PTR lines can be linked.'))
        existing = self.search([('ptr_line_id', '=', source.id)], limit=1)
        if existing:
            if existing.batch_id != batch:
                raise ValidationError(_('This PTR service line already belongs to a Qiwa batch.'))
            return existing
        mapping = self.env['saddad.service.mapping'].search([('company_id', '=', batch.company_id.id), ('service_type', '=', 'work_permit'), ('period', '=', source.period), ('product_id', '=', source.product_id.id)], limit=1)
        values = self._prepare({'employee_id': source.request_id.employee_id.id, 'mapping_id': mapping.id,
                               'amount_source': 'ptr', 'amount': source.amount}, batch)
        values.update(batch_id=batch.id, ptr_line_id=source.id)
        return super(QiwaLine, self).create(values)


class QiwaApprovalRule(models.Model):
    _inherit = 'saddad.approval.rule'
    transition = fields.Selection(selection_add=[('qiwa_review', 'Review Qiwa'), ('qiwa_confirm', 'Confirm Qiwa'), ('qiwa_reset', 'Reset Qiwa to Draft')], ondelete={'qiwa_review': 'cascade', 'qiwa_confirm': 'cascade', 'qiwa_reset': 'cascade'})


class PtrQiwa(models.Model):
    _inherit = 'saddad.ptr'
    qiwa_batch_id = fields.Many2one('saddad.qiwa.batch', string='Qiwa Batch', check_company=True, ondelete='restrict', copy=False, tracking=True)
    qiwa_handoff_state = fields.Selection(selection_add=[('linked', 'Linked to Qiwa')], ondelete={'linked': 'set default'})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_qiwa_target()
        return records

    def write(self, vals):
        if 'qiwa_batch_id' in vals:
            self.check_access('write')
            self._lock_workflow()
            if any(rec.state != 'draft' for rec in self):
                raise UserError(_('Select the Qiwa target while the PTR is in Draft.'))
        result = super().write(vals)
        if 'qiwa_batch_id' in vals:
            self._check_qiwa_target()
        return result

    def _check_qiwa_target(self):
        for rec in self:
            if rec.qiwa_batch_id:
                rec.qiwa_batch_id.check_access('write')
                if rec.qiwa_batch_id.company_id != rec.company_id or rec.qiwa_batch_id.state != 'draft':
                    raise ValidationError(_('Select a draft Qiwa batch in the PTR company.'))

    def _after_confirm(self):
        for rec in self:
            lines = rec.line_ids.filtered(lambda l: l.service_type == 'work_permit')
            if not lines:
                if rec.qiwa_batch_id:
                    raise ValidationError(_('A PTR targeting Qiwa must contain a work-permit service line.'))
                continue
            if len(lines) != 1:
                raise ValidationError(_('Use exactly one work-permit service line per PTR for Qiwa processing.'))
            batch = rec.qiwa_batch_id
            if not batch:
                batch = self.env['saddad.qiwa.batch'].create({'company_id': rec.company_id.id, 'period': lines.period})
            self.env['saddad.qiwa.line']._from_ptr(batch, lines)
            # Bypass only the public protected-field guard after the workflow checks.
            from .ptr import PaymentTransferRequest
            super(PaymentTransferRequest, rec).write({'qiwa_batch_id': batch.id, 'qiwa_handoff_state': 'linked'})
            rec.message_post(body=_('Work-permit service linked to Qiwa batch %s.', batch.name))

    def action_prepare_qiwa(self):
        """Explicit backfill for confirmed requests installed before Qiwa support."""
        self._check_transition('confirm', 'confirmed')
        self.filtered(lambda r: r.qiwa_handoff_state == 'pending')._after_confirm()
        return True
