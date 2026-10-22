## Validation

- Full regression run: 141 tests passed during integration.
- Final focused release tests: all 16 resident tests passed on both the upgraded database and a fresh installation without the optional deferred-account addon.
- Actual Apps-style immediate upgrade from the Services release passed.
- Original 6,852-row workbook: full preview passed; three temporary matching employees applied successfully, with other rows retained as blocked. Validation was rolled back.
- Python/XML/manifest/translation and ZIP integrity validated by the packaging tool.
- No live database, installed addon or original workbook changed. No actual external emails sent. Browser visual/RTL acceptance and SMTP delivery remain checks in the user's environment.


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

# Category filter validation - 13 October 2026

Release **19.0.3.0.6**: 91-test regression run: 90 passed, one settings test failed because its test user lacked Saddad Admin. Corrected the fixture; targeted settings test then passed (0 errors). No runtime changes were needed for that correction. Coverage includes category descendants, renaming, changed-line validation, company settings persistence/switching and preservation of posted expenses. Logs: category_filter.log, category_settings_retest.log. Translation template regenerated and Arabic catalog complete. User database unchanged.

# Product deferred accounts - 13 October 2026

Release **19.0.3.0.5**. With supplied optional addon installed: **89 tests passed, 0 failures/errors**, product_deferral_final.log. Final code without addon: 27 Muqeem tests collected, 23 passed, 4 optional integration skips, 0 failures/errors (product_deferral_fallback_final.log). Covers product/category/parent/company precedence, no company default when product configured, two products with distinct accounts, non-current assets, cross-company rejection, invalid-account rollback and posted override locking. Supplied addon's missing category helper bypassed only for Saddad. Package syntax/XML/manifest/catalog/ZIP checks passed. User database and supplied ZIP unchanged.

# Inclusive end-date validation - 12 October 2026

Release **19.0.3.0.4**: **85 tests, 0 failures, 0 errors** on isolated Odoo Enterprise (inclusive_dates.log). Coverage includes 3/6/9/12-month defaults, leap years, mid-month and month-end starts, onchange parity, explicit overrides and three recognition entries plus one transfer for December-February. Existing posted schedules are unchanged. Package validation passed.

# Prepayments fix validation - 12 October 2026

Release **19.0.3.0.3**: isolated Odoo Enterprise upgrade completed with **83 tests, 0 failures, 0 errors** (prepayments_fix.log). Added full native schedule coverage with a Prepayments holding account and invalid account-type rollback coverage. Existing Current Assets schedule tests remain passing. Package Python/XML/manifest and 673 translated terms validated. User database was not modified.

# Direct PTR handoff validation — 12 October 2026

Release **19.0.3.0.2**. Isolated Odoo 19.0+e-20251217 upgrade:
**81 tests, 0 failures, 0 errors**, ptr_muqeem_final.log, 08:17:13 UTC.
Nine added regressions verify automatic Iqama creation, confirmed cost/date snapshots,
explicit old-request preparation, idempotence, authorization, immutable sources, mixed
service routing, atomic rollback, unchanged work-permit-only behavior, source read access
and completing the direct expense through payment/posting. Existing 72 tests also pass.
Arabic handoff status, preparation action and source label were checked after loading the
final catalog. **673/673** terms translated. Package syntax/XML/manifest/translation and
ZIP byte-integrity checks pass. No user database modified; no new browser RTL visual pass.

---

# Manual PTR preview validation — 12 October 2026

Release **19.0.3.0.1**. Isolated Odoo 19.0+e-20251217 upgrade validation:
**72 tests, 0 failures, 0 errors**, ptr_preview_tests.log, 07:54:02 UTC.
Two added native Form regressions verify Iqama number, expiry, remaining days and department
before saving, save-time snapshot validation, employee switching, clearing and missing master
values. Existing PTR/Qiwa/Muqeem tests also passed. No user database was modified.
No new translated strings or dependencies; the 654-term Arabic catalog remains complete.

