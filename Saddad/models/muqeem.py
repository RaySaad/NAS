from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, Command, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .configuration import PERIODS

STATES = [('draft', 'Draft'), ('assistant', 'HR Assistant'), ('hr', 'HR Confirmed'),
          ('finance', 'Financial Approval'), ('gm', 'GM'), ('payment', 'Payment'),
          ('done', 'Done'), ('posted', 'Posted'), ('rejected', 'Rejected')]
TRANSITIONS = [('submit', 'Submit Muqeem'), ('assistant', 'Review Muqeem HR Assistant'),
               ('hr', 'Approve Muqeem HR'), ('finance', 'Approve Muqeem Finance'),
               ('gm', 'Approve Muqeem GM'), ('payment', 'Record Muqeem Payment'),
               ('post', 'Post Muqeem'), ('reset', 'Reset Muqeem')]
FLOW = {'draft': ('submit', 'assistant'), 'assistant': ('assistant', 'hr'),
        'hr': ('hr', 'finance'), 'finance': ('finance', 'gm'), 'gm': ('gm', 'payment')}


class MuqeemExpense(models.Model):
    _name = 'saddad.muqeem.expense'
    _description = 'Muqeem Expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'id desc'

    name = fields.Char(default='/', readonly=True, required=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    state = fields.Selection(STATES, default='draft', readonly=True, required=True, tracking=True, copy=False)
    reference = fields.Char(tracking=True)
    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    qiwa_batch_id = fields.Many2one('saddad.qiwa.batch', readonly=True, copy=False, check_company=True, ondelete='restrict')
    line_ids = fields.One2many('saddad.muqeem.line', 'expense_id', string='Expense Lines', copy=False)
    journal_id = fields.Many2one('account.journal', string='Bank / Cash Journal', check_company=True,
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]", tracking=True,
        default=lambda s: s.env.company.saddad_bank_journal_id)
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True, copy=False, check_company=True, ondelete='restrict')
    deferred_move_count = fields.Integer(string='Deferred Entries', compute='_compute_deferred_count')
    total_amount = fields.Monetary(compute='_compute_total', store=True)
    paid_amount = fields.Monetary(compute='_compute_total', store=True)
    notes = fields.Text()
    rejection_reason = fields.Text(readonly=True, copy=False, tracking=True)
    action_user_id = fields.Many2one('res.users', string='Last Action By', readonly=True, copy=False)
    action_at = fields.Datetime(string='Last Action At', readonly=True, copy=False)
    can_approve = fields.Boolean(compute='_compute_actions')
    can_reject = fields.Boolean(compute='_compute_actions')
    can_reset = fields.Boolean(compute='_compute_actions')
    can_pay = fields.Boolean(compute='_compute_actions')
    can_post = fields.Boolean(compute='_compute_actions')
    _qiwa_unique = models.Constraint('UNIQUE(qiwa_batch_id)', 'A Qiwa batch can have only one Muqeem expense.')

    @api.depends('move_id.deferred_move_ids')
    def _compute_deferred_count(self):
        for rec in self:
            rec.deferred_move_count = len(rec.move_id.sudo().deferred_move_ids)

    def action_open_deferrals(self):
        self.ensure_one()
        self.check_access('read')
        self.move_id.check_access('read')
        return self.move_id.open_deferred_entries()

    @api.depends('line_ids.total', 'line_ids.paid')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('total'))
            rec.paid_amount = sum(rec.line_ids.filtered('paid').mapped('total'))

    def _allowed(self, action):
        self.ensure_one()
        rule = self.env['saddad.approval.rule']._for_transition(self.company_id, 'muqeem_' + action)
        return bool(rule and (self.env.su or self.env.user in rule.group_id.all_user_ids))

    @api.depends('state', 'company_id')
    @api.depends_context('uid')
    def _compute_actions(self):
        for rec in self:
            rec.can_approve = rec.state in FLOW and rec._allowed(FLOW[rec.state][0])
            rec.can_reject = rec.state in ('assistant', 'hr', 'finance', 'gm') and rec._allowed(rec.state)
            rec.can_reset = rec.state == 'rejected' and rec._allowed('reset')
            rec.can_pay = rec.state in ('payment', 'done') and rec._allowed('payment')
            rec.can_post = rec.state == 'done' and rec._allowed('post')

    def _lock(self):
        self.check_access('write')
        if self.ids:
            self.env.cr.execute('SELECT id FROM saddad_muqeem_expense WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
            self.invalidate_recordset()
            self.line_ids.invalidate_recordset()

    def _check_action(self, action, states):
        self._lock()
        for rec in self:
            if rec.company_id not in self.env.companies or not rec._allowed(action):
                raise AccessError(_('You are not authorized for this Muqeem action.'))
            if rec.state not in states:
                raise UserError(_('The Muqeem expense is not in the required state.'))

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if {'move_id', 'qiwa_batch_id', 'action_user_id', 'action_at', 'rejection_reason', 'total_amount', 'paid_amount'}.intersection(vals) or vals.get('state', 'draft') != 'draft' or vals.get('name', '/') != '/':
                raise AccessError(_('Use Muqeem actions to change protected fields.'))
            company = self.env['res.company'].browse(vals.get('company_id') or self.env.company.id)
            probe = self.new({'company_id': company.id})
            if company not in self.env.companies or not probe._allowed('submit'):
                raise AccessError(_('You are not authorized to create Muqeem expenses in this company.'))
            if 'journal_id' in vals and vals['journal_id'] != company.saddad_bank_journal_id.id and not probe._allowed('payment'):
                raise AccessError(_('Only the configured Payment group can select the bank journal.'))
            vals.update(company_id=company.id, journal_id=vals.get('journal_id', company.saddad_bank_journal_id.id),
                        name=self.env['ir.sequence'].with_company(company).next_by_code('saddad.muqeem.expense') or '/')
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if {'state', 'name', 'move_id', 'qiwa_batch_id', 'action_user_id', 'action_at', 'rejection_reason', 'total_amount', 'paid_amount'}.intersection(vals):
            raise AccessError(_('Use Muqeem actions to change protected fields.'))
        self._lock()
        if 'company_id' in vals and any(r.company_id.id != vals['company_id'] for r in self):
            raise UserError(_('Create a new expense to change its company.'))
        if 'journal_id' in vals:
            self._check_action('payment', ['draft', 'assistant', 'hr', 'finance', 'gm', 'payment'])
            if self.line_ids.filtered('paid'):
                raise UserError(_('Reverse unposted payment marks before changing the bank journal.'))
        if {'reference', 'date', 'line_ids', 'notes'}.intersection(vals):
            self._check_action('submit', ['draft'])
        return super().write(vals)

    def copy(self, default=None):
        raise UserError(_('Create a new Muqeem expense instead of duplicating it.'))

    def unlink(self):
        self._check_action('submit', ['draft'])
        if self.qiwa_batch_id:
            raise UserError(_('A Qiwa-linked expense cannot be deleted.'))
        return super().unlink()

    def _set_state(self, state):
        for rec in self:
            super(MuqeemExpense, rec).write({'state': state, 'action_user_id': self.env.uid, 'action_at': fields.Datetime.now()})
            rec.message_post(body=_('Muqeem stage changed to %s.', dict(STATES)[state]))
        self._notify_next()

    def _validate_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_('Add at least one expense line.'))
            rec.line_ids._validate_business()
            if rec.qiwa_batch_id:
                source = rec.qiwa_batch_id.line_ids
                linked = rec.line_ids.filtered('qiwa_line_id')
                if set(linked.qiwa_line_id.ids) != set(source.ids) or len(linked) != len(source):
                    raise ValidationError(_('All Qiwa employee lines must remain in the consolidated expense.'))

    def action_approve(self):
        for rec in self:
            action, target = FLOW.get(rec.state, (False, False))
            if not action:
                raise UserError(_('This stage has no approval action.'))
            rec._check_action(action, [rec.state])
            rec._validate_lines()
            rec._set_state(target)
        return True

    def action_reject(self):
        self.ensure_one()
        self._check_action(self.state, ['assistant', 'hr', 'finance', 'gm'])
        return {'type': 'ir.actions.act_window', 'name': _('Reject Muqeem Expense'), 'res_model': 'saddad.muqeem.reject',
                'view_mode': 'form', 'target': 'new', 'context': {'default_expense_id': self.id}}

    def action_reset(self):
        self._check_action('reset', ['rejected'])
        self._set_state('draft')
        return True

    def _validate_journal(self):
        self.ensure_one()
        journal = self.journal_id.sudo()
        if not journal or journal.company_id != self.company_id or journal.type not in ('bank', 'cash') or not journal.default_account_id or not journal.active:
            raise ValidationError(_('Select an active Bank/Cash journal with a default account in the expense company.'))
        if journal.currency_id and journal.currency_id != self.currency_id:
            raise ValidationError(_('The bank journal must use the expense company currency.'))
        if self.company_id not in journal.default_account_id.company_ids or not journal.default_account_id.active:
            raise ValidationError(_('The bank account must be active and belong to the expense company.'))

    def action_post(self):
        self._check_action('post', ['done'])
        for rec in self:
            rec._validate_lines()
            rec._validate_journal()
            if rec.move_id or any(not l.paid or l.move_line_id for l in rec.line_ids):
                raise ValidationError(_('Posting requires all lines Paid and no previous posting.'))
            # Narrow escalation: a process-specific Post role may create only this validated JV.
            move = self.env['account.move'].sudo().with_company(rec.company_id).create({
                'move_type': 'entry', 'company_id': rec.company_id.id, 'journal_id': rec.journal_id.id,
                'date': rec.date, 'ref': '%s / %s' % (rec.name, rec.reference or ''),
                'line_ids': rec._move_commands()})
            super(MuqeemExpense, rec).write({'move_id': move.id})
            move.action_post()
            for line in rec.line_ids:
                debit = move.line_ids.filtered(lambda m: m.name == '%s / %s' % (rec.name, line.id))[:1]
                super(MuqeemLine, line).write({'move_line_id': debit.id})
            rec._set_state('posted')
            rec._generate_deferrals()
        return True

    def _move_commands(self):
        commands = []
        for line in self.line_ids:
            account = line._debit_account()
            taxes = line.tax_ids.sudo().with_company(self.company_id).compute_all(line.amount, currency=self.currency_id,
                quantity=1, product=line.product_id, partner=line.employee_id.work_contact_id)
            if self.currency_id.compare_amounts(taxes['total_included'], line.total):
                raise ValidationError(_('Tax configuration changed after the expense amount was calculated. Review the expense before posting.'))
            commands.append(Command.create({'name': '%s / %s' % (self.name, line.id), 'account_id': account.id,
                'product_id': line.product_id.id, 'deferred_start_date': line.defer_start if line.defer_expense else False,
                'deferred_end_date': line.defer_end if line.defer_expense else False,
                'debit': taxes['total_excluded'], 'credit': 0, 'partner_id': line.employee_id.work_contact_id.id,
                'date_maturity': self.date if account.account_type == 'asset_receivable' else False,
                'tax_ids': [Command.set(line.tax_ids.ids)], 'tax_tag_ids': [Command.set(taxes['base_tags'])]}))
            for tax in taxes['taxes']:
                if not tax['account_id']:
                    raise ValidationError(_('Configure an account on every selected tax repartition line.'))
                tax_account = self.env['account.account'].sudo().browse(tax['account_id'])
                if self.company_id not in tax_account.company_ids or not tax_account.active:
                    raise ValidationError(_('Tax accounts must be active and belong to the expense company.'))
                commands.append(Command.create({'name': tax['name'], 'account_id': tax['account_id'],
                    'debit': tax['amount'], 'credit': 0, 'tax_repartition_line_id': tax['tax_repartition_line_id'],
                    'tax_tag_ids': [Command.set(tax['tag_ids'])], 'tax_base_amount': tax['base']}))
        commands.append(Command.create({'name': self.reference or self.name, 'account_id': self.journal_id.default_account_id.id,
                                       'debit': 0, 'credit': self.total_amount}))
        return commands

    def action_open_entry(self):
        self.ensure_one()
        self.check_access('read')
        self.move_id.check_access('read')
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': self.move_id.id, 'view_mode': 'form'}

    def _notify_next(self):
        activity = self.env.ref('Saddad.activity_muqeem')
        template = self.env.ref('Saddad.mail_template_muqeem')
        for rec in self:
            rec.sudo().activity_ids.filtered(lambda a: a.activity_type_id == activity).action_feedback()
            action = {'assistant': 'assistant', 'hr': 'hr', 'finance': 'finance', 'gm': 'gm', 'payment': 'payment', 'done': 'post', 'rejected': 'reset'}.get(rec.state)
            if not action:
                continue
            rule = self.env['saddad.approval.rule']._for_transition(rec.company_id, 'muqeem_' + action)
            users = rule.sudo().group_id.all_user_ids.filtered(lambda u: u.active and not u.share and rec.company_id in u.company_ids)
            for user in users:
                if not rec.with_user(user).with_context(allowed_company_ids=[rec.company_id.id]).has_access('read'):
                    continue
                if rule.notify_activity:
                    rec.sudo().activity_schedule('Saddad.activity_muqeem', user_id=user.id,
                        summary=rec.with_context(lang=user.lang).env._('Muqeem action required'))
                if rule.notify_email and user.email:
                    template.sudo().with_context(lang=user.lang).send_mail(rec.id, force_send=False,
                        email_values={'recipient_ids': [Command.set(user.partner_id.ids)], 'email_to': False})


