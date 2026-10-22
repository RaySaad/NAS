import base64
import binascii
import io
import re
import hashlib

from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.pdf import PdfReader
from .configuration import PERIODS
from .qiwa_pdf import parse_qiwa_text


class QiwaImport(models.TransientModel):
    _name = 'saddad.qiwa.import'
    _description = 'Qiwa PDF Assistance'

    batch_id = fields.Many2one('saddad.qiwa.batch', required=True, readonly=True)
    pdf_file = fields.Binary(string='Qiwa PDF', required=True, attachment=False)
    filename = fields.Char()
    extracted_text = fields.Text(readonly=True)
    reference = fields.Char(string='Qiwa SADAD Reference')
    invoice_number = fields.Char(string='Qiwa Invoice Number')
    document_digest = fields.Char(readonly=True)
    detected_currency = fields.Char(string='Detected Currency', readonly=True)
    issue_date = fields.Date(string='Reference Issue Date')
    due_date = fields.Date(string='Reference Due Date')
    document_payment_status = fields.Selection([('unknown', 'Not Specified'), ('unpaid', 'Unpaid in Qiwa'), ('paid', 'Paid in Qiwa')], default='unknown', required=True)
    document_payment_date = fields.Date(string='Qiwa Payment Date')
    document_export_date = fields.Date(string='PDF Export Date')
    document_total = fields.Monetary(string='PDF Total', readonly=True)
    has_document_total = fields.Boolean(readonly=True)
    currency_id = fields.Many2one(related='batch_id.currency_id')
    import_summary = fields.Text(string='Extraction Notes', readonly=True)
    period = fields.Selection(PERIODS, string='Renewal Period', required=True, default='3')
    line_ids = fields.One2many('saddad.qiwa.import.line', 'wizard_id', string='Employee Matches')
    reviewed = fields.Boolean(string='I checked the document, employee matches, dates and amounts')

    def _pdf_bytes(self):
        self.ensure_one()
        if not self.pdf_file or len(self.pdf_file) > 14 * 1024 * 1024:
            raise UserError(_('Upload a PDF no larger than 10 MB.'))
        try:
            data = base64.b64decode(self.pdf_file, validate=True)
        except (ValueError, binascii.Error):
            raise UserError(_('The uploaded file is not a valid PDF.'))
        if len(data) > 10 * 1024 * 1024 or not data.startswith(b'%PDF-'):
            raise UserError(_('Upload a valid PDF no larger than 10 MB.'))
        return data

    def action_extract(self):
        self.ensure_one()
        self.batch_id._draft()
        data = self._pdf_bytes()
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted or len(reader.pages) > 40:
                raise UserError(_('Use an unencrypted PDF with no more than 40 pages.'))
            text = '\n'.join((page.extract_text() or '') for page in reader.pages)
        except UserError:
            raise
        except Exception:
            raise UserError(_('The PDF could not be read. Use a text PDF or enter the batch manually.'))
        if not text.strip():
            raise UserError(_('No text was found. Scanned PDFs require manual entry; OCR is not included.'))
        if len(text) > 250000:
            raise UserError(_('The extracted document is too large. Split it into smaller PDFs.'))
        self._stage_text(text)
        self.document_digest = hashlib.sha256(data).hexdigest()
        return self._reopen()

    def _stage_text(self, text):
        """Stage document evidence; never approve a batch or record a payment."""
        self.ensure_one()
        parsed = parse_qiwa_text(text)
        ids = [row['identity'] for row in parsed['employees']]
        employees = self.env['hr.employee'].search([('company_id', '=', self.batch_id.company_id.id), ('identification_id', 'in', ids)])
        commands = [Command.clear()]
        for row in parsed['employees']:
            identity = row['identity']
            matches = employees.filtered(lambda e: e.identification_id == identity)
            values = {'employee_id': matches.id if len(matches) == 1 else False, 'source_identity': identity, 'period': row.get('period') or False}
            if 'amount' in row:
                values.update(amount_source='external', amount=row['amount'], permit_valid_until=row['permit_valid_until'],
                              external_reason=_('Extracted from Qiwa PDF; checked by user before applying.'))
            commands.append(Command.create(values))
        summary = _('Review the extracted fields against the original PDF. Arabic text in this PDF may not decode correctly; employee matching uses identification numbers.')
        if parsed['payment_status'] == 'paid':
            summary += '\n' + _('This document reports a completed Qiwa payment. No due date is inferred and no Saddad payment is recorded.')
        if parsed['payment_status'] == 'unknown':
            summary += '\n' + _('Payment status was not recognized. Select the document status and complete the relevant date manually.')
        self.write({'extracted_text': parsed['text'], 'line_ids': commands, 'reviewed': False,
                    'reference': parsed['reference'],
                    'invoice_number': parsed['invoice_number'],
                    'issue_date': parsed['issue_date'],
                    'due_date': parsed['due_date'],
                    'document_payment_status': parsed['payment_status'],
                    'document_payment_date': parsed['payment_date'],
                    'document_export_date': parsed['export_date'],
                    'document_total': parsed['document_total'] or 0,
                    'has_document_total': parsed['document_total'] is not False,
                    'import_summary': summary,
                    'detected_currency': 'SAR' if parsed['reference'] else False,
                    'period': parsed['period'] or self.period})

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def action_apply(self):
        self.ensure_one()
        self.batch_id._draft()
        if not self.reviewed or not self.extracted_text or not self.line_ids:
            raise UserError(_('Extract the PDF, select employee lines and check the review acknowledgement.'))
        if not self.reference or not self.issue_date:
            raise UserError(_('Enter the reference and dates from the document before applying.'))
        if self.document_payment_status == 'paid':
            if not self.document_payment_date or self.document_payment_date < self.issue_date or self.document_payment_date > fields.Date.context_today(self):
                raise ValidationError(_('Check the Qiwa payment date: it must be on or after issue and not in the future.'))
        elif not self.due_date:
            raise ValidationError(_('Enter the payment due date for an unpaid document.'))
        data = self._pdf_bytes()
        if hashlib.sha256(data).hexdigest() != self.document_digest:
            raise UserError(_('The PDF changed after extraction. Extract and review it again.'))
        batch = self.batch_id
        if self.detected_currency and batch.currency_id.name != self.detected_currency:
            raise ValidationError(_('The PDF amount is in SAR but the batch company uses another currency. No automatic conversion is performed.'))
        seen = set()
        commands = []
        for line in self.line_ids:
            mapping = self.env['saddad.service.mapping'].search([('company_id', '=', batch.company_id.id), ('service_type', '=', 'work_permit'), ('period', '=', line.period or self.period)], limit=1)
            if not mapping:
                raise UserError(_('Configure the work-permit mapping for the selected renewal period.'))
            if not line.employee_id:
                raise ValidationError(_('Select an employee for every detected identity, or remove the unmatched row.'))
            if line.source_identity and (line.employee_id.identification_id or '').strip() != line.source_identity:
                raise ValidationError(_('The selected employee does not match the detected identification number.'))
            if line.employee_id.id in seen:
                raise ValidationError(_('An employee may appear only once in a Qiwa batch.'))
            seen.add(line.employee_id.id)
            values = {'employee_id': line.employee_id.id, 'mapping_id': mapping.id, 'amount_source': line.amount_source,
                      'permit_valid_until': line.permit_valid_until}
            if line.amount_source == 'external':
                values.update(amount=line.amount, external_reason=line.external_reason)
            existing = batch.line_ids.filtered(lambda item: item.employee_id == line.employee_id)
            if existing:
                if existing.mapping_id != mapping:
                    raise ValidationError(_('The PDF period does not match the existing employee line. Correct the draft before importing.'))
                values.pop('employee_id')
                values.pop('mapping_id')
                if existing.ptr_line_id and values['amount_source'] == 'cost':
                    values.pop('amount_source')
                commands.append(Command.update(existing.id, values))
            else:
                commands.append(Command.create(values))
        # Validate the proposed result before writing anything: no partial import on failure.
        amounts = {line.employee_id.id: line.amount for line in batch.line_ids}
        for line in self.line_ids:
            existing = batch.line_ids.filtered(lambda item: item.employee_id == line.employee_id)
            amounts[line.employee_id.id] = line.amount if line.amount_source == 'external' else existing.amount if existing.ptr_line_id else line.suggested_cost
        if self.has_document_total and batch.currency_id.compare_amounts(sum(amounts.values()), self.document_total):
            raise ValidationError(_('The employee-line total does not match the PDF total. Resolve missing, extra or incorrect lines before applying.'))
        batch.write({'reference': self.reference, 'invoice_number': self.invoice_number, 'issue_date': self.issue_date, 'due_date': self.due_date,
                     'document_payment_status': self.document_payment_status, 'document_payment_date': self.document_payment_date,
                     'document_export_date': self.document_export_date, 'line_ids': commands})
        # Owned attachment: normal ACLs and batch access checks apply, no public sharing.
        self.env['ir.attachment'].create({'name': self.filename or 'Qiwa.pdf', 'type': 'binary', 'datas': base64.b64encode(data),
            'mimetype': 'application/pdf', 'res_model': batch._name, 'res_id': batch.id})
        batch.message_post(body=_('PDF-assisted employee lines added after user review. Amounts use the selected source.'))
        self.unlink()
        return {'type': 'ir.actions.act_window_close'}


