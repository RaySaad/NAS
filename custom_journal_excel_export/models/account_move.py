# -*- coding: utf-8 -*-
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
        
        # Otherwise use standard PDF report (you can replace this with your custom report)
        return self.env.ref('account.account_invoices').report_action(self)
    
    def export_voucher_excel(self):
        """
        Export journal voucher to professionally formatted Excel file
        Handles large datasets (5000+ lines) efficiently with chunk processing
        """
        self.ensure_one()
        
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
            sheet.merge_range(row, 1, row, 3, self.name or '', header_info_value_format)
            
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
            
            # State
            row += 1
            sheet.write(row, 0, 'Status:', header_info_label_format)
            status_text = dict(self._fields['state'].selection).get(self.state, self.state)
            sheet.write(row, 1, status_text.upper(), header_info_value_format)
            
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
            data_start_row = row + 1
            
            # ==================== DATA ROWS ====================
            row += 1
            chunk_size = 500
            total_lines = len(self.line_ids)
            
            _logger.info(f'Exporting {total_lines} journal lines to Excel in chunks of {chunk_size}')
            
            # Process in chunks for memory efficiency
            for i in range(0, total_lines, chunk_size):
                chunk = self.line_ids[i:i+chunk_size]
                for line in chunk:
                    sheet.write(row, 0, line.account_id.code or '', data_format)
                    sheet.write(row, 1, line.account_id.name or '', data_format)
                    sheet.write(row, 2, line.partner_id.name or '', data_format)
                    sheet.write(row, 3, line.employee_id.name or '', data_format)
                    sheet.write(row, 4, line.name or '', data_format)
                    sheet.write(row, 5, line.debit or 0, money_format)
                    sheet.write(row, 6, line.credit or 0, money_format)
                    sheet.write(row, 7, line.analytic_account_id.name or '', data_format)
                    row += 1
                
                _logger.info(f'Processed {min(i + chunk_size, total_lines)}/{total_lines} lines')
            
            data_end_row = row - 1
            
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
            
            # Create attachment
            filename = f'Journal_Voucher_{self.name.replace("/", "_")}.xlsx'
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
