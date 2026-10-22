from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .muqeem import MuqeemExpense, MuqeemLine


class PtrMuqeem(models.Model):
    _inherit = 'saddad.ptr'

    direct_muqeem_ids = fields.One2many('saddad.muqeem.expense', 'ptr_id', string='Direct Muqeem Expenses')
    muqeem_expense_ids = fields.Many2many('saddad.muqeem.expense', compute='_compute_muqeem_links', string='Muqeem Expenses')
    muqeem_count = fields.Integer(compute='_compute_muqeem_links', string='Muqeem Expenses')
    can_prepare_muqeem = fields.Boolean(compute='_compute_muqeem_links')
    qiwa_route_state = fields.Selection([('not_ready', 'Not Ready'), ('pending', 'Pending Qiwa Integration'),
        ('linked', 'Linked to Qiwa'), ('not_applicable', 'Not Applicable')], compute='_compute_muqeem_links', string='Qiwa Handoff State')

    @api.depends('state', 'company_id', 'line_ids.service_type', 'direct_muqeem_ids', 'qiwa_batch_id.muqeem_ids', 'qiwa_handoff_state')
    @api.depends_context('uid')
    def _compute_muqeem_links(self):
        for rec in self:
            rec.muqeem_expense_ids = rec.direct_muqeem_ids | rec.qiwa_batch_id.muqeem_ids
            rec.muqeem_count = len(rec.muqeem_expense_ids)
            rule = self.env['saddad.approval.rule']._for_transition(rec.company_id, 'confirm')
            rec.can_prepare_muqeem = bool(rec.state == 'confirmed' and rec.line_ids.filtered(lambda l: l.service_type == 'iqama')
                and not rec.direct_muqeem_ids and rule and (self.env.su or self.env.user in rule.group_id.all_user_ids))
            rec.qiwa_route_state = 'not_applicable' if rec.state == 'confirmed' and not rec.line_ids.filtered(lambda l: l.service_type == 'work_permit') else rec.qiwa_handoff_state

    def _after_confirm(self):
        super()._after_confirm()
        self._prepare_iqama_muqeem()

    def _prepare_iqama_muqeem(self):
        # Caller is an authorized confirm/backfill action. Lock the source before checking
        # for an existing expense; unique source constraints also prevent duplicates.
        self._lock_workflow()
        for request in self:
            if request.state != 'confirmed':
                raise UserError(_('Confirm the PTR before preparing a Muqeem expense.'))
            source_lines = request.line_ids.filtered(lambda l: l.service_type == 'iqama')
            if not source_lines or request.sudo().direct_muqeem_ids:
                continue
            model = self.env['saddad.muqeem.expense'].sudo().with_company(request.company_id)
            expense = super(MuqeemExpense, model).create({
                'name': self.env['ir.sequence'].sudo().with_company(request.company_id).next_by_code('saddad.muqeem.expense'),
                'company_id': request.company_id.id, 'ptr_id': request.id, 'reference': request.name,
                'journal_id': request.company_id.saddad_bank_journal_id.id})
            for source in source_lines:
                line = self.env['saddad.muqeem.line'].sudo().with_company(request.company_id).create({
                    'expense_id': expense.id, 'employee_id': request.employee_id.id,
                    'product_id': source.product_id.id, 'period': source.period, 'amount': source.amount,
                    'tax_ids': [(5, 0, 0)], 'defer_start': request.expiry_date,
                    'defer_end': request.expiry_date + relativedelta(months=int(source.period), days=-1)})
                super(MuqeemLine, line).write({'ptr_line_id': source.id})
            expense._validate_lines()
            expense.message_post(body=_('Created from confirmed Iqama PTR %s. Approval and payment are required separately.', request.name))
            request.message_post(body=_('Iqama renewal linked to Muqeem expense %s.', expense.name))

    def action_prepare_muqeem(self):
        self._check_transition('confirm', 'confirmed', validate_employee=False)
        if any(not r.line_ids.filtered(lambda l: l.service_type == 'iqama') for r in self):
            raise UserError(_('Direct Muqeem preparation requires an Iqama service line.'))
        self._prepare_iqama_muqeem()
        return self.action_open_muqeem() if len(self) == 1 else True

    def action_open_muqeem(self):
        self.ensure_one()
        self.check_access('read')
        expenses = self.muqeem_expense_ids
        return {'type': 'ir.actions.act_window', 'name': _('Muqeem Expenses'), 'res_model': 'saddad.muqeem.expense',
                'view_mode': 'form' if len(expenses) == 1 else 'list,form',
                'res_id': expenses.id if len(expenses) == 1 else False, 'domain': [('id', 'in', expenses.ids)]}


