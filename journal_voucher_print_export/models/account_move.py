# -*- coding: utf-8 -*-
# Author: Fakhraddin A. Sa'ad

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import xlsxwriter
import base64
from io import BytesIO
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    def action_print_voucher(self):
        """
        Print journal voucher as PDF using QWeb template
        Works for both draft and posted entries
        """
        self.ensure_one()
        
        if self.move_type not in ('entry',):
            raise UserError(_('This function is only available for Journal Entries.'))
        
        # Check balance before printing
        total_debit = sum(self.line_ids.mapped('debit'))
        total_credit = sum(self.line_ids.mapped('credit'))
        balance_diff = abs(total_debit - total_credit)
        
        # Allow for small rounding differences (0.01 SR tolerance)
        if balance_diff > 0.01:
            raise UserError(_(
                'Journal Entry is NOT Balanced!\n\n'
                'Total Debit: %s\n'
                'Total Credit: %s\n'
                'Difference: %s\n\n'
                'Please balance the entry before printing.'
            ) % (
                '{:,.2f}'.format(total_debit),
                '{:,.2f}'.format(total_credit),
                '{:,.2f}'.format(balance_diff)
            ))
        
        # For large entries, suggest Excel export
        line_count = len(self.line_ids)
        if line_count > 1000:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Large Journal Entry'),
                    'message': _(
                        'This journal entry has %s lines. '
                        'For better performance, consider using "Export to Excel" instead.'
                    ) % line_count,
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        # Print using QWeb template
        return self.env.ref('journal_voucher_print_export.action_report_journal_entry_voucher').report_action(self)
    
    def action_smart_print(self):
        """
        Smart print method that automatically chooses:
        - PDF for journal entries with ≤1000 lines
        - Excel for journal entries with >1000 lines
        """
        self.ensure_one()
        
        if self.move_type not in ('entry',):
            raise UserError(_('This function is only available for Journal Entries.'))
        
        line_count = len(self.line_ids)
        
        # If more than 1000 lines, force Excel export
        if line_count > 1000:
            # Show notification
            message = _(
                'This journal entry has %s lines. '
                'Exporting to Excel for better performance and reliability.'
            ) % line_count
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Large Journal Entry'),
                    'message': message,
                    'type': 'info',
                    'sticky': False,
                    'next': self.export_voucher_excel(),
                }
            }
        
        # Otherwise use PDF
        return self.action_print_voucher()
    
    def export_voucher_excel(self):
        """
        Export journal voucher to professionally formatted Excel file
        Handles large datasets (5000+ lines) efficiently with chunk processing
        
        Author: Fakhraddin A. Sa'ad
        """
        self.ensure_one()
        
        # Check if entry is balanced before export
        total_debit = sum(self.line_ids.mapped('debit'))
        total_credit = sum(self.line_ids.mapped('credit'))
        balance_diff = abs(total_debit - total_credit)
        
        # Allow for small rounding differences (0.01 SR tolerance)
        if balance_diff > 0.01:
            raise UserError(_(
                'Journal Entry is NOT Balanced!\n\n'
                'Total Debit: %s\n'
                'Total Credit: %s\n'
                'Difference: %s\n\n'
                'Please balance the entry before exporting.\n'
                'TIP: If this entry is in DRAFT state, posting it will automatically add balancing lines.'
            ) % (
                '{:,.2f}'.format(total_debit),
                '{:,.2f}'.format(total_credit),
                '{:,.2f}'.format(balance_diff)
            ))
        
        # Show warning if exporting draft entry
        if self.state != 'posted':
            _logger.warning(f'Exporting DRAFT journal entry {self.name}. Entry may be incomplete.')
        
        try:
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('Journal Voucher')
            
            # ==================== FORMATS ====================
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 16,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#4F81BD',
                'font_color': 'white',
                'border': 1
            })
            
            header_info_label_format = workbook.add_format({
                'bold': True,
                'font_size': 11,
                'bg_color': '#D3D3D3',
                'border': 1
            })
            
            header_info_value_format = workbook.add_format({
                'font_size': 11,
                'border': 1
            })
            
            # Add warning format for draft entries
            header_warning_format = workbook.add_format({
                'font_size': 11,
                'border': 1,
                'bg_color': '#FFC7CE',  # Light red background
                'font_color': '#9C0006'  # Dark red text
            })
            
            column_header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4F81BD',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True
            })
            
            data_format = workbook.add_format({
                'border': 1,
                'valign': 'top',
                'text_wrap': True
            })
            
            money_format = workbook.add_format({
                'num_format': '#,##0.00',
                'border': 1
            })
            
            total_format = workbook.add_format({
                'bold': True,
                'bg_color': '#FFC000',
                'border': 2,
                'num_format': '#,##0.00'
            })
            
            total_label_format = workbook.add_format({
                'bold': True,
                'bg_color': '#FFC000',
                'border': 2,
                'align': 'right'
            })
            
            # Balance check format - Green if balanced
            balance_check_format = workbook.add_format({
                'bold': True,
                'bg_color': '#92D050',
                'border': 1,
                'num_format': '#,##0.00'
            })
            
            # ==================== TITLE ====================
            sheet.merge_range('A1:H1', 'JOURNAL VOUCHER', title_format)
            sheet.set_row(0, 30)
            
            # ==================== HEADER INFORMATION ====================
            row = 2
            
            # Company
            sheet.write(row, 0, 'Company:', header_info_label_format)
            sheet.merge_range(row, 1, row, 3, self.company_id.name, header_info_value_format)
            
            # Journal Entry Number
            row += 1
            sheet.write(row, 0, 'Journal Entry:', header_info_label_format)
            entry_display = self.name if self.name else 'Draft'
            sheet.merge_range(row, 1, row, 3, entry_display, header_info_value_format)
            
            # Date
            row += 1
            sheet.write(row, 0, 'Date:', header_info_label_format)
            sheet.write(row, 1, self.date.strftime('%d/%m/%Y') if self.date else '', header_info_value_format)
            
            # Journal
            row += 1
            sheet.write(row, 0, 'Journal:', header_info_label_format)
            sheet.write(row, 1, self.journal_id.name or '', header_info_value_format)
            
            # Reference (if exists)
            if self.ref:
                row += 1
                sheet.write(row, 0, 'Reference:', header_info_label_format)
                sheet.merge_range(row, 1, row, 3, self.ref, header_info_value_format)
            
            # Total Lines Count
            row += 1
            sheet.write(row, 0, 'Total Lines:', header_info_label_format)
            sheet.write(row, 1, len(self.line_ids), header_info_value_format)
            
            # State - with warning if draft
            row += 1
            sheet.write(row, 0, 'Status:', header_info_label_format)
            status_text = dict(self._fields['state'].selection).get(self.state, self.state)
            
            if self.state == 'posted':
                sheet.write(row, 1, status_text.upper(), header_info_value_format)
            else:
                # Highlight draft/cancelled status in red
                sheet.write(row, 1, status_text.upper(), header_warning_format)
            
            # Blank row
            row += 2
            
            # ==================== COLUMN HEADERS ====================
            headers = [
                'Account Code',
                'Account Name', 
                'Partner',
                'Employee',
                'Label',
                'Debit (SR)',
                'Credit (SR)',
                'Analytic Account'
            ]
            
            for col, header in enumerate(headers):
                sheet.write(row, col, header, column_header_format)
            
            sheet.set_row(row, 35)
            
            # ==================== DATA ROWS ====================
            row += 1  # Move to first data row
            data_start_row = row  # This is now the first data row
            chunk_size = 500
            total_lines = len(self.line_ids)
            
            _logger.info(f'Exporting {total_lines} journal lines to Excel in chunks of {chunk_size}')
            
            # Process in chunks for memory efficiency
            for i in range(0, total_lines, chunk_size):
                chunk = self.line_ids[i:i+chunk_size]
                for line in chunk:
                    # Get analytic account name (Odoo 18 compatible)
                    # In Odoo 18, analytic_distribution is a JSON field: {"analytic_account_id": percentage}
                    analytic_name = ''
                    if line.analytic_distribution:
                        try:
                            # Extract analytic account IDs from the distribution dict
                            analytic_ids = [int(k) for k in line.analytic_distribution.keys()]
                            if analytic_ids:
                                # Fetch all analytic accounts at once
                                analytic_accounts = self.env['account.analytic.account'].browse(analytic_ids)
                                # Join multiple analytic accounts with comma
                                analytic_name = ', '.join(analytic_accounts.mapped('name'))
                        except Exception as e:
                            _logger.warning(f'Error processing analytic distribution for line {line.id}: {str(e)}')
                            pass
                    
                    sheet.write(row, 0, line.account_id.code or '', data_format)
                    sheet.write(row, 1, line.account_id.name or '', data_format)
                    sheet.write(row, 2, line.partner_id.name or '', data_format)
                    sheet.write(row, 3, line.employee_id.name or '', data_format)
                    sheet.write(row, 4, line.name or '', data_format)
                    sheet.write(row, 5, line.debit or 0, money_format)
                    sheet.write(row, 6, line.credit or 0, money_format)
                    sheet.write(row, 7, analytic_name, data_format)
                    row += 1
                
                _logger.info(f'Processed {min(i + chunk_size, total_lines)}/{total_lines} lines')
            
            data_end_row = row
            
            # ==================== TOTALS ROW ====================
            sheet.write(row, 0, '', total_label_format)
            sheet.write(row, 1, '', total_label_format)
            sheet.write(row, 2, '', total_label_format)
            sheet.write(row, 3, '', total_label_format)
            sheet.write(row, 4, 'TOTAL', total_label_format)
            sheet.write_formula(row, 5, f'=SUM(F{data_start_row}:F{data_end_row})', total_format)
            sheet.write_formula(row, 6, f'=SUM(G{data_start_row}:G{data_end_row})', total_format)
            sheet.write(row, 7, '', total_label_format)
            
            sheet.set_row(row, 25)
            total_row = row
            
            # ==================== BALANCE CHECK ====================
            row += 2
            sheet.write(row, 3, 'Balance Check (Debit - Credit):', header_info_label_format)
            sheet.write_formula(row, 4, f'=F{total_row}-G{total_row}', balance_check_format)
            sheet.write(row, 5, 'Should be 0.00', header_info_value_format)
            
            # ==================== COLUMN WIDTHS ====================
            sheet.set_column('A:A', 15)  # Account Code
            sheet.set_column('B:B', 35)  # Account Name
            sheet.set_column('C:C', 25)  # Partner
            sheet.set_column('D:D', 25)  # Employee
            sheet.set_column('E:E', 45)  # Label
            sheet.set_column('F:F', 16)  # Debit
            sheet.set_column('G:G', 16)  # Credit
            sheet.set_column('H:H', 25)  # Analytic
            
            # ==================== FREEZE PANES ====================
            # Freeze header row so it stays visible when scrolling
            sheet.freeze_panes(data_start_row, 0)
            
            # ==================== FINALIZE ====================
            workbook.close()
            output.seek(0)
            
            # Create attachment with safe filename handling
            # Handle draft entries that don't have a name yet
            if self.name:
                entry_name = self.name.replace("/", "_")
            else:
                entry_name = f"Draft_{self.id}"
            
            filename = f'Journal_Voucher_{entry_name}.xlsx'
            
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(output.read()),
                'res_model': 'account.move',
                'res_id': self.id,
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            })
            
            _logger.info(f'Successfully created Excel export: {filename}')
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }
            
        except Exception as e:
            _logger.error(f'Error exporting journal voucher to Excel: {str(e)}')
            raise UserError(_(
                'Error exporting to Excel: %s\n\n'
                'Please contact your system administrator.'
            ) % str(e))
