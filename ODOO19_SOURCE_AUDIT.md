# Odoo 19 migration verification

Employee header / contacts API follow-up (2026-10-14): verified the Odoo 18
header displayed `job_title` below the employee name. Restored that existing
field in the 19.0 header (including Arabic values) and positioned the native
image upload widget on the right, retaining presence/chat controls and the
editable Job Title detail row. No employee field or stored value was added or
changed. Odoo inheritance/selector checks and Enterprise Payroll composition
pass. The UI patch is not yet installed on the running database or browser-
verified. Current source/offline suite: 33 passing checks.

Compared all ten `contacts_ext` routes against `NAS_old`: contact/company CRUD,
countries/read and states/read remain. Eight JSON routes were renamed jsonrpc;
nine body parsers use the flat/JSON-RPC compatibility helper. An AST regression
normalizes only those changes and confirms all remaining controller statements
match. No contacts controller code was edited during this follow-up.

Live curl work completed before this header follow-up: all 24 endpoints were
exercised successfully with test payloads, and all nine JV types created draft
entries 18666–18674 in `naass_test_19.0_2026_10_06_16_05`. Read-only verification
confirmed company 1 and debit=credit=10 for each. The first section read found
no sections; it passed after fixture creation. Department create initially
failed for omitted manager/non-numeric CRM values; explicit unassigned lookup
keys plus numeric CRM passed without API code changes. All 64 missing/invalid-
token curl checks passed. These are representative endpoint tests, not
exhaustive accounting/posting/security certification.

Only separately created delete-test employee/department/section/company and
the unused test contact were deleted through the APIs. They can be recreated
from the prepared test JSON; no pre-existing records were deleted. The primary
test company, subscription, employee, department, section and nine linked draft
JVs were retained for inspection. Curl run ID: `20261014-mv80eqrn`.

API test-code handoff (2026-10-14): added `tools/test_nas_apis.py`, fixture
configuration and `tools/NAS_API_TESTING.md` for database
`naass_test_19.0_2026_10_06_16_05`. The runner discovers all 24 current routes,
checks authorization/validation, and provides explicit write-mode CRUD plus all
nine JV types/batch creation with independent read-back/balance checks. Existing
master-data codes must be configured; it does not seed or alter production
configuration. Write mode requires matching test DB confirmation. Owned CRUD
fixtures are deleted; test draft JVs are retained and listed in the report.
No requests to the user's server were executed while preparing this harness.
Six offline runner checks pass; the combined source/isolated suite has 32
passing tests. This does not certify an HTTP/API run or every business edge case.

Account API preservation update (2026-10-14): at the user's request,
`account_ext/controllers/jv_api.py` now matches `NAS_old` statement-for-statement
except the required `json` to `jsonrpc` route-type rename. Restored original
raw JSON parsing and hardcoded `account.1_sale` / `account.1_general` references;
removed the added active-company journal selector. Authentication, validations,
JV branches, journal searches, accounting values and responses are unchanged.
An AST equality regression enforces this scope. This intentionally retains
legacy configuration/company assumptions, not general multi-company safety.
No database or external API calls were made for this update.

Employee tab follow-up (2026-10-06): restored Resume-first navigation,
Work Information / Private Information labels, Employee Sector under Settings
Status, and the Iqama label in Citizenship. Added native `study_school` and
`private_car_plate` controls omitted from the default 19.0 form; no new storage
or data changes were introduced. Kept the 19.0 contract/payroll controls, salary
adjustment extension anchors, approvers and multi-bank allocation UI rather
than replacing them with the old native forms. Legal Name / Payslip Language /
Disabled remain in Personal; Registration Number remains in native Payroll
(Reference, subject to native group visibility).

The offline layout check now applies Enterprise Payroll inheritance before
the customization and asserts retention of its personal/payroll fields and
contract controls. This is view-composition/selector validation, not payroll
workflow certification or visual browser validation. The running database has
not been upgraded with these latest view changes.

Employee layout follow-up (2026-10-06): restored a named two-column employee
details section above the native tabs. Email/phone/mobile/tags now have labeled
rows; Employee Code is no longer inside the phone header. Custom work details,
job and manager fields are on the right. Native tabs, version timeline and the
organization-chart anchor remain. Odoo's selector validator and inheritance
engine checks pass, as do all 25 source/isolated regressions. This UI patch was
not installed on the user's database or visually verified in a browser.

The supplied screenshots show Employee Sector 2 versus 1 for the same employee.
No data was changed by this layout patch. Compare the source database/backup
before correcting this value; matching fields do not prove migrated data.

Updated 2026-10-01: source comparison, isolated installation and runtime tests
have been completed. This is not certification of a live Odoo 18 database
upgrade or every business workflow. No production database was modified.

### Contact layout follow-up (2026-10-05)

