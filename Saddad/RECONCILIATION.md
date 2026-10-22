# 19.0.5.0.0 — Saddad Services

Saddad Services adds the approved Draft > Reviewed > Financial Approval > GM > Pending Payment > Done / Posting Ready > Posted workflow. Service User submits and reviews; Service Finance and GM approve/reject their own stages; rejected requests reset to Draft through the configured reset role. Saddad Payment controls bank/cash journal selection and line payment marks; Service Post posts the direct journal entry. Approval rules can be overridden per company. Administrators do not automatically hold every approval role.

New Billers master data under Saddad > Configuration > Billers: translated name, code, partner, company and archive control. Codes are unique per company. Saddad Admin maintains billers; Services roles have read-only access. A request requires a description and biller. Lines hold service product, invoice/reference number, optional description, amount, VAT, analytic account and supporting document. Employee selection is not required for general services. Attachments also remain available through request chatter. No invented biller seed data or automatic old-module record migration.

Saddad Settings > Saddad Services Product Category is company-specific, defaults to the existing seeded service category and includes descendants. Only active service products available to the company can be selected; new/edited lines enforce the same rule. Product Cost supplies the initial editable amount. Existing Muqeem and Morro category settings remain independent. The shared Default Bank / Cash Journal is used; billers must be configured before service requests can be created.

Untaxed, VAT and total amounts are calculated with native Odoo tax computation, including tax-inclusive prices. Supported taxes retain the existing Saddad scope: non-negative percentage purchase taxes due on invoice. Group, fixed, cash-basis and negative taxes are not supported by this direct-JV flow. Payment is recorded per line; partial payment remains Pending Payment, all paid moves to Done. Posting creates one balanced account.move journal entry with service expense debits, tax repartition lines/tags and bank/cash credit. The expense lines carry the biller partner and optional analytic allocation. No account.payment or external bank transfer is created. Reposting, independent reset/cancellation/reversal, deletion and economic edits of posted entries are blocked. Reversal workflow remains a later enhancement. No Services deferrals are introduced.

Email and Odoo activities route to the next configured role, with the correct state in the recipient language and a direct link. Completed-stage activities are closed. English/Arabic catalogs cover new fields, views, statuses, validations and notifications. Native list views/statusbars preserve Odoo direction handling; browser RTL acceptance and real SMTP delivery remain user-environment checks.

Validation: full isolated Odoo 19 Enterprise regression suite passed **131 tests, 0 failures, 0 errors** (services_regression.log), including 18 Services tests for workflow/roles, reset, payment, journal guards, category configuration, biller access/company/uniqueness, VAT-inclusive posting, analytics/attachments, recipient-language notifications and Arabic views/stages. Apps immediate-upgrade method passed against a pre-Services database (services_frontend_upgrade.log). Original supplied source files, installed addons and user database were not modified.

Upgrade: replace the complete capital-S Saddad folder, restart Odoo, then Upgrade; do not uninstall. Configure Billers, Services Product Category and accounting defaults; assign Saddad Service User / Finance / GM / Post and Saddad Payment roles. This full release includes all previous PTR, Qiwa, Muqeem and Morro work. Optional product deferred-account addon remains optional. Dashboard implementation and final user acceptance remain after this phase.

# 19.0.4.0.0 — Morro phase

Morro is now available under Saddad > Morro Expenses. Workflow: Draft > Fleet Manager > Financial Approval > GM > Pending Payment > Done / Posting Ready > Posted, with rejection reasons and authorized reset to Draft. Each transition uses configurable approval rules and company-aware permissions. Assign Morro User, Morro Fleet, Morro Finance, Morro GM, Saddad Payment and Morro Post to the responsible users; Saddad Admin configures rules and does not automatically own every approval role.

Supports Traffic Violation, Driving Licence and Motor Vehicle requests. Employee/department and optional Fleet vehicle/plate links are on each line. Products come from the configurable Morro Product Category (including descendants); active services only, with product Cost as the initial amount and editable draft amounts. Existing 166 seeded Morro products remain unchanged. Includes violation number/date, description, optional licence period (2/5/10 years), analytic account, planned deduction date, line supporting document and request chatter attachments. The planned deduction date is informational; no payroll deduction is generated.

