# Muqeem Resident Management — 19.0.6.0.1

## Setup

1. Replace the Saddad folder, restart Odoo and Upgrade Saddad in Apps. Back up your database first. The Odoo Python environment needs openpyxl 3.1 or later (below 4), as well as the existing hijridate dependency.
2. Assign the new **Muqeem Resident HR** role to authorized HR users. Retain their existing expense/workflow roles if they also manage payments or approvals. Saddad Admin configures employer mappings; it does not automatically grant resident-management access to ordinary users.
3. In Saddad → Configuration → Muqeem Establishments, create each employer number and assign its company. Multiple establishments may belong to one company. One employer number cannot belong to multiple companies. Configure the default 7 pending days and 30 expiry-warning days here.
4. Ensure employee Iqama numbers and company assignments are correct. Assign active HR owners with access to the relevant company. Outgoing email must be configured for queued alert emails to be delivered.

## Import and resident profiles

Open Saddad → Muqeem → Resident Imports. Select the company, upload the original active-residents XLSX, and enter its actual export date. Preview Import displays matching, proposed changes and row errors. Apply Ready Rows updates only matching resident profiles; blocked rows remain in the batch for review. For a report spanning several companies, import separately for each company; rows for other employer numbers are blocked for that company. The original workbook remains unchanged.

The importer supports the supplied 13 Arabic columns, including reordered columns, at most 25,000 data rows and 15 MB. It normalizes identity digits/whitespace, requires a unique active employee match, checks employer mappings, dates and Gregorian/Hijri agreement, and preserves existing values where source cells are blank. Profiles retain source batch, export date and import history. An older report cannot replace a newer stored snapshot. A stale preview must be recreated. Employee absence from an export never archives the employee.

Use Saddad → Muqeem → Muqeem Residents or the employee's Muqeem tab to view the profile. Reported data remains separate from core employee fields. Review Employee Expiry Update provides an explicit HR confirmation step for applying the reported expiry; it rejects stale/conflicting data and dates that shorten the employee's current expiry. It does not mark a renewal completed or change payment/accounting status.

## Renewal follow-up

Open **Renewal Follow-up** from a confirmed Qiwa employee line or a Muqeem Iqama expense line. Alternatively create an entry in Saddad → Renewals → Iqama Renewal Follow-up after importing the resident. The shortcuts reuse an existing cycle. Only one pending cycle is allowed per employee. Link the corresponding Qiwa work-permit line and Iqama expense line for the same employee and duration.

The original expiry comes from the PTR snapshot, or from the employee expiry captured on new Muqeem expense lines. When preparing a follow-up without an expense line, it snapshots the current employee expiry. Linking a source with a different original expiry is blocked. The suggested new expiry is original expiry plus the renewal period; HR must verify it against the actual Muqeem result. It is intentionally separate from the accounting deferral end date, which uses an inclusive end-date rule.

For work permits, enter the actual renewal date and evidence, verify the existing Qiwa Valid Until field, and click **Confirm Work Permit Renewed**. Qiwa batch confirmation/payment does not perform this action automatically. The latest verified permit expiry appears on the resident profile and employee tab.

Record employee/company/other blockers, notes and an HR owner. Daily alerts create Odoo activities and queued email after 7 days from the actual permit renewal date, and within 30 days of the work-permit expiry, while the matching Iqama renewal remains pending. Both thresholds are configurable per establishment. Each condition alerts once per cycle; simultaneous conditions produce one notification. Overdue permits qualify for the expiry condition. A missing validity date must be corrected before confirming actual work-permit renewal. Completing the cycle closes its generated activities.

After renewal is executed on Muqeem, enter its evidence/reference and verified new expiry. **Confirm Iqama Renewal** requires a paid, mapped Iqama service line. It locks and checks the records:

- Current employee expiry equals original: apply the verified new date.
- Current equals the verified new date: mark completion without adding another period.
- Neither matches: block for HR reconciliation.
- Already completed: reject repeat confirmation.

Completion records the user/time and chatter history. It does not post accounting entries or make bank payments. A payment mark cannot be reversed after the linked Iqama renewal is completed.

## Limits and future connector

- No live Muqeem API calls, endpoints, credentials or subscription checks are implemented. The resident records, source history and guarded expiry update method form the integration foundation. The optional provider addon still requires Elm's specification and sandbox validation.
- Existing manual expense lines created before this version may lack an original expiry snapshot. PTR-linked lines can use their PTR snapshot. Unknown legacy baselines are blocked from automatic renewal confirmation rather than guessed; historical reconciliation/migration remains a separate task. Imported verified dates can still be reviewed independently.
- Core name, nationality, passport and job fields are not overwritten by imports. All supplied fields are retained in the separate resident profile.
- Imports apply ready rows and retain blocked rows; a concurrent-data conflict aborts the application transaction and requires a fresh preview. There is no external background job dependency.
- Existing posted entries, deferral schedules, employee dates and renewal history are not retroactively modified by installation.

The employee Muqeem tab displays read-only resident fields, including employer number, and provides Open Muqeem Profile for history. Older imported expiry dates are clearly flagged before an update can be reviewed.
