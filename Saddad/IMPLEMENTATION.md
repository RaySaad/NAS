Fresh installation succeeded (services_clean_install.log). Clean database Services workflow run: 18 collected, 17 passed, one Arabic check skipped because Arabic was not active; no failures/errors (services_clean_tests.log). Arabic validation passed on the upgraded database. Final package contains 58 files and 778 translated terms.

# 19.0.5.0.0 — Saddad Services

Saddad Services adds the approved Draft > Reviewed > Financial Approval > GM > Pending Payment > Done / Posting Ready > Posted workflow. Service User submits and reviews; Service Finance and GM approve/reject their own stages; rejected requests reset to Draft through the configured reset role. Saddad Payment controls bank/cash journal selection and line payment marks; Service Post posts the direct journal entry. Approval rules can be overridden per company. Administrators do not automatically hold every approval role.

New Billers master data under Saddad > Configuration > Billers: translated name, code, partner, company and archive control. Codes are unique per company. Saddad Admin maintains billers; Services roles have read-only access. A request requires a description and biller. Lines hold service product, invoice/reference number, optional description, amount, VAT, analytic account and supporting document. Employee selection is not required for general services. Attachments also remain available through request chatter. No invented biller seed data or automatic old-module record migration.

Saddad Settings > Saddad Services Product Category is company-specific, defaults to the existing seeded service category and includes descendants. Only active service products available to the company can be selected; new/edited lines enforce the same rule. Product Cost supplies the initial editable amount. Existing Muqeem and Morro category settings remain independent. The shared Default Bank / Cash Journal is used; billers must be configured before service requests can be created.

Untaxed, VAT and total amounts are calculated with native Odoo tax computation, including tax-inclusive prices. Supported taxes retain the existing Saddad scope: non-negative percentage purchase taxes due on invoice. Group, fixed, cash-basis and negative taxes are not supported by this direct-JV flow. Payment is recorded per line; partial payment remains Pending Payment, all paid moves to Done. Posting creates one balanced account.move journal entry with service expense debits, tax repartition lines/tags and bank/cash credit. The expense lines carry the biller partner and optional analytic allocation. No account.payment or external bank transfer is created. Reposting, independent reset/cancellation/reversal, deletion and economic edits of posted entries are blocked. Reversal workflow remains a later enhancement. No Services deferrals are introduced.

Email and Odoo activities route to the next configured role, with the correct state in the recipient language and a direct link. Completed-stage activities are closed. English/Arabic catalogs cover new fields, views, statuses, validations and notifications. Native list views/statusbars preserve Odoo direction handling; browser RTL acceptance and real SMTP delivery remain user-environment checks.

Validation: full isolated Odoo 19 Enterprise regression suite passed **131 tests, 0 failures, 0 errors** (services_regression.log), including 18 Services tests for workflow/roles, reset, payment, journal guards, category configuration, biller access/company/uniqueness, VAT-inclusive posting, analytics/attachments, recipient-language notifications and Arabic views/stages. Apps immediate-upgrade method passed against a pre-Services database (services_frontend_upgrade.log). Original supplied source files, installed addons and user database were not modified.

Upgrade: replace the complete capital-S Saddad folder, restart Odoo, then Upgrade; do not uninstall. Configure Billers, Services Product Category and accounting defaults; assign Saddad Service User / Finance / GM / Post and Saddad Payment roles. This full release includes all previous PTR, Qiwa, Muqeem and Morro work. Optional product deferred-account addon remains optional. Dashboard implementation and final user acceptance remain after this phase.

Clean-install workflow check: 22 Morro tests collected; 21 passed and one Arabic-language check skipped because Arabic was not active on the fresh database. Arabic checks passed on the upgraded database. No failures or errors (morro_clean_tests.log).

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

# Patch 19.0.3.0.2 — Complete the Phase 4 Iqama handoff

Direct Iqama PTR → Draft Muqeem is implemented, with source-preserving amounts/dates,
duplicate protection, role checks and two-way navigation. Existing confirmed PTRs use
Prepare Muqeem; new confirmations create the expense automatically. No approval, payment,
posting or employee-expiry update is inferred from confirmation. Work permits remain on
PTR → Qiwa → Muqeem. Mixed requests use both routes without copying work-permit lines twice.
All 81 tests passed. Upgrade using the complete Saddad folder; do not uninstall.

---

# Patch 19.0.3.0.1 — Manual PTR preview

Employee selection now previews Iqama details immediately in a Draft PTR. Previously these
snapshots were assigned only when saving. Clearing/changing the employee clears or replaces
old values. Missing employee master data remains blank; saving still enforces valid data.
No records are backfilled and approval/accounting behavior is unchanged. Upgrade instructions
remain the same. Full 72-test regression suite passed.

---

# Muqeem implementation — 19.0.3.0.0

Adds consolidated Qiwa-to-Muqeem handoff and manual expenses; configuration-driven HR,
Finance and GM approvals; rejection with reason; separate line payment marking and direct
journal posting; VAT and employee-loan debit routing; native Odoo Enterprise deferral
calculations/schedules; bilingual views, activities, email queue and company boundaries.

The ZIP includes the entire accepted foundation and PDF importer, not only changed files.
No user database was modified during development. Upgrade the module; do not uninstall it.
Enterprise `account_accountant` is now required. Configure journals/accounts and assign
Muqeem roles before using the new workflow; details are in README.md.

## Explicit design choices and remaining items

- HR Assistant defaults to Muqeem User through its independent configurable approval rule.
- One Qiwa batch creates one Draft expense; existing confirmed batches need Prepare Muqeem.
- All required lines must be Paid before posting. No automatic bank transfer or payroll recovery.
- Posted cancellation/reversal needs a future linked reversal workflow; ordinary unposted
  payment-mark reversal is included. Independent reset/delete of linked accounting is blocked.
- Company currency and ordinary non-negative purchase percentage VAT are supported. Other
  tax types are rejected instead of being posted with an assumed treatment.
- Deferred dates are editable in Draft and locked with the approved amounts after submission.
  No employee expiry is automatically advanced by posting; the spec did not authorize that update.
- Native deferral calculations are reused for direct JVs. Per-expense schedules are generated
  after Posted, even if invoice deferrals elsewhere are configured for grouped generation.
- Morro, Saddad Services and dashboard remain out of this phase. Traffic forecast definition
  remains open for the dashboard phase.
- Muqeem roles currently include HR Officer access; posting includes Accounting Read-only.
  Full browser RTL rendering and real SMTP delivery were not revalidated for this release.
