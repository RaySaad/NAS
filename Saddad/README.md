# Saddad 19.0.6.0.1 — Resident display and navigation

- Replaced the employee Muqeem tab's single-row table with read-only fields grouped into Resident Details, Employer and Report, Iqama Dates, and Passport and Work Permit. These display the same resident profile; no duplicate data store or migration is introduced. Open Muqeem Profile provides access to history and the reviewed expiry action.
- Employer Number is visible on the employee tab and resident list/form, and searchable in the resident screen.
- Muqeem menu groups Muqeem Expenses, Muqeem Expense Lines, Muqeem Residents and Resident Imports.
- Renewals menu groups Pending to Renew and Iqama Renewal Follow-up. Existing menu IDs, actions and role restrictions are retained.
- Expiry review now distinguishes Current Employee Expiry from Imported Muqeem Expiry. Older imported dates show a warning and are rejected before opening the confirmation wizard; the existing server-side protection remains. Imported history is preserved rather than rewritten with a renewed employee date.
- English/Arabic labels updated. Version 19.0.6.0.0 remains preserved as an earlier ZIP.


# 19.0.6.0.0 — Muqeem Resident Management

Resident profiles, Excel import preview, renewal confirmation safeguards and 7/30-day work-permit follow-up alerts. See [Resident Management](RESIDENT_MANAGEMENT.md) for setup, operation and limits. Live API execution awaits Elm documentation.

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

# Saddad — Odoo 19 Enterprise

Version **19.0.3.0.2**. Technical module **Saddad** (capital S).
Fresh implementation of the approved Rev. 2 design: foundation, PTR, Qiwa and now Muqeem.
The original logo and 196 workbook products are preserved. Morro, Saddad Services and
the dashboard remain later phases.

## Upgrade

1. Keep a backup of the existing module folder and database. Replace the complete `Saddad`
   folder with this ZIP's folder in the active addons directory; avoid leaving old source files.
2. Use Odoo 19 Enterprise with `account_accountant` available. This release explicitly
   depends on its native deferred-expense fields and calculation helpers.
3. Restart Odoo and upgrade Saddad in Apps. Do not uninstall the accepted module.
4. Assign the required Muqeem roles and configure accounting below before posting.

No automatic historical posting, payment marking, Qiwa backfill or price reseeding runs
on upgrade. Already-confirmed Qiwa batches have an explicit **Prepare Muqeem** action.
New Qiwa confirmations automatically create one consolidated Draft expense. Repeating
Prepare Muqeem returns the same expense. The Qiwa PDF's Paid status never marks its lines paid.

## Required setup

- Saddad Settings: default Bank/Cash Journal and Employee Loan Account, separately per company.
- Bank/Cash Journal: active, company currency, with a valid default bank/cash account.
- Service products or categories: expense accounts. Amounts initially use product Cost;
  confirmed Qiwa source amounts, employees, products and periods remain fixed.
- Accounting Settings: Deferred Expense Account (current asset), Deferred Expense Journal
  (general), and computation method Days, Months or Full Months.
- VAT is optional; select configured purchase percentage taxes and their repartition accounts.
  No tax is invented or seeded. Cash-basis, grouped, negative and non-percentage taxes are
  deliberately rejected by this release. Company currency only; no foreign-bank conversion.
- Approval Rules: company overrides for each Muqeem transition, with email/activity switches.
  A custom approval group must also carry Muqeem Access to open the records.

## Muqeem workflow

Draft → HR Assistant → HR Confirmed → Financial Approval → GM → Payment → Done → Posted.

| Step | Default role |
|---|---|
| Create, Submit, HR Assistant review, reset Rejected | Muqeem User |
| HR approval or rejection | Muqeem HR |
| Finance approval or rejection | Muqeem Finance |
| GM approval or rejection | Muqeem GM |
| Choose bank journal, mark/reverse unposted Paid lines | Saddad Payment |
| Post the consolidated journal entry | Muqeem Post |

The HR Assistant step defaults to Muqeem User because Rev. 2 does not define a separate
assistant group. It has its own configurable rule. Rejection requires a reason and is
available at the four approval stages. Reset is available only for Rejected expenses.
Expense details and deferral dates are editable in Draft; submission locks them for approval.
Actor/time, rejection reason, transitions and payment actions are retained in chatter.
Action-required notices queue email and Odoo activities to the next configured group.

Partial payment leaves the request in Payment. All lines must be Paid before Done, and
only Muqeem Post can post. Payment marks do not create journal entries. Unposted payment
marks can be reversed; the request returns to Payment. Reverse all marks before changing
its bank journal. Posted reversals/cancellation are intentionally unavailable pending a
separate linked reversal design; independent accounting resets/deletions are blocked.

## Accounting and deferrals

