# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError
import base64
import io

ACCRUED_SALARY_CODE = '213001'


class FullEmployeeStatementWizard(models.TransientModel):
    _name = 'full.employee.statement.wizard'
    _description = 'Full Employee Statement Wizard'

    account_ids = fields.Many2many(
        comodel_name='account.account',
        string='Accounts',
        required=True,
        default=lambda self: self.env['account.account'].search(
            [('code', '=', ACCRUED_SALARY_CODE)], limit=1,
        ),
    )
    date_from = fields.Date(
        string='From Date',
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(month=1, day=1),
    )
    date_to = fields.Date(
        string='To Date',
        required=True,
        default=fields.Date.context_today,
    )
    line_ids = fields.One2many(
        comodel_name='full.employee.statement.line',
        inverse_name='wizard_id',
        string='Statement Lines',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    total_debit = fields.Monetary(compute='_compute_totals', currency_field='currency_id')
    total_credit = fields.Monetary(compute='_compute_totals', currency_field='currency_id')
    total_balance = fields.Monetary(compute='_compute_totals', currency_field='currency_id')

    @api.depends('line_ids.debit', 'line_ids.credit', 'line_ids.balance')
    def _compute_totals(self):
        for wizard in self:
            wizard.total_debit = sum(wizard.line_ids.mapped('debit'))
            wizard.total_credit = sum(wizard.line_ids.mapped('credit'))
            wizard.total_balance = sum(wizard.line_ids.mapped('balance'))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                raise UserError(_('The start date cannot be later than the end date.'))

    def _base_domain(self):
        """Filters that apply to every query in this report."""
        return [
            ('account_id', 'in', self.account_ids.ids),
            ('employee_id', '!=', False),
            ('parent_state', '=', 'posted'),
            ('display_type', 'not in', ('line_section', 'line_note')),
        ]

    def action_generate_statement(self):
        """Build one row per employee per account, then reopen the result view."""
        self.ensure_one()
        self.line_ids.unlink()

        # Movements inside the selected period
        period_groups = self.env['account.move.line'].read_group(
            domain=self._base_domain() + [
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
            ],
            fields=['debit:sum', 'credit:sum'],
            groupby=['employee_id', 'account_id'],
            lazy=False,
        )

        # Everything before the period start
        opening_groups = self.env['account.move.line'].read_group(
            domain=self._base_domain() + [('date', '<', self.date_from)],
            fields=['balance:sum'],
            groupby=['employee_id', 'account_id'],
            lazy=False,
        )

        period_by_key = {
            (g['employee_id'][0], g['account_id'][0]): g for g in period_groups
        }
        opening_by_key = {
            (g['employee_id'][0], g['account_id'][0]): g['balance']
            for g in opening_groups
        }

        keys = set(period_by_key) | set(opening_by_key)

        employees = self.env['hr.employee'].browse({key[0] for key in keys})
        employee_codes = {emp.id: emp.employee_code or '' for emp in employees}

        line_vals = []
        for employee_id, account_id in sorted(
            keys, key=lambda key: (employee_codes.get(key[0], ''), key[1])
        ):
            group = period_by_key.get((employee_id, account_id), {})
            debit = group.get('debit', 0.0)
            credit = group.get('credit', 0.0)
            opening = opening_by_key.get((employee_id, account_id), 0.0)
            net_diff = debit - credit
            line_vals.append({
                'wizard_id': self.id,
                'employee_id': employee_id,
                'employee_code': employee_codes.get(employee_id, ''),
                'account_id': account_id,
                'opening_balance': opening,
                'debit': debit,
                'credit': credit,
                'net_diff': net_diff,
                'balance': opening + net_diff,
            })

        if line_vals:
            self.env['full.employee.statement.line'].create(line_vals)

        return {
            'name': _('Full Employee Statement'),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'account_ext.full_employee_statement_wizard_view_result_form'
            ).id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_print_pdf(self):
        """Placeholder — button is present but does nothing yet."""
        self.ensure_one()
        return True

    def action_export_excel(self):
        """Build the xlsx and hand it to the browser as a download."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('There is nothing to export. Generate the statement first.'))

        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('The xlsxwriter library is required for Excel export.'))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Employee Statement Report')

        title_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'center', 'valign': 'vcenter',
        })
        subtitle_format = workbook.add_format({
            'bold': True, 'font_size': 12, 'align': 'center',
        })
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
        })
        text_format = workbook.add_format({'border': 1, 'align': 'left'})
        money_format = workbook.add_format({
            'num_format': '#,##0.00', 'border': 1, 'align': 'right',
        })
        total_label_format = workbook.add_format({
            'bold': True, 'bg_color': '#D9E2F3', 'border': 1, 'align': 'right',
        })
        total_format = workbook.add_format({
            'bold': True, 'bg_color': '#D9E2F3', 'num_format': '#,##0.00',
            'border': 1, 'align': 'right',
        })

        sheet.set_column('A:A', 16)
        sheet.set_column('B:B', 30)
        sheet.set_column('C:G', 18)

        sheet.merge_range('A1:G1', self.env.company.name, title_format)
        sheet.merge_range('A2:G2', 'Full Employee Statement', subtitle_format)
        sheet.merge_range(
            'A3:G3',
            'Period: %s to %s' % (self.date_from, self.date_to),
            subtitle_format,
        )

        row = 4
        headers = [
            'Employee ID', 'Account', 'Opening Balance', 'Debit',
            'Credit', 'Net Diff.', 'Balance',
        ]
        for col, header in enumerate(headers):
            sheet.write(row, col, header, header_format)
        row += 1

        for line in self.line_ids:
            sheet.write(row, 0, line.employee_code or '', text_format)
            sheet.write(row, 1, line.account_id.display_name or '', text_format)
            sheet.write(row, 2, line.opening_balance, money_format)
            sheet.write(row, 3, line.debit, money_format)
            sheet.write(row, 4, line.credit, money_format)
            sheet.write(row, 5, line.net_diff, money_format)
            sheet.write(row, 6, line.balance, money_format)
            row += 1

        sheet.write(row, 0, 'TOTALS:', total_label_format)
        sheet.write(row, 1, '', total_label_format)
        sheet.write(row, 2, sum(self.line_ids.mapped('opening_balance')), total_format)
        sheet.write(row, 3, self.total_debit, total_format)
        sheet.write(row, 4, self.total_credit, total_format)
        sheet.write(row, 5, sum(self.line_ids.mapped('net_diff')), total_format)
        sheet.write(row, 6, self.total_balance, total_format)

        sheet.freeze_panes(5, 0)

        workbook.close()
        output.seek(0)

        filename = 'full_employee_statement_%s_%s.xlsx' % (
            self.date_from, self.date_to,
        )
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.'
                        'spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }


class FullEmployeeStatementLine(models.TransientModel):
    _name = 'full.employee.statement.line'
    _description = 'Full Employee Statement Line'
    _order = 'employee_code, account_id'

    wizard_id = fields.Many2one(
        comodel_name='full.employee.statement.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one('hr.employee', string='Employee')
    employee_code = fields.Char(string='Employee ID')
    account_id = fields.Many2one('account.account', string='Account')
    currency_id = fields.Many2one(related='wizard_id.currency_id')
    opening_balance = fields.Monetary(currency_field='currency_id')
    debit = fields.Monetary(currency_field='currency_id')
    credit = fields.Monetary(currency_field='currency_id')
    net_diff = fields.Monetary(string='Net Diff.', currency_field='currency_id')
    balance = fields.Monetary(currency_field='currency_id')