2026-10-06 correction: replaced forbidden translated `@title` selectors with
`hasclass('fa-envelope')` / `hasclass('fa-phone')` selectors. The layout checker
now runs Odoo's `_valid_inheritance` selector validation as well as applying
inheritance, and verifies that a deliberately invalid `@title` selector fails.
This corrects a gap in the previous engine-only check. Latest run: 18 tests pass,
four backup-comparison tests skip because `NAS (copy)` is no longer available.
No running database was modified for this correction.

Settings follow-up: a database settings view calling the removed
`iap_action_view_my_services` method can fail validation while loading the HR
settings extension. Added an explicit `iap` dependency and a compatibility
method returning the native Odoo 19 `iap.iap_account_action`. It keeps older
stored views usable until the core IAP XML is upgraded; no core file or database
view was overwritten. Removed the inapplicable `type="object"` attribute from
the token field. Isolated action delegation passes; current source/isolated
suite: 19 pass, four backup-dependent checks skipped. This database-specific
upgrade was not executed here.

Employee storage follow-up (2026-10-06): compared the current customization with
the now-available sibling `NAS_old` and local Odoo 18/19 HR sources. Odoo 19
delegates `identification_id` and `marital` from `hr.version`; legacy direct
employee definitions incorrectly shadowed that storage. Both now explicitly
use writable, non-stored `version_id` related fields with `inherited=True`.
The native version model keeps the custom required marital default and `other`
choice. Custom `employee_code` remains required/unique/stored on the employee;
sector values 1–5, views, API names and remaining custom fields are retained.

Source/isolated suite: 25 passing tests, including backup comparisons against
`NAS_old`. Added a registered Odoo ORM test for Iqama/marital writes through to
the version and preservation of employee code/sector; that new database test
has not been run here. No database values or legacy columns were changed.
For an existing upgraded database, verify native HR version data and retained
legacy employee columns before any data cleanup: source corrections alone do
not certify that historical Odoo 18 values were migrated.

Restored VAT and custom contact fields to the left column below the address,
and phone/mobile/email to the right column. Kept Odoo 19's native title/image
structure. Removed the repeated Mobile 2 occurrence outside the groups and
anchored Subscription insertion to the main notebook instead of every page.
No stored fields, values or voucher buttons were removed.

The current contact inheritance was applied to the local Odoo 19 parent with
Odoo's real inheritance engine (without starting a database). Column membership,
Mobile, a single Mobile 2 and Subscription page are asserted. The suite now has
22 passing source/isolated checks, including preservation of the old voucher
button labels/types. The previous installation/runtime results below predate
this UI-only follow-up; the running user instance was not upgraded in this pass.

## Runtime results

Using the local Odoo 19 Community/Enterprise sources and Python 3.12 environment:

- All 23 custom addons installed on `nas_odoo19_verify_20261001_01` with demo
  data, and independently on empty `nas_odoo19_verify_20261001_02` without demo.
- Updating all custom addons with their registered tests returned exit code 0:
  **33 tests, 0 failures, 0 errors**. Coverage includes OU access, company
  defaults, invoice/payment posting, cross-OU balancing, cash-basis line
  preparation, purchase security, stock access and extended view inheritance.
- All seven OU report layouts render; a regression covers bubble-layout OU
  headers when the company header is blank.
- `tools/odoo19_runtime_smoke.py`: **19 passing checks** against real ORM records.
  Includes balanced journal posting/custom dimensions, employee search/gender
  compatibility, both prepaid expense journal modes and approvals, petty cash
  with/without 15% tax, and individual/full employee statements.
- Four XLSX exports generated and opened successfully: both voucher exporters,
  individual employee statement and full employee statement.
- Seven report actions generated actual PDFs with wkhtmltopdf: journal entry
  reports, voucher, customer statement, both employee statements and petty cash.
  Separate journal printing produced a ZIP containing two valid PDFs.
- Local HTTP login returned 200; flat JSON and JSON-RPC contact requests both
  dispatched and rejected missing authorization as expected. Authorized API
  CRUD, all API endpoints and browser interaction were not exhaustively tested.
- Smoke fixtures were rolled back. The temporary localhost server was stopped;
  the two verification databases and temporary logs were retained.

Runtime repairs additionally covered Odoo 19 Command imports, removed default
user templates (preserving the legacy template when present), report XPath and
bubble-header conditions, search-view schema/menu changes, mapping company
fields and deprecated `_context` access. Payment/stock/cash-basis fixtures were
adapted without weakening assertions; partial-registry tests run post-install.

Evidence: `/tmp/nas_odoo19_verify_20261001.jAZV5j/tests_final.log`,
`fresh_no_demo.log`, `smoke.log` and `http.log`. Smoke PASS details are printed
to stdout by the repeatable script, not stored in `smoke.log`.

## Preservation

Compared the current repository against the sibling `NAS (copy)` directory.
All 353 non-cache backup files remain present. Regression checks confirm that
the original custom Python field definitions, SQL constraint definitions, and
API routes remain available. The current folder's newer clearance JV workflow,
employee project/OU mapping and cron, partner-ledger customization, Excel lookup
caches, and individual PDF/ZIP printing have been retained.

