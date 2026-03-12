# -*- coding: utf-8 -*-
import base64
import io
import zipfile

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PrintSeparatePdfWizard(models.TransientModel):
    _name = 'account.move.print.separate.pdf.wizard'
    _description = 'Print Journal Entries as Separate PDFs'

    move_ids = fields.Many2many(comodel_name='account.move', string='Journal Entries')
    pdf_file = fields.Binary(string='PDF File', readonly=True)
    pdf_filename = fields.Char(string='Filename', readonly=True)

    @api.model
    def action_print_separate(self, active_ids):
        if not active_ids:
            raise UserError(_('No Journal Entries selected.'))

        report = self.env.ref(
            'bi_print_journal_entries.journal_entry_report_id',
            raise_if_not_found=False
        )
        if not report:
            raise UserError(_('Could not find the Journal Entry report.'))

        moves = self.env['account.move'].browse(active_ids)

        # Single record: download PDF directly
        if len(moves) == 1:
            move = moves[0]
            pdf_content, _ = report._render_qweb_pdf(
                report_ref=report.id,
                res_ids=[move.id],
            )
            safe_name = (move.name or str(move.id)).replace('/', '-')
            filename = f'Journal_Entry_Report_{safe_name}.pdf'
            record = self.create({
                'move_ids': [(6, 0, [move.id])],
                'pdf_file': base64.b64encode(pdf_content),
                'pdf_filename': filename,
            })
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/account.move.print.separate.pdf.wizard/{record.id}/pdf_file/{filename}?download=true',
                'target': 'self',
            }

        # Multiple records: bundle all PDFs into a single ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zip_file:
            used_names = {}
            for move in moves:
                pdf_content, _ = report._render_qweb_pdf(
                    report_ref=report.id,
                    res_ids=[move.id],
                )
                safe_name = (move.name or str(move.id)).replace('/', '-')
                pdf_filename = f'Journal_Entry_Report_{safe_name}.pdf'

                # Avoid duplicate filenames inside the ZIP
                if pdf_filename in used_names:
                    used_names[pdf_filename] += 1
                    base, ext = pdf_filename.rsplit('.', 1)
                    pdf_filename = f'{base}_{used_names[pdf_filename]}.{ext}'
                else:
                    used_names[pdf_filename] = 0

                zip_file.writestr(pdf_filename, pdf_content)

        zip_data = base64.b64encode(zip_buffer.getvalue())
        zip_filename = 'Journal_Entry_Reports.zip'

        record = self.create({
            'move_ids': [(6, 0, moves.ids)],
            'pdf_file': zip_data,
            'pdf_filename': zip_filename,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/account.move.print.separate.pdf.wizard/{record.id}/pdf_file/{zip_filename}?download=true',
            'target': 'self',
        }
