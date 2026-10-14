# Per-API JSON and curl commands

`payloads/` contains 32 flat JSON samples: all 24 routes, with separate
accounting payloads for each of the nine JV types. `endpoints.tsv` maps each
sample to its route and method. The shell driver makes every HTTP call using
curl; jq only prepares JSON and checks responses. No controller is changed.

The default URL/database are `http://127.0.0.1:8069` and
`naass_test_19.0_2026_10_06_16_05`. Override with NAS_CURL_URL / NAS_CURL_DB.
The driver selects this DB through a fresh Odoo login-page cookie session.

From the NAS folder:

```bash
# Missing/invalid-token checks; does not write business records.
bash tools/curl_api/run.sh auth

# Countries, states, taxes, sections and nine JV required-field checks.
# Prompts for your configured HR API token without echoing it.
bash tools/curl_api/run.sh read

# One non-mutating call, using the existing JSON file.
NAS_CURL_RUN=YOUR_UNIQUE_RUN bash tools/curl_api/run.sh call contact_read
```

For CRUD: keep the same NAS_CURL_RUN across create/read/update/delete requests.
Use a new unique run ID for new tests. Set NAS_CURL_DEPARTMENT_CRM to a unique
numeric CRM value below 2147483647 for all related department/employee calls.
Set NAS_CURL_SECTION_ID to the numeric ID returned by section/create when
updating/deleting sections or assigning employee_section. Never use a section
ID belonging to existing business data. The department create sample supplies
unique unmatched manager/parent lookup keys because omitted values caused a
singleton failure on this database.

```bash
export NAS_CURL_RUN=my-unique-test-run
export NAS_CURL_DEPARTMENT_CRM=190614002

bash tools/curl_api/run.sh call contact_create --write \
  --confirm-db naass_test_19.0_2026_10_06_16_05
bash tools/curl_api/run.sh call contact_read
bash tools/curl_api/run.sh call contact_update --write \
  --confirm-db naass_test_19.0_2026_10_06_16_05
bash tools/curl_api/run.sh call contact_delete --write \
  --confirm-db naass_test_19.0_2026_10_06_16_05
```

Other names are listed in endpoints.tsv. For JV calls, review `values.json`
first. The sampled BU01, accounts 101005/101006 and bank INMA02 were read from
this test database. Contract/employee replacements refer to fixtures created
with the SAME run ID; they are not production/customer credentials. Create
company/employee fixtures first or replace them with approved existing test
master-data codes. Link the test employee to the selected OU using update.

```bash
bash tools/curl_api/run.sh call jv_invoice --write \
  --confirm-db naass_test_19.0_2026_10_06_16_05
```

You can also invoke curl directly with a prepared file. Select the DB session
first and use its cookie jar for every request. Supply the configured token as
a header; do not paste it into shared logs or save it in JSON files.

```bash
curl -sS -L -c /tmp/nas-api-cookies.txt -b /tmp/nas-api-cookies.txt \
  'http://127.0.0.1:8069/web/login?db=naass_test_19.0_2026_10_06_16_05' \
  -o /dev/null

read -r -s -p 'HR API token: ' NAS_API_TOKEN
printf '\n'
printf 'Authorization: Bearer %s\n' "$NAS_API_TOKEN" | \
  curl -sS -b /tmp/nas-api-cookies.txt -H @- \
    -H 'Content-Type: application/json' \
    --data-binary @tools/curl_api/payloads/contact_read.json \
    http://127.0.0.1:8069/api/contact/read
```

Direct curl sends file contents literally: unlike the driver, it does not
replace NAS-CURL identifiers or REPLACE_* master-data placeholders. GET routes
use curl without --data-binary. `/api/jv/create` requires flat JSON, not a
JSON-RPC params envelope. Passing HTTP 200 alone does not mean success; check
the JSON success/error fields.

Each run prints a private /tmp/nas-curl-results.* response directory, with
resolved payload JSON for call mode. Cookies are sensitive: do not publish the
cookie/login files. An optional --try-default-token uses the module's declared
factory default without displaying it; use the configured token normally.

## Completed live run, 2026-10-14

Run: `20261014-mv80eqrn`; numeric department CRM `1076511973`.
All 24 endpoints succeeded with suitable payloads, including CRUD deletion
using separate owned delete-test fixtures. All nine JV creations succeeded;
saved IDs 18666–18674 were independently checked as draft/company 1 with
debit=credit=10. No posting/reconciliation was performed. All 64 unauthenticated/
invalid-token cases were rejected. Initial department payload failures and the
initial empty section list are retained as limitations, not hidden successes.

Delete-test fixtures and the unused contact were removed; recreate them from
the JSON if needed. The accounting fixture company/contract/employee/department/
section and nine draft moves remain for inspection. No pre-existing record was
modified/deleted. Current curl responses are in the printed /tmp directories.
