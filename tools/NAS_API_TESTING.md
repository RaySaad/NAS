# NAS Odoo 19 API tests

Target database: `naass_test_19.0_2026_10_06_16_05`, server
`http://127.0.0.1:8069`. Run from the NAS repository directory.

The script authenticates the Odoo session and checks its database and version
before API calls. Supply the Odoo login password when prompted. Supply the HR
API token configured in General Settings when prompted; do not paste secrets
into the script or command arguments. Optional environment variables are
`NAS_TEST_PASSWORD` and `NAS_API_TOKEN`.

## Start with non-mutating checks

```bash
/home/ayyan-dev/.venv312/bin/python -B tools/test_nas_apis.py
```

This checks missing/invalid-token rejection on all 24 endpoints, countries,
states (US by default), taxes, safe missing-required-field cases and all nine
JV type validators. It does not run successful CRUD or successful accounting
creation. API endpoints returning a business error are failures, even with
HTTP 200. Missing country/state/tax master data can therefore fail read tests.

For authorization checks only, without supplying the API token:

```bash
/home/ayyan-dev/.venv312/bin/python -B tools/test_nas_apis.py --auth-only
```

## Full endpoint/JV smoke suite on the test database

First edit `tools/nas_api_fixtures.json`. Replace every `REPLACE_...` value with
an existing code/name from this database. Account and OU values are codes, not
record IDs. Customer contract is the `partner.subscription.name`. Bank journal
is its code, not its name/ID. Keep leading-zero account codes as JSON strings.
Set company_id to the login's active company. The sample uses company 1 only
because the retained controller references company-1 journal XML IDs.

Choose debit/credit accounts suitable for a balanced general entry; avoid
receivable/payable accounts requiring extra partner/payment terms. The
configured employee must be active. Use an employee/contract/OU from the same
company. Use a bank/cash journal with a valid default account. A Payroll journal
with a default account is also needed. Optionally set department/cost_center/
branch to analytic account codes, and tax_id to a numeric tax record ID.

The untouched legacy API also requires `account.1_sale`, `account.1_general`
and user ID 6 (with accounting permissions) for multi-entry creation. Tests
report missing configuration; they do not silently create these records or
change any production API logic.

```bash
/home/ayyan-dev/.venv312/bin/python -B tools/test_nas_apis.py \
  --fixtures tools/nas_api_fixtures.json \
  --write \
  --confirm-db naass_test_19.0_2026_10_06_16_05
```

Write mode creates, reads, updates, reads back and deletes **only newly created
uniquely named CRUD fixtures**. It checks contacts, companies, employees,
departments and sections. Company/create creates a test subscription too;
the script removes that exact owned subscription through authenticated ORM
before testing company/delete because there is no subscription-delete API.
It never deletes or edits the pre-existing accounting fixture records.

It creates all nine JV types plus a two-invoice batch, then independently reads
saved records to verify IDs, company, JV type, amount, balance and draft state.
These draft test accounting entries are **retained** for inspection, not posted
or deleted. Existing partner/employee/contract references are used on those
draft entries. All write-mode actions commit through normal HTTP requests;
there is no cross-request rollback. A failed legacy API may leave partial data.
Only use a disposable test database, never a production database.

## Results and coverage

Results are saved in `nas_api_test_results.json`, including failures and created
JV IDs. Exit codes: 0 = enabled checks passed, 1 = failed/incomplete checks,
2 = invalid options/login/database mismatch/unhandled setup error. A safe-mode
exit 0 is not a full-suite pass. Failed preflight skips positive JV creation and
makes the full run unsuccessful. Do not equate passing tests with exhaustive
proof of every possible payload, multi-company case or accounting workflow.

Routes covered: contact/company/employee/department create/read/update/delete;
employee sections create/read/update/delete; countries/read; states/read;
tax/read; jv/create. JV types covered: invoice, invoice_refund, payment,
clearance, insurance_payment, cost_invoice, payroll, multi-invoice, multi-payment.

`/api/jv/create` stays an HTTP endpoint and receives the original flat JSON
object/list. JSON-RPC endpoints use the Odoo 19 envelope; an additional employee
read checks legacy flat JSON compatibility. The server must have the latest
modules loaded. The script does not upgrade modules or restart Odoo.

This suite does not post/reconcile JVs, validate PDFs, test all optional line
dimensions, simulate simultaneous requests or certify production data.

Offline tests of the runner (no Odoo/database requests):

```bash
/home/ayyan-dev/.venv312/bin/python -B -m unittest discover -s tests -v
```
