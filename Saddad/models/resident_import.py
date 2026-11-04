import base64
import io
import json
import zipfile
from datetime import date, datetime
from collections import Counter
import openpyxl
from hijridate import Gregorian
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .resident import Resident, identity


HEADERS = ['رقم الاقامة', 'الاسم', 'الجنس', 'الجنسية', 'المهنة', 'رقم الجواز',
           'تاريخ انتهاء الجواز', 'تاريخ اصدار الاقامة', 'تاريخ انتهاء الاقامة',
           'تاريخ الميلاد', 'خارج المملكه', 'تاريخ انتهاء الاقامة بالهجري', 'رقم صاحب العمل']
KEYS = ['iqama', 'reported_name', 'sex', 'nationality', 'occupation', 'passport',
        'passport_expiry', 'iqama_issue', 'reported_expiry', 'birth_date',
        'outside_kingdom', 'reported_hijri', 'employer']
DATE_KEYS = {'passport_expiry', 'iqama_issue', 'reported_expiry', 'birth_date'}


def date_value(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value).strip()).isoformat()


class ResidentImport(models.Model):
    _name = 'saddad.resident.import'
    _description = 'Muqeem Resident Import'
    _inherit = ['mail.thread']
    _rec_name = 'filename'
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    filename = fields.Char(required=True)
    file = fields.Binary(required=True, attachment=True)
    snapshot_date = fields.Date(required=True, help='Date the report was exported from Muqeem, confirmed by HR.')
    state = fields.Selection([('draft', 'Draft'), ('preview', 'Preview'), ('applied', 'Applied'), ('rejected', 'Rejected')], default='draft', readonly=True, tracking=True)
    line_ids = fields.One2many('saddad.resident.import.line', 'batch_id', readonly=True)
    summary = fields.Text(readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason')
    applied_at = fields.Datetime(readonly=True)
    applied_by = fields.Many2one('res.users', readonly=True)

    blocked_export = fields.Binary(string='Blocked Records Excel', compute='_compute_blocked_export', attachment=False, groups='Saddad.group_resident_hr')

    def _check_blocked_export(self):
        self.ensure_one()
        self.check_access('read')
        if not self.env.user.has_group('Saddad.group_resident_hr'):
            raise AccessError(_('Muqeem Resident HR access is required to export blocked records.'))
        if self.state not in ('preview', 'applied'):
            raise UserError(_('Preview the import before exporting blocked records.'))
        blocked = self.line_ids.filtered(lambda line: line.status == 'error').sorted('row_number')
        blocked.check_access('read')
        if not blocked:
            raise UserError(_('There are no blocked records to export.'))
        return blocked

    def action_export_blocked(self):
        self._check_blocked_export()
        filename = 'Muqeem_Blocked_%s_%s.xlsx' % (self.id, self.snapshot_date.strftime('%d-%m-%Y'))
        return {'type': 'ir.actions.act_url', 'url': '/web/content/saddad.resident.import/%s/blocked_export/%s?download=true' % (self.id, filename), 'target': 'self'}

    def _compute_blocked_export(self):
        for batch in self:
            batch.blocked_export = base64.b64encode(batch._blocked_export_bytes())

    def _blocked_export_bytes(self):
        blocked = self._check_blocked_export()
        # Blocked rows can fail before a payload is populated. Always read the
        # immutable original workbook, including pre-feature import batches.
        source = openpyxl.load_workbook(io.BytesIO(base64.b64decode(self.file)), read_only=True, data_only=False)
        try:
            sheet = source.active
            rows = sheet.iter_rows(values_only=True)
            headers = [str(v or '').strip() for v in next(rows)]
            order = [headers.index(header) for header in HEADERS]
            wanted = {line.row_number: line for line in blocked}
            original = {n: [row[i] if i < len(row) else None for i in order]
                        for n, row in enumerate(rows, 2) if n in wanted}
        finally:
            source.close()
        if len(original) != len(blocked):
            raise UserError(_('Some blocked rows could not be located in the original report.'))
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        book = openpyxl.Workbook()
        sheet = book.active
        sheet.title = 'Blocked Records'
        sheet.sheet_view.rightToLeft = self.env.lang.startswith('ar') if self.env.lang else False
        sheet.append([_('Source Row'), _('Blocking Reason')] + HEADERS)
        for row_index, line in enumerate(blocked, 2):
            values = original[line.row_number]
            output = [line.row_number, line.detail or '']
            for key, value in zip(KEYS, values):
                if key in DATE_KEYS and value:
                    try:
                        value = fields.Date.to_date(value) if isinstance(value, (date, datetime)) else date.fromisoformat(str(value).strip())
                    except (ValueError, TypeError):
                        pass  # Invalid dates must remain visible for correction.
                elif key == 'reported_hijri' and value:
                    import re
                    match = re.fullmatch(r'(\d{4})[-/](\d{2})[-/](\d{2})', str(value).strip())
                    if match:
                        value = '%s/%s/%s' % (match[3], match[2], match[1])
                if key not in DATE_KEYS and value is not None:
                    value = str(value)
                output.append(value)
            sheet.append(output)
            for column in range(1, 16):
                cell = sheet.cell(row_index, column)
                # Force strings, including =,+,-,@ values, to remain literal.
                if isinstance(cell.value, str):
                    cell.data_type = 's'
                    cell.number_format = '@'
                elif isinstance(cell.value, (date, datetime)):
                    cell.number_format = 'dd/mm/yyyy'
                cell.alignment = Alignment(vertical='top', wrap_text=True)
        sheet.freeze_panes = 'C2'
        sheet.auto_filter.ref = sheet.dimensions
        sheet.row_dimensions[1].height = 42
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='24476A')
            cell.alignment = Alignment(wrap_text=True, vertical='center')
        for n in range(1, 16):
            sheet.column_dimensions[get_column_letter(n)].width = 12 if n == 1 else 65 if n == 2 else 32 if n == 4 else 22
        for n in range(2, sheet.max_row + 1):
            sheet.row_dimensions[n].height = 60
        stream = io.BytesIO()
        book.save(stream)
        book.close()
        return stream.getvalue()

    @api.model_create_multi
    def create(self, vals_list):
        if any({'state', 'line_ids', 'summary', 'applied_at', 'applied_by'}.intersection(v) for v in vals_list):
            raise AccessError(_('Import outcomes are managed by import actions.'))
        return super().create([dict(v, state='draft', summary=False, applied_at=False, applied_by=False, line_ids=False) for v in vals_list])

    def write(self, vals):
        if 'company_id' in vals and any(rec.company_id.id != vals['company_id'] for rec in self):
            raise UserError(_('Create a new import to change the company.'))
        if set(vals) == {'rejection_reason'}:
            self._lock()
        if set(vals) == {'rejection_reason'} and all(rec.state == 'preview' for rec in self):
            return super().write(vals)
        if {'state', 'line_ids', 'summary', 'applied_at', 'applied_by'}.intersection(vals) or any(r.state != 'draft' for r in self):
            raise AccessError(_('Create a new import to change a reviewed report.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Import history cannot be deleted.'))

    def _lock(self):
        self.ensure_one()
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM saddad_resident_import WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset()

    def action_reset_preview(self):
        self._lock()
        if self.state != 'preview':
            raise UserError(_('Only Preview imports can be reset.'))
        lines = self.line_ids
        audit = [{'row': l.row_number, 'iqama': l.iqama, 'status': l.status, 'detail': l.detail} for l in lines]
        self.env['ir.attachment'].create([
            {'name': 'Before reset - ' + self.filename, 'type': 'binary', 'datas': self.file,
             'res_model': self._name, 'res_id': self.id, 'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},
            {'name': 'Preview before reset.json', 'type': 'binary',
             'datas': base64.b64encode(json.dumps({'snapshot_date': str(self.snapshot_date), 'summary': self.summary, 'rows': audit}, ensure_ascii=False).encode('utf-8')),
             'res_model': self._name, 'res_id': self.id, 'mimetype': 'application/json'}])
        super(ResidentImportLine, lines).write({'active': False})
        super().write({'state': 'draft', 'summary': False, 'rejection_reason': False})
        self.message_post(body=_('Preview reset to Draft. The previous source report and preview results were retained as audit attachments. No resident records were changed.'))
        return True

    def action_reject_preview(self):
        self._lock()
        if self.state != 'preview':
            raise UserError(_('Only Preview imports can be rejected.'))
        if not (self.rejection_reason or '').strip():
            raise UserError(_('Enter a rejection reason first.'))
        super().write({'state': 'rejected'})
        self.message_post(body=_('Resident import rejected: %s', self.rejection_reason))
        return True

    def action_preview(self):
        self._lock()
        if self.state != 'draft':
            raise UserError(_('This import has already been previewed.'))
        if self.snapshot_date > fields.Date.context_today(self):
            raise UserError(_('The snapshot date cannot be in the future.'))
        try:
            data = base64.b64decode(self.file, validate=True)
            if len(data) > 15 * 1024 * 1024:
                raise ValueError()
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(f.file_size for f in archive.infolist()) > 100 * 1024 * 1024:
                    raise ValueError()
            book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            sheet = book.active
            if sheet.max_row > 25001 or sheet.max_column != 13:
                raise ValueError()
            rows = sheet.iter_rows(values_only=True)
            headers = [str(v or '').strip() for v in next(rows)]
            if set(headers) != set(HEADERS):
                raise ValueError()
            order = [headers.index(h) for h in HEADERS]
            records = [(n, [r[i] for i in order]) for n, r in enumerate(rows, 2) if any(v is not None for v in r)]
            book.close()
        except Exception as exc:
            raise UserError(_('Upload the active-residents XLSX report with its 13 original columns, no more than 25,000 rows and 15 MB.')) from exc
        identities = Counter(identity(r[0]) for _, r in records)
        employees = self.env['hr.employee'].with_context(active_test=False).search([('company_id', '=', self.company_id.id)])
        matches = {}
        for employee in employees:
            matches.setdefault(identity(employee.identification_id), []).append(employee)
        establishments = {r.number: r for r in self.env['saddad.establishment'].search([('company_id', '=', self.company_id.id)])}
        profiles = {r.employee_id.id: r for r in self.env['saddad.resident'].search([('company_id', '=', self.company_id.id)])}
        labels = self.env['saddad.resident'].fields_get(attributes=['string'])
        prepared = []
        for number, row in records:
            values, error = {}, ''
            employee = False
            profile = False
            try:
                iqama, employer = identity(row[0]), identity(row[12])
                if len(iqama) != 10 or not iqama.isdigit() or identities[iqama] > 1:
                    raise ValueError(_('Missing, invalid or duplicated Iqama number.'))
                if employer not in establishments:
                    raise ValueError(_('Employer number is not mapped to this company.'))
                candidates = matches.get(iqama, [])
                if len(candidates) != 1 or not candidates[0].active:
                    raise ValueError(_('No unique active employee matches this Iqama in this company.'))
                employee = candidates[0]
                profile = profiles.get(employee.id)
                if profile and profile.snapshot_date > self.snapshot_date:
                    raise ValueError(_('This report is older than the stored resident snapshot.'))
                for key, raw in zip(KEYS, row):
                    if key == 'employer' or raw is None or str(raw).strip() == '':
                        continue
                    values[key] = date_value(raw) if key in DATE_KEYS else str(raw).strip()
                values['iqama'] = iqama
                if not values.get('reported_expiry'):
                    raise ValueError(_('The report must contain an Iqama expiry date.'))
                expiry = fields.Date.to_date(values['reported_expiry'])
                hijri = Gregorian(expiry.year, expiry.month, expiry.day).to_hijri().isoformat()
                if values.get('reported_hijri') and identity(values['reported_hijri']) != hijri:
                    raise ValueError(_('Gregorian and Hijri expiry dates do not agree. Review the source report.'))
                values.update(company_id=self.company_id.id, employee_id=employee.id,
                              establishment_id=establishments[employer].id, snapshot_date=str(self.snapshot_date))
            except (ValueError, OverflowError) as exc:
                error = str(exc)
            changes = []
            if not error:
                for key, value in values.items():
                    current = profile[key] if profile else False
                    if hasattr(current, 'id'):
                        current = current.id
                    if str(current or '') != str(value):
                        descriptor = self.env['saddad.resident']._fields[key]
                        old_display, new_display = current or '', value
                        if descriptor.type == 'many2one':
                            old_display = profile[key].display_name if profile and profile[key] else ''
                            new_display = self.env[descriptor.comodel_name].browse(value).display_name
                        changes.append('%s: %s → %s' % (labels[key]['string'], old_display, new_display))
            prepared.append({'batch_id': self.id, 'row_number': number, 'iqama': identity(row[0]),
                'employee_id': employee.id if employee else False, 'status': 'error' if error else 'ready',
                'detail': error or '\n'.join(changes) or _('No changes'),
                'payload': json.dumps({'values': values, 'profile_id': profile.id if profile else False,
                    'version': str(profile.write_date) if profile else False}),
                'proposed_expiry': values.get('reported_expiry') if not error else False})
        super(ResidentImportLine, self.env['saddad.resident.import.line']).create(prepared)
        errors = sum(v['status'] == 'error' for v in prepared)
        super().write({'state': 'preview', 'summary': _('Rows: %(rows)s. Ready: %(ready)s. Blocked: %(errors)s. Applying updates ready resident profiles and fills empty or advances older employee Iqama expiry dates. Equal or later employee dates are preserved; blocked rows are skipped.', rows=len(prepared), ready=len(prepared)-errors, errors=errors)})

    def action_apply(self):
        self._lock()
        if self.state != 'preview':
            raise UserError(_('Preview the import before applying it.'))
        ready = self.line_ids.filtered(lambda l: l.status == 'ready')
        if not ready:
            raise UserError(_('There are no ready rows to import.'))
        # A company lock serializes imports even where a resident does not exist yet.
        self.env.cr.execute('SELECT id FROM res_company WHERE id = %s FOR UPDATE', [self.company_id.id])
        # Read the latest employee expiry under a lock, including changes made
        # after Preview. Never overwrite a newer employee date with this report.
        employees = ready.employee_id.sorted('id')
        if any(not line.employee_id for line in ready):
            raise UserError(_('Employee matching changed. Create a fresh import preview.'))
        employees.check_access('write')
        self.env.cr.execute('SELECT id FROM hr_employee WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(employees.ids)])
        employees.invalidate_recordset()
        updated_expiries = 0
        for line in ready:
            payload = json.loads(line.payload)
            values = payload['values']
            employee = line.employee_id
            employee.check_access('read')
            if employee.company_id != self.company_id or not employee.active or identity(employee.identification_id) != line.iqama:
                raise UserError(_('Employee matching changed. Create a fresh import preview.'))
            profile = self.env['saddad.resident'].search([('employee_id', '=', employee.id)], limit=1)
            if profile:
                self.env.cr.execute('SELECT id FROM saddad_resident WHERE id = %s FOR UPDATE', [profile.id])
                profile.invalidate_recordset()
            if (profile.id or False) != payload['profile_id'] or (str(profile.write_date) if profile else False) != payload['version']:
                raise UserError(_('Resident data changed since preview. Create a fresh import preview.'))
            establishment = self.env['saddad.establishment'].browse(values['establishment_id'])
            if establishment.company_id != self.company_id:
                raise UserError(_('Establishment mapping changed. Create a fresh import preview.'))
            values['source_batch_id'] = self.id
            if profile:
                super(Resident, profile).write(values)
            else:
                profile = super(Resident, self.env['saddad.resident']).create(values)
            profile.message_post(body=_('Resident snapshot imported from %s.', self.filename))
            reported_expiry = fields.Date.to_date(values['reported_expiry'])
            current_expiry = employee.saddad_iqama_expiry
            if not current_expiry or reported_expiry > current_expiry:
                employee._apply_verified_expiry(current_expiry, reported_expiry,
                    _('Muqeem Resident Import %(batch)s: %(filename)s', batch=self.id, filename=self.filename))
                updated_expiries += 1
            super(ResidentImportLine, line).write({'status': 'applied'})
        super().write({'state': 'applied', 'applied_at': fields.Datetime.now(), 'applied_by': self.env.uid})
        self.message_post(body=_('Resident import applied. Employee Iqama expiry dates updated: %s. Equal or later dates were preserved.', updated_expiries))


class ResidentImportLine(models.Model):
    _name = 'saddad.resident.import.line'
    _description = 'Muqeem Import Preview Row'
    _order = 'row_number'
    batch_id = fields.Many2one('saddad.resident.import', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='batch_id.company_id', store=True)
    active = fields.Boolean(default=True)
    row_number = fields.Integer()
    iqama = fields.Char()
    employee_id = fields.Many2one('hr.employee')
    proposed_expiry = fields.Date()
    status = fields.Selection([('ready', 'Ready'), ('error', 'Blocked'), ('applied', 'Applied')])
    detail = fields.Text()
    payload = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Preview rows are generated by the import.'))

    def write(self, vals):
        raise AccessError(_('Preview rows cannot be edited. Create a corrected import.'))

    def unlink(self):
        raise AccessError(_('Import history cannot be deleted.'))
