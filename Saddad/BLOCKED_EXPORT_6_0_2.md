# Saddad 19.0.6.0.2 - Muqeem blocked-record export

Upgrade the existing Saddad addon (capital S). Replace its folder, restart Odoo and upgrade Saddad; do not uninstall it. This update is separate from Manpower Recruitment and does not start Housing development.

Open a Muqeem Resident Import in Preview or Applied and click **Export Blocked Records**. The Excel download contains only rows currently marked Blocked, with the original source row number, blocking reason and all 13 original report columns. It works on previously reviewed imports as well as new ones, because it reads their retained original workbook.

Dates display DD/MM/YYYY; identifiers remain text. Invalid source values are preserved for review and formula-like text remains literal. Filters and frozen columns help review long lists. No blocked rows produces a clear message instead of an empty file.

Export does not apply records, change results, edit employee information or refresh matching. It respects the Muqeem Resident HR permission and company access rules. The file is generated on demand, without saving another attachment or unlocking the reviewed import.

Use the file as a review report. Correct the underlying employee/mapping data or the original Muqeem report as appropriate, then create a fresh import. The downloaded review file includes extra columns and is not directly re-importable.