class MuqeemLine(models.Model):
    _name = 'saddad.muqeem.line'
    _description = 'Muqeem Expense Line'
    _check_company_auto = True
    expense_id = fields.Many2one('saddad.muqeem.expense', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='expense_id.company_id', store=True)
    currency_id = fields.Many2one(related='expense_id.currency_id')
    employee_id = fields.Many2one('hr.employee', required=True, check_company=True, ondelete='restrict')
    department_id = fields.Many2one(related='employee_id.department_id', store=True)
    muqeem_category_id = fields.Many2one('product.category', compute='_compute_muqeem_category', string='Muqeem Product Category')
    product_id = fields.Many2one('product.product', required=True, check_company=True, ondelete='restrict', domain="[('type', '=', 'service'), ('active', '=', True), ('categ_id', 'child_of', muqeem_category_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    def action_open_expense(self):
        self.ensure_one()
        self.check_access('read')
        self.expense_id.check_access('read')
        return {'type': 'ir.actions.act_window', 'res_model': 'saddad.muqeem.expense',
                'res_id': self.expense_id.id, 'view_mode': 'form', 'target': 'current'}

    @api.depends('company_id', 'company_id.saddad_muqeem_category_id')
    def _compute_muqeem_category(self):
        for line in self:
            line.muqeem_category_id = line.company_id.saddad_muqeem_category_id or self.env.ref('Saddad.category_muqeem', raise_if_not_found=False)

    def _validate_product_category(self):
        for line in self:
            category = line.muqeem_category_id
            if not category or not self.env['product.category'].search_count([('id', '=', line.product_id.categ_id.id), ('id', 'child_of', category.id)]):
                raise ValidationError(_('Select a product in the configured Muqeem category or its subcategories.'))

    period = fields.Selection(PERIODS, default='3')
    amount = fields.Monetary(required=True)
    tax_ids = fields.Many2many('account.tax', check_company=True, domain="[('type_tax_use', '=', 'purchase'), ('company_id', '=', company_id)]")
    total = fields.Monetary(compute='_compute_total', store=True)
    paid_for = fields.Selection([('company', 'Company'), ('employee', 'Employee')], default='company', required=True)
    paid = fields.Boolean(readonly=True, copy=False)
    paid_by = fields.Many2one('res.users', readonly=True, copy=False)
    paid_at = fields.Datetime(readonly=True, copy=False)
    payment_date = fields.Date(readonly=True, copy=False)
    qiwa_line_id = fields.Many2one('saddad.qiwa.line', readonly=True, copy=False, check_company=True, ondelete='restrict')
    move_line_id = fields.Many2one('account.move.line', readonly=True, copy=False, check_company=True, ondelete='restrict')
    defer_expense = fields.Boolean(string='Defer Expense')
    defer_start = fields.Date(string='Deferral Start Date')
    defer_end = fields.Date(string='Deferral End Date')
    _qiwa_unique = models.Constraint('UNIQUE(qiwa_line_id)', 'A Qiwa line can be included only once.')

    @api.depends('amount', 'tax_ids', 'product_id', 'company_id')
    def _compute_total(self):
        for line in self:
            line.total = line.tax_ids.sudo().with_company(line.company_id).compute_all(line.amount, currency=line.currency_id, quantity=1, product=line.product_id)['total_included'] if line.company_id else line.amount

    @api.onchange('product_id')
    def _onchange_product(self):
        self.amount = self.product_id.with_company(self.company_id).standard_price
        self.tax_ids = self.product_id.supplier_taxes_id.filtered(lambda t: t.company_id == self.company_id)

    @api.onchange('employee_id', 'period')
    def _onchange_expiry(self):
        self.defer_start = self.employee_id.saddad_iqama_expiry
        self._onchange_start()

    @api.onchange('defer_start')
    def _onchange_start(self):
        self.defer_end = self.defer_start + relativedelta(months=int(self.period), days=-1) if self.defer_start and self.period else False

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if {'paid', 'paid_by', 'paid_at', 'payment_date', 'move_line_id', 'qiwa_line_id', 'total'}.intersection(vals):
                raise AccessError(_('Use the payment and posting actions for protected expense line fields.'))
            parent = self.env['saddad.muqeem.expense'].browse(vals.get('expense_id'))
            parent._check_action('submit', ['draft'])
            product = self.env['product.product'].browse(vals.get('product_id'))
            employee = self.env['hr.employee'].browse(vals.get('employee_id'))
            product.check_access('read')
            employee.check_access('read')
            vals.setdefault('amount', product.with_company(parent.company_id).standard_price)
            vals.setdefault('tax_ids', [Command.set(product.supplier_taxes_id.filtered(lambda t: t.company_id == parent.company_id).ids)])
            vals.setdefault('defer_start', employee.saddad_iqama_expiry)
            start = fields.Date.to_date(vals.get('defer_start'))
            vals.setdefault('defer_end', start + relativedelta(months=int(vals.get('period') or '3'), days=-1) if start else False)
            prepared.append(vals)
        records = super().create(prepared)
        records._validate_business()
        records._validate_product_category()
        return records

    def write(self, vals):
        if {'paid', 'paid_by', 'paid_at', 'payment_date', 'move_line_id', 'qiwa_line_id', 'total', 'company_id'}.intersection(vals):
            raise AccessError(_('Use the payment and posting actions for protected expense line fields.'))
        self.expense_id._check_action('submit', ['draft'])
        if 'expense_id' in vals and any(l.expense_id.id != vals['expense_id'] for l in self):
            raise AccessError(_('Expense lines cannot be moved to another expense.'))
        if self.filtered('qiwa_line_id') and {'employee_id', 'product_id', 'period', 'amount'}.intersection(vals):
            raise UserError(_('The employee, product, period and amount of a Qiwa line are fixed by its confirmed source.'))
        result = super().write(vals)
        self._validate_business()
        self._validate_product_category()
        return result

    def unlink(self):
        self.expense_id._check_action('submit', ['draft'])
        if self.qiwa_line_id:
            raise UserError(_('Qiwa-linked expense lines cannot be deleted.'))
        return super().unlink()

    def _validate_business(self):
        for line in self:
            if not line.employee_id.active or line.employee_id.company_id != line.company_id or not line.product_id.active or line.product_id.type != 'service':
                raise ValidationError(_('Use an active employee and service product in the expense company.'))
            if line.currency_id.compare_amounts(line.amount, 0) <= 0:
                raise ValidationError(_('Expense amounts must be positive.'))
            if any(t.company_id != line.company_id or t.type_tax_use != 'purchase' or t.tax_exigibility != 'on_invoice' or t.amount_type != 'percent' or t.amount < 0 for t in line.tax_ids):
                raise ValidationError(_('Use non-negative purchase percentage taxes due on invoice in the expense company.'))
            if line.defer_expense and (not line.defer_start or not line.defer_end or line.defer_end <= line.defer_start or line.paid_for != 'company'):
                raise ValidationError(_('Deferred company expenses require an end date after the start date.'))
            if line.qiwa_line_id and (line.qiwa_line_id.batch_id != line.expense_id.qiwa_batch_id or line.qiwa_line_id.employee_id != line.employee_id or line.qiwa_line_id.product_id != line.product_id or line.qiwa_line_id.period != line.period or line.currency_id.compare_amounts(line.qiwa_line_id.amount, line.amount)):
                raise ValidationError(_('Qiwa source values must match the expense line.'))

    def _debit_account(self):
        self.ensure_one()
        if self.paid_for == 'employee':
            account = self.company_id.saddad_employee_loan_account_id.sudo()
        else:
            product = self.product_id.sudo().with_company(self.company_id)
            account = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id
        if not account or not account.active or self.company_id not in account.company_ids:
            raise ValidationError(_('Configure an active expense or employee-loan account in the expense company.'))
        if self.paid_for == 'company' and account.account_type not in ('expense', 'expense_direct_cost', 'expense_depreciation'):
            raise ValidationError(_('Company-paid lines require an expense account.'))
        if self.paid_for == 'employee' and account.account_type not in ('asset_current', 'asset_receivable'):
            raise ValidationError(_('Employee-paid lines require a current asset or receivable loan account.'))
        if account.account_type == 'asset_receivable' and not self.employee_id.work_contact_id:
            raise ValidationError(_('Set the employee work contact for receivable posting.'))
        return account

    def action_mark_paid(self):
        self.expense_id._check_action('payment', ['payment'])
        for line in self:
            if line.paid or line.move_line_id:
                raise UserError(_('This line is already paid or posted.'))
            line.expense_id._validate_journal()
            super(MuqeemLine, line).write({'paid': True, 'paid_by': self.env.uid, 'paid_at': fields.Datetime.now(), 'payment_date': fields.Date.context_today(line)})
            line.expense_id.message_post(body=_('Payment recorded for employee %s.', line.employee_id.name))
        for parent in self.expense_id:
            if all(parent.line_ids.mapped('paid')):
                parent._set_state('done')
        return True

    def action_unmark_paid(self):
        self.expense_id._check_action('payment', ['payment', 'done'])
        for line in self:
            if not line.paid or line.move_line_id:
                raise UserError(_('Only unposted paid lines can be reversed.'))
            super(MuqeemLine, line).write({'paid': False, 'paid_by': False, 'paid_at': False, 'payment_date': False})
            line.expense_id.message_post(body=_('Payment mark reversed for employee %s.', line.employee_id.name))
        self.expense_id._set_state('payment')
        return True


class MuqeemReject(models.TransientModel):
    _name = 'saddad.muqeem.reject'
    _description = 'Reject Muqeem Expense'
    expense_id = fields.Many2one('saddad.muqeem.expense', required=True)
    reason = fields.Text(required=True)

    def action_apply(self):
        self.ensure_one()
        rec = self.expense_id
        rec._check_action(rec.state, ['assistant', 'hr', 'finance', 'gm'])
        if not (self.reason or '').strip():
            raise ValidationError(_('Enter a rejection reason.'))
        super(MuqeemExpense, rec).write({'rejection_reason': self.reason.strip()})
        rec._set_state('rejected')
        return {'type': 'ir.actions.act_window_close'}


class MuqeemApproval(models.Model):
    _inherit = 'saddad.approval.rule'
    transition = fields.Selection(selection_add=[('muqeem_' + key, label) for key, label in TRANSITIONS],
                                 ondelete={'muqeem_' + key: 'cascade' for key, label in TRANSITIONS})


class MuqeemCompany(models.Model):
    _inherit = 'res.company'
    saddad_muqeem_category_id = fields.Many2one('product.category', string='Muqeem Product Category', prefetch=False, ondelete='restrict', default=lambda s: s.env.ref('Saddad.category_muqeem', raise_if_not_found=False))
    saddad_bank_journal_id = fields.Many2one('account.journal', string='Default Saddad Bank Journal', check_company=True)
    saddad_employee_loan_account_id = fields.Many2one('account.account', string='Saddad Employee Loan Account', check_company=True)


class MuqeemSettings(models.TransientModel):
    _inherit = 'saddad.settings'
    muqeem_category_id = fields.Many2one('product.category', string='Muqeem Product Category', required=True, default=lambda s: s.env.company.saddad_muqeem_category_id or s.env.ref('Saddad.category_muqeem', raise_if_not_found=False))
    bank_journal_id = fields.Many2one('account.journal', string='Default Bank / Cash Journal', domain="[('company_id', '=', company_id), ('type', 'in', ['bank', 'cash'])]", default=lambda s: s.env.company.saddad_bank_journal_id)
    employee_loan_account_id = fields.Many2one('account.account', string='Employee Loan Account', domain="[('company_ids', 'in', company_id), ('account_type', 'in', ['asset_current', 'asset_receivable'])]", default=lambda s: s.env.company.saddad_employee_loan_account_id)

    @api.onchange('company_id')
    def _onchange_company(self):
        super()._onchange_company()
        self.muqeem_category_id = self.company_id.saddad_muqeem_category_id or self.env.ref('Saddad.category_muqeem', raise_if_not_found=False)
        self.bank_journal_id = self.company_id.saddad_bank_journal_id
        self.employee_loan_account_id = self.company_id.saddad_employee_loan_account_id

    def action_save(self):
        result = super().action_save()
        if self.bank_journal_id and (self.bank_journal_id.company_id != self.company_id or self.bank_journal_id.type not in ('bank', 'cash')):
            raise ValidationError(_('Choose a bank or cash journal in the selected company.'))
        if self.employee_loan_account_id and (self.company_id not in self.employee_loan_account_id.company_ids or self.employee_loan_account_id.account_type not in ('asset_current', 'asset_receivable')):
            raise ValidationError(_('Choose a current asset or receivable loan account in the selected company.'))
        self.company_id.sudo().write({'saddad_muqeem_category_id': self.muqeem_category_id.id, 'saddad_bank_journal_id': self.bank_journal_id.id, 'saddad_employee_loan_account_id': self.employee_loan_account_id.id})
        return result