---

# Muqeem validation — 11 October 2026

Release **19.0.3.0.0**, technical module **Saddad**.
Validated with the user-supplied Odoo **19.0+e-20251217** Enterprise runtime,
PostgreSQL 18.1 and Python 3.12.3, in isolated databases on port 55439.
The user's installed Odoo databases, addons and services were not modified.

## Final results

- Upgrade from the accepted Qiwa release: **70 tests, 0 failures, 0 errors**.
  Final log: muqeem_final.log, 11 October 2026 at 06:40:41 UTC.
  Odoo's fixture statistics count 78 entries; there are 70 test methods.
- Clean installation: **70 collected, 69 passed, 1 skipped**, no failures/errors,
  muqeem_fresh.log at 06:39:08 UTC. The skipped check requires activated Arabic.
  The subsequent upgrade suite ran that Arabic check successfully. Final navigation
  and accounting-lock refinements are included in the successful upgrade suite.
- Separately loaded the final Arabic catalog and verified translated Muqeem states,
  posting action, deferral field labels, native statusbar/list architecture and RTL
  language metadata. No full browser visual RTL pass is claimed.
- **654/654** exported strings have Arabic translations. Source export excludes the
  older installed Saddad folder, so only the delivered module's code is included.
- All previous foundation/Qiwa regressions remain. Eighteen new Muqeem methods cover
  full approvals, configurable company overrides, permission/RPC guards, rejection,
  partial payment and reversal, journal restrictions, company isolation, notifications,
  native form entry, VAT posting, employee-loan accounts, missing-account rollback,
  Qiwa consolidation/idempotence, duplicate/posted-entry protections, native deferred
  schedules, day/month/full-month calculations, penny rounding and scheduled posting.
- Python syntax, XML/list-view conventions, manifest files, translation completeness
  and byte-for-byte ZIP integrity are checked by package_saddad.py.

## Scope of verification

All accounting tests use synthetic records and transaction rollback. No real bank
transfer, SMTP delivery, payroll recovery, multi-session stress run or posted expense
reversal was executed. No PDF source documents or employee identities are packaged.

Early runs exposed a mixed-build test setup, a changed Odoo account active-field API,
and a penny rounding case in full-month deferrals; these were resolved before final
validation. Expected duplicate-key/access errors are deliberately triggered by tests
and are not failures. The previously delivered PDF samples remain covered by the parser
regressions; the three original PDF end-to-end checks are documented below historically.

---

## Prior releases (historical)

# Validation — 10 October 2026

Release **19.0.2.0.1**, technical module **Saddad**.
Isolated Odoo 19.0-20251124 / PostgreSQL 18.1 / Python 3.12.3.
The user's installed Odoo database was not modified.

## Current release results

- Upgraded the isolated Qiwa database; all updated views compiled successfully.
- **52 test methods, 0 failures, 0 errors**, pdf_final_tests.log, 11:01:40 UTC.
  Odoo fixture statistics count 58 entries; the actual suite contains 52 test methods.
- All three original supplied PDFs passed extraction, application, review and confirmation:
  unpaid: 1 employee / SAR 2,425; paid: 4 employees / SAR 9,700;
  paid: 8 employees / SAR 19,400. Verified distinct SADAD/invoice references, issue dates,
  paid payment dates versus unpaid due date, employee matches and totals.
  Transactions were rolled back so private employee IDs and documents were not retained.
- Six new regressions cover paid workflow/date guards, print-footer removal, distinct
  issue/export dates, unknown status, alternate row order and PDF-total mismatch blocking.
- **522/522** exported terms translated into Arabic; no new dependencies.
- Source syntax, XML, manifest, translation completeness and ZIP integrity checked by
  the packaging tool. Sample PDFs, private data and local test infrastructure are excluded.

## Limitations

