# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import io
import base64
from datetime import datetime


class EmployeeStatementWizard(models.TransientModel):
    _name = 'employee.statement.wizard'
    _description = 'Employee Financial Statement Wizard'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True
    )
    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date')
    linking_method = fields.Selection([
        ('partner', 'Partner Based (partner_id)'),
        ('employee', 'Employee Field (employee_id)'),
        ('both', 'Both Methods')
    ], string='Linking Method', default='both', required=True,
       help='Select how employees are linked to journal entries')
    group_by_account = fields.Boolean(string='Group by Account', default=False)
    
    # For storing generated report data
    line_ids = fields.One2many(
        'employee.statement.line',
        'wizard_id',
        string='Statement Lines'
    )
    
    # Summary fields
    total_debit = fields.Monetary(
        string='Total Debit',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    total_credit = fields.Monetary(
        string='Total Credit',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    balance = fields.Monetary(
        string='Balance',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    @api.depends('line_ids.debit', 'line_ids.credit')
    def _compute_totals(self):
        for wizard in self:
            wizard.total_debit = sum(wizard.line_ids.mapped('debit'))
            wizard.total_credit = sum(wizard.line_ids.mapped('credit'))
            wizard.balance = wizard.total_debit - wizard.total_credit

    def _get_domain(self):
        """Build domain based on linking method"""
        self.ensure_one()
        domain = [('parent_state', '=', 'posted')]
        
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        
        employee = self.employee_id
        
        if self.linking_method == 'partner':
            # Get partner from employee (user's partner or private partner if available)
            partner_ids = []
            if employee.user_id and employee.user_id.partner_id:
                partner_ids.append(employee.user_id.partner_id.id)
            # Check if private_address field exists (requires hr_contract)
            if hasattr(employee, 'address_home_id') and employee.address_home_id:
                partner_ids.append(employee.address_home_id.id)
            # Also check work_contact_id (standard in Odoo 18)
            if hasattr(employee, 'work_contact_id') and employee.work_contact_id:
                partner_ids.append(employee.work_contact_id.id)
            if not partner_ids:
                raise UserError(_('Employee %s has no linked partner. Please ensure the employee has a related user or contact.') % employee.name)
            domain.append(('partner_id', 'in', list(set(partner_ids))))
            
        elif self.linking_method == 'employee':
            domain.append(('employee_id', '=', employee.id))
            
        else:  # both
            partner_ids = []
            if employee.user_id and employee.user_id.partner_id:
                partner_ids.append(employee.user_id.partner_id.id)
            if hasattr(employee, 'address_home_id') and employee.address_home_id:
                partner_ids.append(employee.address_home_id.id)
            if hasattr(employee, 'work_contact_id') and employee.work_contact_id:
                partner_ids.append(employee.work_contact_id.id)
            
            if partner_ids:
                domain.append('|')
                domain.append(('partner_id', 'in', list(set(partner_ids))))
                domain.append(('employee_id', '=', employee.id))
            else:
                domain.append(('employee_id', '=', employee.id))
        
        return domain

    def action_generate_statement(self):
        """Generate the statement lines"""
        self.ensure_one()
        
        # Clear existing lines
        self.line_ids.unlink()
        
        domain = self._get_domain()
        move_lines = self.env['account.move.line'].search(domain, order='date asc, id asc')
        
        if not move_lines:
            raise UserError(_('No journal entries found for the selected criteria.'))
        
        # Create statement lines with running balance
        running_balance = 0.0
        line_vals = []
        
        for ml in move_lines:
            running_balance += ml.debit - ml.credit
            line_vals.append({
                'wizard_id': self.id,
                'date': ml.date,
                'move_id': ml.move_id.id,
                'move_line_id': ml.id,
                'journal_id': ml.journal_id.id,
                'account_id': ml.account_id.id,
                'label': ml.name or ml.move_id.name,
                'debit': ml.debit,
                'credit': ml.credit,
                'running_balance': running_balance,
            })
        
        self.env['employee.statement.line'].create(line_vals)
        
        # Return action to show the statement
        return {
            'name': _('Employee Statement: %s') % self.employee_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'employee.statement.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('employee_financial_statement.view_employee_statement_result_form').id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_view_lines(self):
        """Open statement lines in a list view"""
        self.ensure_one()
        
        action = {
            'name': _('Statement Lines: %s') % self.employee_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'employee.statement.line',
            'view_mode': 'list',
            'domain': [('wizard_id', '=', self.id)],
            'context': {
                'group_by': 'account_id' if self.group_by_account else False,
            },
        }
        return action

    def action_print_pdf(self):
        """Generate PDF report"""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Please generate the statement first.'))
        
        return self.env.ref('employee_financial_statement.action_report_employee_statement').report_action(self)

    def action_export_excel(self):
        """Export to Excel"""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Please generate the statement first.'))
        
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('xlsxwriter library is required for Excel export. Please install it.'))
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Employee Statement')
        
        # Formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter',
        })
        subtitle_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
        })
        date_format = workbook.add_format({
            'num_format': 'yyyy-mm-dd',
            'border': 1,
            'align': 'center',
        })
        money_format = workbook.add_format({
            'num_format': '#,##0.00',
            'border': 1,
            'align': 'right',
        })
        text_format = workbook.add_format({
            'border': 1,
            'align': 'left',
        })
        total_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E2F3',
            'num_format': '#,##0.00',
            'border': 1,
            'align': 'right',
        })
        total_label_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E2F3',
            'border': 1,
            'align': 'right',
        })
        
        # Set column widths
        worksheet.set_column('A:A', 12)  # Date
        worksheet.set_column('B:B', 18)  # JV Reference
        worksheet.set_column('C:C', 15)  # Journal
        worksheet.set_column('D:D', 25)  # Account
        worksheet.set_column('E:E', 35)  # Description
        worksheet.set_column('F:F', 15)  # Debit
        worksheet.set_column('G:G', 15)  # Credit
        worksheet.set_column('H:H', 15)  # Running Balance
        
        # Company Header
        company = self.env.company
        row = 0
        worksheet.merge_range('A1:H1', company.name, title_format)
        row = 1
        
        # Report Title
        worksheet.merge_range('A2:H2', 'Employee Financial Statement', subtitle_format)
        row = 2
        
        # Employee and Date Info
        worksheet.merge_range('A3:H3', f'Employee: {self.employee_id.name}', subtitle_format)
        row = 3
        
        date_range = ''
        if self.date_from and self.date_to:
            date_range = f'Period: {self.date_from} to {self.date_to}'
        elif self.date_from:
            date_range = f'From: {self.date_from}'
        elif self.date_to:
            date_range = f'To: {self.date_to}'
        else:
            date_range = 'Period: All Time'
        worksheet.merge_range('A4:H4', date_range, subtitle_format)
        row = 5
        
        # Headers
        headers = ['Date', 'JV Reference', 'Journal', 'Account', 'Description', 'Debit', 'Credit', 'Running Balance']
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)
        row += 1
        
        # Data rows
        for line in self.line_ids:
            worksheet.write(row, 0, line.date, date_format)
            worksheet.write(row, 1, line.move_id.name or '', text_format)
            worksheet.write(row, 2, line.journal_id.name or '', text_format)
            worksheet.write(row, 3, line.account_id.display_name or '', text_format)
            worksheet.write(row, 4, line.label or '', text_format)
            worksheet.write(row, 5, line.debit, money_format)
            worksheet.write(row, 6, line.credit, money_format)
            worksheet.write(row, 7, line.running_balance, money_format)
            row += 1
        
        # Totals row
        worksheet.write(row, 4, 'TOTALS:', total_label_format)
        worksheet.write(row, 5, self.total_debit, total_format)
        worksheet.write(row, 6, self.total_credit, total_format)
        worksheet.write(row, 7, self.balance, total_format)
        
        workbook.close()
        output.seek(0)
        
        # Create attachment
        filename = f'employee_statement_{self.employee_id.name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def get_report_data(self):
        """Prepare data for PDF report"""
        self.ensure_one()
        
        lines_data = []
        grouped_data = {}
        
        for line in self.line_ids:
            line_dict = {
                'date': line.date,
                'move_name': line.move_id.name,
                'journal_name': line.journal_id.name,
                'account_name': line.account_id.display_name,
                'label': line.label,
                'debit': line.debit,
                'credit': line.credit,
                'running_balance': line.running_balance,
            }
            lines_data.append(line_dict)
            
            if self.group_by_account:
                account_key = line.account_id.display_name
                if account_key not in grouped_data:
                    grouped_data[account_key] = {
                        'account_name': account_key,
                        'lines': [],
                        'total_debit': 0,
                        'total_credit': 0,
                    }
                grouped_data[account_key]['lines'].append(line_dict)
                grouped_data[account_key]['total_debit'] += line.debit
                grouped_data[account_key]['total_credit'] += line.credit
        
        return {
            'wizard': self,
            'lines': lines_data,
            'grouped_data': grouped_data if self.group_by_account else None,
            'company': self.env.company,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'total_debit': self.total_debit,
            'total_credit': self.total_credit,
            'balance': self.balance,
        }


class EmployeeStatementLine(models.TransientModel):
    _name = 'employee.statement.line'
    _description = 'Employee Statement Line'
    _order = 'date asc, id asc'

    wizard_id = fields.Many2one(
        'employee.statement.wizard',
        string='Wizard',
        ondelete='cascade'
    )
    date = fields.Date(string='Date')
    move_id = fields.Many2one('account.move', string='Journal Entry')
    move_line_id = fields.Many2one('account.move.line', string='Journal Item')
    journal_id = fields.Many2one('account.journal', string='Journal')
    account_id = fields.Many2one('account.account', string='Account')
    label = fields.Char(string='Description')
    debit = fields.Monetary(string='Debit', currency_field='currency_id')
    credit = fields.Monetary(string='Credit', currency_field='currency_id')
    running_balance = fields.Monetary(string='Running Balance', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
