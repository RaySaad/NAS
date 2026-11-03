# Saddad 19.0.6.1.1

Menu update: Qiwa Work Permit and Qiwa Work Permit Lines are now grouped under Saddad > Work Permit Transactions (معاملات رخص العمل). Existing actions and access permissions are retained. This menu-only update was checked for XML validity and packaged with all 6.1.0 features below; the full test result below applies to 6.1.0.

## Accountant deferral review
After all Muqeem payments are marked and the expense reaches Done, the user authorized by the configured posting approval rule may change Defer Expense, Defer Start, and Defer End on the expense form before creating the JV. Save changes before posting. Changes are recorded in chatter. Other financial fields remain locked. Posted transactions cannot be edited. Deferral still requires company-paid expenses and valid start/end dates.

## Resident Import
Preview imports now offer Reset Preview to Draft and Reject Preview.
- Reset retains the previous XLSX and preview results as audit attachments and archives the old preview rows. Replace the file if needed and preview again on the same record.
- Reject requires a Rejection Reason and retains the import in Rejected state without applying it. Create a new import to try again.
- Applied imports cannot be reset or rejected. Existing blocked-record export is unchanged and includes Iqama Number.

## Line reporting
Muqeem Expense Lines includes Transaction Date, taken from its parent expense, and a date filter.
The new Qiwa Work Permit Lines menu lists each employee's permit line with Iqama, batch reference, issue date, product, period, permit validity, amount, batch status and downstream status. Search and group lines; use Open Batch to view the source and its chatter. The list does not permit direct edits. Existing company access rules apply.
New date columns display DD/MM/YYYY.

## Installation
Back up the database and existing addon. Replace the existing uppercase Saddad addon folder with the complete Saddad folder in this ZIP. Restart Odoo, update the Apps list, and upgrade Saddad. Reload the browser to load the new date widget. This package does not automatically modify the live installation.

## Validation
Verified in an isolated Odoo 19 Enterprise database with Arabic enabled: module installation and upgrade, 154 tests with zero failures or errors, Python/XML/catalog validation, and JavaScript syntax validation. No live business database was changed. Browser visual review was not performed for this release.