Arabic raw text can remain garbled where the PDF font encoding is damaged. Structured
fields must still be reviewed against the source. Unknown layouts and scans are not OCR'd.
Reported Paid status never records payment or posts accounting. Muqeem remains a later phase.
The current views compiled and native form tests passed; no new full browser RTL visual
pass is claimed. The prior browser check and its cached-asset limitation are recorded below.
A first run encountered an old demonstration record in a different test database; the
final suite used the clean isolated Qiwa database. A header date edge case found by the
new tests was fixed before the successful final run.

---

## Previous release validation (historical)

# Validation — 8 October 2026

Release: **19.0.2.0.0**, technical name **Saddad**.
Environment: isolated Odoo 19.0-20251124, PostgreSQL 18.1, Python 3.12.3.
The user's installed localhost:8070 database was not modified.

## Executed results

- Upgraded the existing accepted-foundation test database to Qiwa successfully.
- Final regression result: **46 tests, 0 failures, 0 errors** in qiwa_final.log
  (8 October 2026, 04:58:51 UTC). Fixture statistics report 52 entries, not 52 test methods.
- A separate clean installation completed and passed the then-current **42-test** suite
  in qiwa_fresh.log. Four subsequent tests added backfill, currency/identity mismatch,
  mixed periods and native form coverage; all passed in the final 46-test upgrade run.
- Final import-dialog label change loaded and compiled successfully in a subsequent
  isolated module upgrade (qiwa_views_final.log); no business logic changed afterward.
- Original supplied Qiwa PDF passed extraction with Odoo's own PDF engine. The complete
  wizard extract-and-apply path also passed: invoice and SADAD references stayed distinct;
  issue/payment/permit dates, employee, three-month period and 2,425 fee were correct.
  The source document and matched identity were rolled back from the test database.
- **502/502** Odoo-exported terms translated, including the original 196 product names.
  Final export includes the new import-review label and extracted-text heading.
- Python/XML/manifest/translation checks and ZIP byte-integrity checks are performed
  by package_saddad.py. Only module files are distributed; no test database, credentials,
  source PDF, logs or extracted private document text are included.

## Coverage

The 25 foundation tests remain, plus 21 Qiwa tests covering: protected workflow and
cost snapshots; authorization and configurable approvals; normalized reference uniqueness;
duplicate employee prevention; external fee explanations and positive amounts; invalid
and expired dates; empty batches; atomic PTR creation/linking; multi-employee consolidation;
company boundaries; invalid targets; immutable PTR origins; stale employee/mapping checks;
email queue and activity completion; local PDF extraction/application; invalid documents;
ambiguous/unmatched identities; updates of existing PTR-linked lines without duplication;
changed-file checks; currency/identity mismatch; mixed-period parsing; native form entry;
and explicit idempotent legacy-confirmed-PTR backfill.

Duplicate-key and access-denied messages are deliberately provoked by protection tests.
They are expected and are not failures.

## UI checks and limits

English Qiwa form and import dialog were inspected in the browser. Arabic labels,
status text and the review acknowledgement appeared correctly. The test browser retained
LTR positioning while loading cached RTL assets; regenerating its assets then stalled
page loading. Therefore a complete visual RTL pass is **not claimed** for this release.
Views use standard Odoo list/form/statusbar structures with no custom directional CSS.
Confirm Arabic mirroring on the target server with its standard rtlcss setup after upgrade.

No real SMTP delivery, parallel-session stress test, or broad set of Qiwa PDF templates
was tested. The supplied text PDF layout is supported; unknown layouts require manual
review/completion, and scanned/encrypted PDFs are not supported. Limits are 10 MB,
40 pages and 250,000 extracted characters. PDF values never approve or pay a request.

The actual Muqeem expense/payment/accounting integration is deferred to the next phase.
A confirmed Qiwa batch explicitly shows Pending Muqeem Phase. No automatic backfill
or reseeding of existing prices/configuration runs during upgrade.