Violation numbers are unique across Morro lines, preserving the original global duplicate rule. Whitespace and Arabic/Western digit differences are normalized. Traffic lines require number/date, and future violation dates are rejected. Unpaid/paid marks are controlled by Saddad Payment; partial payment stays Pending Payment. All lines paid moves to Done. Posting creates a balanced direct bank/cash journal entry, with company expenses or employee-loan debits according to Paid For. Employee is the default as in the reference module. VAT uses existing supported percentage-tax rules. No account.payment, bank transfer, payroll transaction or deferred schedule is generated by Morro. Posted entries are protected; reversal/cancellation workflow remains outside this release.

Traffic Violation Forecast follows the confirmed stage-based definition: full traffic-violation request total in Fleet Manager, Financial Approval, GM and Pending Payment; zero in Draft, Rejected, Done and Posted. Partially paid requests in Pending Payment remain included at full total, as this is a request-stage measure. Driving Licence and Motor Vehicle requests are excluded. Forecast field, list total and filter are available now; dashboard presentation remains a later phase. Do not sum companies with different currencies without currency conversion.

Email and activities route to the next configured group. After Fleet approval the recipient is Finance and the message includes Financial Approval in the recipient's language. Prior workflow activities close on advancement. English and Arabic model/view/message translations are included. Uses native Odoo list views and statusbars without forced direction styles.

Installation: complete capital-S Saddad module, version 19.0.4.0.0. Fleet is now a declared dependency and installs automatically. Replace the full folder, restart and Upgrade (do not uninstall). Set Morro Product Category in Saddad Settings; shared Default Bank / Cash Journal and Employee Loan Account apply. Optional product deferred-account addon remains optional and pertains to Muqeem. Existing PTR/Qiwa/Muqeem functionality is included. No legacy Morro record migration is performed.

Validation: 113 tests passed with no failures/errors on the upgraded isolated Odoo 19 Enterprise database. Includes 22 Morro tests covering approval roles, payment, JV balances/locking, duplicate normalization, dates, vehicle/analytic/company checks, configurable category/rules, forecast membership, native form entry, notifications and Arabic view/stage labels. Fresh installation succeeded; frontend Apps upgrade method also succeeded on a pre-Morro database. Logs: morro_release_tests.log, morro_clean_install.log, morro_frontend_upgrade.log. Email queue/rendering verified; real SMTP delivery and full browser RTL visual acceptance still need user-environment testing. No user database or installed addon directory was changed.

# 19.0.3.0.7 — Frontend upgrade compatibility

Disable automatic prefetch on the newly added res.company category field. This prevents Apps Upgrade from reading a not-yet-created column while checking company countries before schema migration. Reproduced the missing-column database state in isolation, successfully read company countries and ran button_immediate_upgrade; verified the new column was created. No manual SQL or reinstall is needed on the user database. Replace the full module, restart Odoo and retry Upgrade.

# 19.0.3.0.6 — Configurable Muqeem product category

Saddad Settings now exposes Muqeem Product Category for each company. Defaults/falls back to the seeded Muqeem category using its XML ID, never its name. Product selector includes active service products in that category and descendants, shared or belonging to the expense company. Quick product creation is disabled in this selector. New and edited lines are validated server-side, including PTR/Qiwa handoffs; existing posted records are not migrated. Changing the setting may require moving mapped service products into the selected category. Company settings remain restricted to Saddad Admin and allowed companies. Category changes do not rewrite any product or historical expense.

# 19.0.3.0.5 — Product deferred-account integration

