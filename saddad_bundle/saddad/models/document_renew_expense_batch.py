# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DocumentRenewExpenseBatch(models.Model):
    _name = 'document.renew.expense.batch'
    _description = 'Muqeem Expense Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Batch Name',
        required=True,
        tracking=True
    )
    date = fields.Date(
        string='Date',
        required=True,
        tracking=True
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        tracking=True,
        domain=[('categ_id.type', '=', 'muqeem_expenses')]
    )
    iqama_period = fields.Selection([
        ('3month', '3 Months'),
        ('6month', '6 Months'),
        ('9month', '9 Months'),
        ('1year', '1 Year'),
    ], string='Iqama Period', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company.id,
        tracking=True
    )
    state = fields.Selection([
        ('new', 'New'),
        ('confirmed', 'Confirmed'),

        ('paid', 'Paid'),
    ], string='Status', default='new', tracking=True)
    expense_ids = fields.One2many(
        'document.renew.expense',
        'batch_id',
        string='Expenses'
    )
    expense_count = fields.Integer(
        string='Expenses Count',
        compute='_compute_expense_count'
    )
    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_total_amount',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    @api.depends('expense_ids')
    def _compute_expense_count(self):
        for batch in self:
            batch.expense_count = len(batch.expense_ids)

    @api.depends('expense_ids.total_amount')
    def _compute_total_amount(self):
        for batch in self:
            batch.total_amount = sum(batch.expense_ids.mapped('total_amount'))

    def action_open_expenses(self):
        return {
            'name': _('Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'document.renew.expense',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {'default_batch_id': self.id}
        }

    def action_generate_expenses(self):
        """Open wizard to generate expenses for this batch"""
        self.ensure_one()
        return {
            'name': _('Generate Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'muqeem.generate.expense.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_batch_id': self.id,
                'default_product_id': self.product_id.id,
                'default_iqama_period': self.iqama_period,
                'default_date': self.date,
            }
        }

    def action_confirm(self):
        for batch in self:
            if not batch.expense_ids:
                raise ValidationError(_('You cannot confirm a batch without expenses.'))
            batch.write({'state': 'confirmed'})



    def action_mark_paid(self):
        for batch in self:
            batch.write({'state': 'paid'})

            for expense in batch.expense_ids:
                if expense.state == 'payment':
                    expense.write({'state': 'done'})
                    expense.paid_by = self.env.user.name

    def action_reset_to_new(self):
        for batch in self:
            batch.write({'state': 'new'})

    def action_create_expense_transactions(self):
        self.ensure_one()

        if not self.expense_ids:
            raise ValidationError(_('No expenses found in this batch.'))

        # Get default general journal
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not journal:
            raise ValidationError(_('No general journal found for company %s.') % self.company_id.name)

        # Collect all expense lines
        detail_lines = []
        for expense in self.expense_ids:
            for line in expense.expense_line_ids:
                product = line.product_id
                expense_account = product.property_account_expense_id
                if not expense_account:
                    expense_account = product.categ_id.property_account_expense_categ_id
                if not expense_account:
                    raise ValidationError(
                        _('Product "%s" does not have an Expense Account configured.') % product.name
                    )

                from datetime import timedelta
                from odoo.addons.saddad.models.document_renew_expense import set_period
                iqama_expiry = expense.iqama_expiry_date
                period_str = line.period
                period_days = set_period(int(period_str[0])) if period_str else 0
                start_date = iqama_expiry or line.date
                end_date = (start_date + timedelta(days=period_days)) if period_days else start_date

                analytic_dist = None
                if line.analytic_account_id:
                    analytic_dist = {str(line.analytic_account_id.id): 100}

                detail_lines.append((0, 0, {
                    'description': line.product_id.name,
                    'employee_id': line.expense_id.employee_id.employee_id.id if line.expense_id.employee_id and line.expense_id.employee_id.employee_id else False,
                    'operating_unit_id': line.expense_id.operating_unit_id.id if line.expense_id.operating_unit_id else False,
                    'prepaid_expense_account_id': expense_account.id,
                    'expense_account_id': expense_account.id,
                    'analytic_distribution': analytic_dist,
                    'start_date': start_date,
                    'end_date': end_date,
                    'quantity': line.quantity,
                    'price_unit': line.unit_price,
                }))

        if not detail_lines:
            raise ValidationError(_('No expense lines found in batch expenses.'))

        # Create expense transaction
        transaction = self.env['account.expense.transaction'].create({
            'date': self.date,
            'reference': self.name,
            'expense_nature': 'accrual',
            'amortization_method': 'on_time',
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            'expense_detail_ids': detail_lines,
        })

        # Mark lines as exported
        for expense in self.expense_ids:
            expense.expense_line_ids.write({'exported_to_transaction': True})

        # Open created transaction
        return {
            'type': 'ir.actions.act_window',
            'name': _('Expense Transaction'),
            'res_model': 'account.expense.transaction',
            'res_id': transaction.id,
            'view_mode': 'form',
            'target': 'current',
        }