class QiwaImportLine(models.TransientModel):
    _name = 'saddad.qiwa.import.line'
    _description = 'Qiwa PDF Employee Match'

    wizard_id = fields.Many2one('saddad.qiwa.import', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='wizard_id.batch_id.company_id')
    currency_id = fields.Many2one(related='wizard_id.batch_id.currency_id')
    source_identity = fields.Char(string='Detected Identification No.', readonly=True)
    employee_id = fields.Many2one('hr.employee')
    permit_valid_until = fields.Date(string='Work Permit Valid Until')
    period = fields.Selection(PERIODS, string='Line Period', help='Empty uses the wizard renewal period.')
    suggested_cost = fields.Monetary(string='Product Cost Suggestion', compute='_compute_suggested_cost')
    amount_source = fields.Selection([('cost', 'Product Cost'), ('external', 'External Amount')], required=True, default='cost')
    amount = fields.Monetary(string='External Amount')
    external_reason = fields.Char(string='External Amount Explanation')

    @api.depends('period', 'wizard_id.period', 'company_id')
    def _compute_suggested_cost(self):
        for line in self:
            mapping = self.env['saddad.service.mapping'].search([('company_id', '=', line.company_id.id), ('service_type', '=', 'work_permit'), ('period', '=', line.period or line.wizard_id.period)], limit=1)
            line.suggested_cost = mapping.product_id.with_company(line.company_id).standard_price if mapping else 0