The backup is older than the current code; differences are not automatically
regressions. In particular, the current petty-cash move header/counterpart OU
behavior and current journal selection customization were not reverted.

## Repairs

- Migrated user groups to `group_ids`/`all_group_ids`, group users to `user_ids`,
  and security categories to Odoo 19 privileges, retaining existing group IDs.
- Repaired the user-defaults `fields` shadowing bug and Odoo 19 `name_search`
  keyword/domain handling, including legacy `args` callers.
- Declared missing customization and Accounting/Fleet bridge dependencies.
- Adapted the account-type dropdown to Odoo 19 sections/groups and analytic OU
  filtering to the frontend many2one object and many2many domain format.
- Updated deprecated JSON routes and QWeb `t-esc`; retained flat API bodies
  while also accepting standard JSON-RPC `params`.
- Retained contact `mobile`; exposed legacy employee `gender` through Odoo 19
  `sex`. Fresh-record runtime behavior passes; upgrading existing native HR
  version/data storage remains unverified.
- Account API journal selection was originally adapted, then restored to its
  production hardcoded behavior at the user's request on 2026-10-14 (see above).
- Repaired prepaid bill linkage, company/nature assignment and propagation of
  employee, operating-unit, contract and analytic dimensions.
- Repaired per-line expense entries so lines do not accumulate into subsequent
  entries and every created entry is posted; included explicit company IDs.
- Repaired petty-cash batch creation, default account return value, split-tax
  duplication and project-mapping batch deletion protection.
- Fixed the purchase search XPath and OU report fallbacks when no OU is set.
- Implemented the full employee statement PDF button and landscape report.
  Replaced its deprecated aggregation API with `_read_group`, retained opening
  balances/period totals and scoped the report to its company.
- Preserved both voucher export layouts by separating colliding button methods.
  Added composite analytic-key handling and repaired the large-voucher workbook
  total/balance formulas.
- Preserved Excel lookup caches and employee-linked dimension precedence;
  supported normalized headers and textual account codes with leading zeros.
- Restored context-inheritance assertions using an explicit test fixture instead
  of silently removing demo-dependent assertions.

## Verification

Latest source-only results: 23 custom modules, 141 module Python files and
71 XML files checked against 58 dependency modules, with zero findings in the
static audit. All 20 Python source/isolated-method tests and the JavaScript patch
checks pass. The inherited-view inspection covered 66 explicit XPath expressions;
the one unmatched purchase-search XPath was repaired. Git's whitespace check
passes using its CRLF-aware setting.

Run with Python 3.12 or newer because local Odoo 19 sources use newer syntax:

```sh
python -B tools/audit_odoo19.py --odoo-root=/home/ayyan-dev/odoo19/odoo --backup='../NAS (copy)'
python -B -m unittest discover -s tests -v
node tests/test_odoo19_frontend.mjs
```

The audit checks module dependency existence, Python/XML syntax, XML record
fields, view fields, decorated ORM field references, identifiable create-value
fields, inherited core method availability and backup file presence. It is a
static approximation, not an Odoo registry or view validation.

The regression suite includes isolated execution of actual repaired methods.
Workbook tests generate real XLSX bytes with XlsxWriter and inspect formulas,
analytic labels and account codes with openpyxl; their ORM records are mocked.
The JavaScript checks execute the actual patches against isolated components,
not a browser session. A separate source inspection checked inherited XPath
targets against local community/enterprise view ancestors.

## Remaining limitations / warnings

- Installation logs warn about missing `hr.employee.employee_code` values in
  built-in/demo employees: 21 employees in the demo database and the built-in
  Administrator in the no-demo database. The field remains required and unique.
  Assign legitimate business codes before enforcing NOT NULL on existing data;
  neither fabricated codes nor weakened constraints were introduced.
- Core/dependency module descriptions produce docutils formatting warnings on
  installation/update. Custom manifest descriptions were checked independently.
  Installation success does not mean the complete environment is warning-free.
- Full browser workflows, authorized API CRUD, scheduled jobs, stock validation,
  visual PDF/Excel layout review and large-volume performance remain unverified.
- An Odoo 18-to-19 database migration on a restored copy, including native HR
  version-backed fields and unchanged custom stored data. Source compatibility
  does not upgrade native database schemas or prove preservation of live data.
- Existing `noupdate` records and privilege assignments on an upgraded database.
- Configuration-dependent company journals, OU clearing accounts and project/OU
  mapping entries. No production configuration/data was overwritten.
- Upgraded the verification environment from openpyxl 3.1.2 to 3.1.5 and reran
  the 20 source/isolated tests successfully without its `utcnow` warning.

Do not interpret passing these checks as confirmation that every business
workflow, database migration or PDF layout is perfectly verified.