class DirectPtrExpense(models.Model):
    _inherit = 'saddad.muqeem.expense'
    ptr_id = fields.Many2one('saddad.ptr', string='Source PTR', readonly=True, copy=False, check_company=True, ondelete='restrict')
    _ptr_unique = models.Constraint('UNIQUE(ptr_id)', 'An Iqama PTR can have only one direct Muqeem expense.')
    _single_source = models.Constraint('CHECK(ptr_id IS NULL OR qiwa_batch_id IS NULL)', 'An expense cannot have both a direct PTR and a Qiwa batch source.')

    @api.model_create_multi
    def create(self, vals_list):
        if any('ptr_id' in vals for vals in vals_list):
            raise AccessError(_('PTR source links are managed by the confirmation workflow.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'ptr_id' in vals:
            raise AccessError(_('PTR source links are managed by the confirmation workflow.'))
        return super().write(vals)

    def unlink(self):
        if self.ptr_id:
            raise UserError(_('A PTR-linked Muqeem expense cannot be deleted.'))
        return super().unlink()

    def _validate_lines(self):
        super()._validate_lines()
        for rec in self.filtered('ptr_id'):
            source = rec.ptr_id
            expected = source.line_ids.filtered(lambda l: l.service_type == 'iqama')
            linked = rec.line_ids.filtered('ptr_line_id')
            if source.state != 'confirmed' or source.company_id != rec.company_id or set(linked.ptr_line_id.ids) != set(expected.ids) or len(linked) != len(expected):
                raise ValidationError(_('All confirmed Iqama PTR lines must remain linked to their Muqeem expense.'))


class DirectPtrExpenseLine(models.Model):
    _inherit = 'saddad.muqeem.line'
    ptr_line_id = fields.Many2one('saddad.ptr.line', string='Source PTR Line', readonly=True, copy=False, check_company=True, ondelete='restrict')
    _ptr_unique = models.Constraint('UNIQUE(ptr_line_id)', 'A PTR service line can be linked to Muqeem only once.')
    _single_source = models.Constraint('CHECK(ptr_line_id IS NULL OR qiwa_line_id IS NULL)', 'A line cannot have both a direct PTR and a Qiwa line source.')

    @api.model_create_multi
    def create(self, vals_list):
        if any('ptr_line_id' in vals for vals in vals_list):
            raise AccessError(_('PTR source links are managed by the confirmation workflow.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'ptr_line_id' in vals:
            raise AccessError(_('PTR source links are managed by the confirmation workflow.'))
        if self.ptr_line_id and {'employee_id', 'product_id', 'period', 'amount'}.intersection(vals):
            raise UserError(_('The employee, product, period and amount are fixed by the confirmed PTR.'))
        return super().write(vals)

    def unlink(self):
        if self.ptr_line_id:
            raise UserError(_('PTR-linked Muqeem lines cannot be deleted.'))
        return super().unlink()

    def _validate_business(self):
        super()._validate_business()
        for line in self.filtered('ptr_line_id'):
            source = line.ptr_line_id
            request = source.request_id
            if source.service_type != 'iqama' or request.state != 'confirmed' or request != line.expense_id.ptr_id or request.company_id != line.company_id or request.employee_id != line.employee_id or source.product_id != line.product_id or source.period != line.period or line.currency_id.compare_amounts(source.amount, line.amount):
                raise ValidationError(_('The Muqeem line must match its confirmed Iqama PTR source.'))