Optional compatibility with account_deferred_expense_account (supplied 19.0.1.0.0). Install that addon separately to configure deferred accounts on products/categories. Saddad resolves each source journal line using the addon's configured fields: line override (if present), product, category/parent, company default. Saddad exposes no new manual line override field. Without the addon, company defaults continue to apply. Uses the expense company for company-dependent settings; validates active accounts, company membership and Current Assets/Prepayments/Non-current Assets types. General/Miscellaneous journal remains company-configured. Both transfer and recognition use the same resolved account. Posted source account overrides are locked. The supplied addon's category helper is unavailable in the installed Odoo build; Saddad traverses category parents directly instead. This does not repair the separate addon's vendor-bill fallback. No changes to the supplied addon, existing posted schedules or user database.

Upgrade: keep the supplied addon installed, replace the Saddad folder, restart Odoo and upgrade Saddad. Test new expenses with the intended product accounts. The ZIP contains Saddad only; the optional addon is not bundled.

# 19.0.3.0.4 — Inclusive deferral end dates

Automatic deferral end dates now use start date + renewal months - one day, matching Odoo inclusive end dates. December 1 plus 3 months ends February 28 (February 29 in leap years); December 15 ends March 14. Applies to manual/Qiwa line defaults, form recalculation and direct PTR handoff. Explicit end dates remain editable and are preserved. Existing records and posted schedules are not migrated. A mid-month start can legitimately span four calendar recognition months.

# 19.0.3.0.3 — Prepayments deferral compatibility

Deferred posting now accepts both Prepayments and Current Assets holding accounts, including the Saudi localization default 104020. Active account, company and active General/Miscellaneous journal checks remain. English and Arabic validation text updated. No account reclassification or data migration is required.

# Direct Iqama handoff correction — 19.0.3.0.2

Completes the missed Phase 4 route explicitly requested by the user: confirmed Iqama PTRs
create/link a Draft Muqeem expense without Qiwa. Employee, service product, period, reviewed
amount and source PTR/line are retained. Snapshot expiry supplies default deferral dates.
Database uniqueness plus the source lock prevent duplicate direct expenses. Old confirmed
records are handled by an explicit authorized preparation action, not an upgrade backfill.
Mixed PTRs send Iqama directly and work permit through Qiwa. Qiwa status is Not Applicable
for confirmed requests without work-permit lines. Payment and posting remain separate.

---

# Muqeem phase — 19.0.3.0.0

The user approved the proposed Muqeem phase including deferrals and supplied the Odoo 19
Enterprise addons path when asked. This implements document Phase 4 and the Muqeem portion
of Phase 7; no invoice/vendor-bill workaround or accounting.payment output is introduced.

- Sections 7, 10, 12: all retained approval states, rejection/reset, group-specific Paid/Post,
  direct balanced JV, source/account links, duplicate protection and company enforcement.
- OD-04: one consolidated expense per Qiwa batch, including multi-employee sources.
- OD-06/07: expiry-based editable dates, native Enterprise expense calculations and deferred
  schedules only after Posted, for Paid company-expense lines. No deferral on employee loans.
- Section 13: actor/time audit, rejection reason, email queue, activities and record links.
- Section 14: English/Arabic fields/actions, native list/statusbar structures.
- Section 18: default bank journal and employee-loan account configured per company.
- VAT was included as explicitly proposed and accepted for this phase; special tax types are
  rejected. OD-05's separate Saddad Services workflow remains deferred.

HR Assistant has its own rule defaulting to Muqeem User. The technical design uses one JV
once all required lines are Paid. Native deferral periods and amounts are used with explicit
expense direction because Odoo's invoice generator otherwise treats direct entries as revenue.
No employee expiry update, historical Paid import, bank execution or posted reversal is inferred.

Earlier reconciliation notes below are historical and superseded by this section where relevant.

# PDF follow-up — 19.0.2.0.1

The user supplied two paid PDFs in addition to the unpaid sample and authorized improving
PDF import. Reported Qiwa payment status/date and export date are now document metadata.
Paid samples contain payment dates, not due dates; the importer does not invent due dates.
This extends the Qiwa staging/validation scope without implementing Muqeem or accounting
payments. The three actual samples were validated through confirmation with all test data
rolled back. Existing records are not reclassified automatically during upgrade.