One direct `account.move` journal entry per expense, without a vendor bill or account.payment:
company-paid lines debit their product/category expense account, employee-paid lines debit
the company employee-loan account, tax lines use tax repartition accounts, and the consolidated
credit uses the selected bank/cash account. A receivable loan account requires an employee
work contact. The source expense and each line retain journal links; duplicate posting is blocked.
This records the accounting of payment; it does not execute a bank transfer or payroll recovery.

Enable Defer Expense on eligible company-paid lines. Start defaults to the employee's Iqama
expiry; end defaults to start plus the selected 3/6/9/12-month period. Review and edit these dates
in Draft, particularly if a different applicable expiry is needed. Nothing is deferred merely
by approving the request or marking lines Paid.

After Muqeem reaches Posted, the adapter uses Odoo 19's native deferral periods and expense
amount calculations. It creates the initial expense-to-deferred-account transfer and monthly
recognition entries linked through Odoo's native deferred-entry relationship. Due entries are
posted; future entries use Odoo's standard `auto_post=at_date` schedule. Company method and
currency precision are respected; final allocation is capped/adjusted to avoid negative penny
residuals. Same-month lines follow the native no-deferral behavior. Missing configuration rolls
back the whole posting transaction. Journal Entry and Deferred Entries buttons expose the audit trail.

The native invoice generator infers revenue for a plain journal entry, so this adapter explicitly
uses its **expense** calculation direction rather than pretending the direct JV is a vendor bill.
Saddad generates its own per-expense schedule regardless of the company's invoice batching mode.

## Access and company behavior

All transactions, lines, employees, accounts, taxes and journals are checked against the company.
Protected actions are enforced on the server; direct field updates cannot bypass approvals,
payment or posting. Transaction locks and unique Qiwa links prevent duplicate handoffs/posting.

Muqeem roles imply Muqeem Access, which currently implies Odoo HR Officer to read the private
employee data used by this app. This is broader HR access and should be considered when assigning
roles. Muqeem Post also implies Accounting Read-only for journal inspection, not general accounting
write access. Posting uses a narrow internal escalation after process-specific authorization and
validation. Saddad Admin configures rules/settings but does not automatically receive all approval roles.

## Existing foundation and Qiwa

- Gregorian Iqama expiry, Umm al-Qura Hijri display and computed remaining days; supported
  Hijri conversion range 1924-08-01 through 2077-11-16.
- PTR Draft/Reviewed/Confirmed, configurable 30-day expiry threshold, daily creation/cleanup,
  opt-in company automation, mapped product Cost and configurable default PTR mapping.
- Eight initial Iqama/work-permit mappings for 3/6/9/12 months; seeds use `noupdate`.
- Workbook catalog: 29 Muqeem, 166 Morro and one Saddad Service product. Source cost values
  and spelling remain for business review; no currency/tax/account assumptions were seeded.
- Qiwa multi-employee batches, distinct SADAD/invoice references, paid/unpaid document dates,
  reviewed PDF staging, employee identity matching, total reconciliation and original attachment.
- PDF limits: 10 MB, 40 pages, 250,000 characters; text PDFs only. No OCR/encrypted-PDF support.
  Some raw Arabic remains garbled due to embedded font encoding; verify against the original.
- English and Arabic catalogs; native list/form/statusbar structures without directional overrides.

See IMPLEMENTATION.md, VALIDATION.md and RECONCILIATION.md for scope and actual validation.

## Manual PTR preview fix — 19.0.3.0.1

Selecting an employee on a Draft PTR immediately previews the employee's Identification No.,
Iqama expiry and remaining days. Switching or clearing the employee refreshes/clears these
values. Department continues to come from the employee's department. Missing employee master
values remain blank and the existing save-time validation still requires valid Iqama details.
Server-side snapshots and workflow locks remain authoritative; no historical PTR is rewritten.

## Direct Iqama PTR → Muqeem — 19.0.3.0.2

Confirming a PTR automatically creates one Draft Muqeem expense for its Iqama service lines.
The employee, products, periods and reviewed amounts are copied from the confirmed PTR;
deferral dates default from its expiry snapshot. These source values and links are protected.
The expense still requires its normal approvals, explicit payment marking and posting.

For a PTR already Confirmed before this upgrade, an authorized PTR confirmer can use
**Prepare Muqeem**. Repeating that action opens the existing expense, even if already posted.
No automatic historical conversion runs during upgrade. Pre-existing manually created expenses
are not automatically matched or linked by this action.

The PTR's **Muqeem Expenses** button opens its direct expense and any expense reached through
Qiwa. Muqeem shows **Source PTR**, with a source line reference available in optional columns.
Iqama-only confirmed requests display **Not Applicable** for Qiwa in the form and list.
Work-permit-only requests still go through Qiwa; mixed PTRs send Iqama lines directly and work
permit lines through Qiwa, producing separate expenses for those two routes.
Muqeem roles can read PTR records within their allowed companies but gain no PTR confirmation rights.
