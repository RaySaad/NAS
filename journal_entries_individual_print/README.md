# account_journal_separate_pdf

**Odoo 18 Module — Print Journal Entries as Separate PDFs**

---

## What This Module Does

In standard Odoo 18, when you select multiple Journal Entries and click
**Print → Print Journal Entries**, all entries are merged into **one PDF**.

This module adds a new option so you can generate each Journal Entry as its
**own individual PDF file**. All individual PDFs are packed into a single
**ZIP archive** for easy download.

---

## New Feature Location

**Accounting → Journal Entries (list view)**

1. Select one or more Journal Entries (tick the checkboxes)
2. Click the **⚙ Actions** button (or the **Print** dropdown)
3. Choose **"Print Separate PDFs"**
4. A wizard opens — click **"Generate Separate PDFs"**
5. Click **"⬇ Download ZIP"** to save the archive

Each PDF inside the ZIP is named after the **CRM Number / Reference** of the
Journal Entry (e.g. `P243841.pdf`, `P243840.pdf`, etc.).

---

## Installation

### Step 1 — Copy the module
Place the `account_journal_separate_pdf` folder inside your Odoo addons path:

```
/path/to/odoo/custom_addons/account_journal_separate_pdf/
```

### Step 2 — Update the app list
```bash
# Restart Odoo with update flag
./odoo-bin -c odoo.conf -u account_journal_separate_pdf
# OR from the Odoo UI:
# Settings → Activate Developer Mode → Apps → Update Apps List
```

### Step 3 — Install the module
- Go to **Apps**
- Search for **"Journal Entries - Print Separate PDFs"**
- Click **Install**

---

## Requirements

| Item        | Version  |
|-------------|----------|
| Odoo        | 18.0     |
| Python      | 3.10+    |
| Dependencies| `account` (standard Odoo Accounting module) |

No additional Python packages required — uses only Python's built-in `zipfile`
and `io` modules.

---

## File Structure

```
account_journal_separate_pdf/
├── __init__.py
├── __manifest__.py
├── security/
│   └── ir.model.access.csv          # Access rights for the wizard model
├── wizard/
│   ├── __init__.py
│   ├── print_separate_pdf_wizard.py  # Core logic: PDF generation + ZIP packing
│   └── print_separate_pdf_wizard_views.xml  # Wizard form + server action binding
├── views/
│   └── account_move_views.xml        # Adds action to Actions menu in list view
└── static/src/js/
    └── action_manager_report.js      # Optional JS (future frontend extension)
```

---

## How It Works (Technical)

1. **Server Action** (`ir.actions.server`) bound to `account.move` model with
   `binding_view_types="list"` — this makes it appear in the **Actions** dropdown
   when rows are selected in the list view.

2. **TransientModel Wizard** (`account.move.print.separate.pdf.wizard`):
   - Receives the selected `account.move` IDs via `context['active_ids']`
   - Iterates over each move and calls `report._render_qweb_pdf([move.id])`
   - Packs each resulting PDF into a `zipfile.ZipFile` in memory
   - Stores the ZIP as a `Binary` field and shows a download button

3. **Download** uses Odoo's standard `/web/content/` route with `?download=true`
   to trigger the browser's save dialog.

---

## Customization

### Change the PDF filename pattern
In `wizard/print_separate_pdf_wizard.py`, edit this section:

```python
crm_number = move.payment_reference or move.ref or move.name or f'JV_{move.id}'
```

You can use any field from `account.move`, for example:
- `move.name` — Journal Entry number (e.g. `RAJHI04/2026/...`)
- `move.ref` — CRM Number / Reference
- `move.payment_reference` — Payment reference

### Change the ZIP filename
```python
'zip_filename': 'Journal_Entries_Separate_PDFs.zip',
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Could not find a PDF report" error | Make sure the `account` module is installed and the Journal Entry report (`account.action_report_journal_entry`) exists |
| Option not visible in Actions menu | Upgrade the module: `./odoo-bin -u account_journal_separate_pdf` |
| Empty ZIP file | Check that selected Journal Entries have a valid report template |

---

## License

LGPL-3 — Free to use, modify, and distribute.