# Qiwa-phase reconciliation — 19.0.2.0.0

This release continues the user-approved baseline after acceptance of the foundation.
The initial delivery covered document Phases 1 and 2; this adds Phase 3 (Qiwa Work Permit).
The historical Phase 1 comparison below is retained as context, superseded where noted.

- OD-02: actual atomic PTR → Qiwa create/link, plus explicit legacy confirmed-PTR backfill.
- Section 6: multi-employee batches; invoice/payment references; dates, periods, amounts;
  hr.employee source; Draft/Reviewed/Confirmed; reviewed reset; original PDF attachment.
- OD-03: manual entry and local PDF-assisted staging, validated against the user-supplied
  رمضان.pdf. Its separate SADAD/invoice numbers and payment/permit dates are not conflated.
- OD-04: batch is the single consolidated future Muqeem origin. Creating the actual Muqeem
  expense is deferred to document Phase 4, not falsely represented as complete here.
- Sections 12–14: server ACLs/actions/constraints, company rules, configurable Qiwa approval
  transitions, audit and notifications, translated native Odoo views.
- Specific Qiwa role names were not defined in the baseline. Defaults reuse PTR User and
  PTR Confirmed via independent Qiwa rules; administrators can create company overrides.
- No arbitrary open batch is chosen automatically: users select a shared Draft batch;
  absent that selection, a new batch is created. No invented external reference is assigned.
- PDF scans/unknown layouts need manual completion; no OCR, external API or automatic payment.

Technical conventions checked against Odoo 19 multi-company documentation:
https://www.odoo.com/documentation/19.0/developer/howtos/company.html

---

# Rev. 2 reconciliation

The user-approved Rev. 2 specification is the business baseline. Its document labels
requesting later review/sign-off were treated as document content, not as new instructions
overriding the user's authorization to develop. The current user request defines phase
boundaries and expressly includes PTR/mapping despite their separate document phase number.

| Baseline | Implemented for this delivery |
|---|---|
| §1–2 Fresh Odoo 19, hr.employee, logo | Fresh Saddad module; no employee.record; original embedded logo restored |
| §3 Employee fields | Gregorian source, Hijri conversion, searchable days; exact Citizenship placement |
| §4 Mapping | Four periods, product cost, Default for PTR checkbox, company uniqueness |
| §4.2 / OD-10 Seeds | 29 Muqeem + 166 Morro + 1 Saddad Service; three categories; 196 Arabic names |
| §5.2 PTR workflow | Draft/Reviewed/Confirmed, service lines, review/reset by PTR User, confirmation group |
| §5.3 / §15 Automation | Daily ID/date eligibility, 30-day configurable cutoff, duplicate protection, all-draft recheck |
| §5.4 / §16 UI | Department, ID, expiry, days, totals, state, search filters and bulk review/confirm |
| §12 Security | Approved role skeleton, server checks, line locks, company rules; HR Officer implication explicitly disclosed |
| §13 / OD-08 Notifications | Chatter, actor/time audit, group email queue, translated activities, previous activities closed |
| §14 Language | English source, Arabic catalog and native RTL-compatible views/statusbar |
| OD-02 Qiwa handoff | Explicit pending handoff hook only; actual batches deferred under the user's Phase 1 scope |
| §7–11 / OD-03–07 | Muqeem/Morro/Services processing, payment, direct JV, imports and deferrals deferred |
| §16.1 / OD-11 | Dashboard deferred; forecast-method open item retained |

## Decisions made explicit

One active default mapping per company. Initial choice: three-month Work Permit renewal.
No assumed Iqama number checksum; nonblank identity plus valid expiry is the Phase 1 check.
No currency conversion or invented tax/account mapping from a workbook with no such columns.
Source costs of 1 and source spelling are retained for business review.
Other companies configure their own costs/mappings. Company automation stays disabled until
configured. Full old-source comparison remains unavailable because that archive was not supplied.
