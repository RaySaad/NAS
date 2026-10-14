#!/usr/bin/env bash
# Every HTTP request below is made by curl, not Python requests.
set -euo pipefail
umask 077
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(cd -- "$script_dir/../.." && pwd)"
NAS_CURL_URL="${NAS_CURL_URL:-http://127.0.0.1:8069}"
NAS_CURL_DB="${NAS_CURL_DB:-naass_test_19.0_2026_10_06_16_05}"
mode="${1:-auth}"
[[ $# -eq 0 ]] || shift
entry="${1:-}"
if [[ "$mode" == "call" ]]; then
    [[ -n "$entry" ]] || { echo 'Usage: bash tools/curl_api/run.sh call contact_read'; exit 2; }
    shift
fi
write=false
confirm=''
try_default=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --write) write=true; shift ;;
        --confirm-db) confirm="${2:?Missing database}"; shift 2 ;;
        --try-default-token) try_default=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done
case "$mode" in auth|read|call) ;; *) echo 'Modes: auth, read, call ENTRY' >&2; exit 2 ;; esac
for dependency in curl jq rg; do command -v "$dependency" >/dev/null || { echo "Missing $dependency"; exit 2; }; done
if [[ "$mode" != auth && -z "${NAS_API_TOKEN:-}" ]]; then
    if $try_default; then
        # Read only the declared factory default, without echoing it into logs.
        NAS_API_TOKEN="$(/home/ayyan-dev/.venv312/bin/python -B -c 'import ast,sys
tree=ast.parse(open(sys.argv[1]).read())
for node in ast.walk(tree):
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="api_token" for t in node.targets):
  for kw in node.value.keywords:
   if kw.arg=="default": print(ast.literal_eval(kw.value))' "$root_dir/employees_ext/models/token_settings.py")"
    else
        read -r -s -p 'Configured HR API token: ' NAS_API_TOKEN
        echo
    fi
fi
NAS_CURL_RESULTS="${NAS_CURL_RESULTS:-$(mktemp -d /tmp/nas-curl-results.XXXXXX)}"
mkdir -p -- "$NAS_CURL_RESULTS"
cookies="$NAS_CURL_RESULTS/cookies.txt"
# Odoo's ensure_db binds this fresh cookie session to the named database.
login_status="$(curl -sS -L --connect-timeout 5 --max-time 30 -c "$cookies" -b "$cookies" \
    -o "$NAS_CURL_RESULTS/login.html" -w '%{http_code}' \
    "$NAS_CURL_URL/web/login?db=$NAS_CURL_DB")"
[[ "$login_status" == 200 ]] || { echo "Cannot select test database: HTTP $login_status"; exit 2; }
passed=0
failed=0

request_case() {
    local name="$1" method="$2" route="$3" payload="$4" auth="$5" expected="$6"
    local body="$NAS_CURL_RESULTS/$name.json" status token=''
    local -a args=(-sS --connect-timeout 5 --max-time 60 -b "$cookies" -c "$cookies"
                  -X "$method" -H 'Content-Type: application/json' -o "$body" -w '%{http_code}')
    if [[ "$method" != GET ]]; then args+=(--data-binary "@$payload"); fi
    if [[ "$auth" != missing ]]; then
        token="${NAS_API_TOKEN:-}"
        [[ "$auth" != invalid ]] || token="NAS-CURL-INVALID-$(date +%s)"
        # Header on stdin keeps the token out of curl's argument list and logs.
        status="$(printf 'Authorization: Bearer %s\n' "$token" | curl "${args[@]}" -H @- "$NAS_CURL_URL$route")"
    else
        status="$(curl "${args[@]}" "$NAS_CURL_URL$route")"
    fi
    local predicate
    if [[ "$expected" == unauthorized ]]; then
        predicate='(.result // .) | .success == false and .error == true and (.message | ascii_downcase | contains("unauthorized"))'
    elif [[ "$expected" == required ]]; then
        predicate='(.result // .) | .success == false and .error == true and (.message | ascii_downcase | contains("required"))'
    else
        predicate='(.result // .) | if type == "array" then length > 0 and all(.[]; .success == true and .error == false) else .success == true and .error == false end'
    fi
    if [[ "$status" == 200 ]] && jq -e "$predicate" "$body" >/dev/null 2>&1; then
        echo "PASS $name HTTP=$status"
        passed=$((passed + 1))
    else
        echo "FAIL $name HTTP=$status response=$body"
        jq -r 'if .error and (.error | type == "object") then .error.message else (.result // .).message // "Unexpected/non-JSON response" end' "$body" 2>/dev/null || true
        failed=$((failed + 1))
    fi
}

if [[ "$mode" == auth ]]; then
    while IFS=$'\t' read -r name method route file; do
        for auth in missing invalid; do
            request_case "$name-$auth" "$method" "$route" "$script_dir/payloads/$file" "$auth" unauthorized
        done
    done < "$script_dir/endpoints.tsv"
elif [[ "$mode" == read ]]; then
    while IFS=$'\t' read -r name method route file; do
        case "$name" in countries_read|states_read|tax_read|section_read)
            request_case "$name" "$method" "$route" "$script_dir/payloads/$file" valid success ;;
        esac
    done < "$script_dir/endpoints.tsv"
    for kind in invoice invoice_refund payment clearance insurance_payment cost_invoice payroll multi-invoice multi-payment; do
        # Safe missing-field tests: this payload cannot reach journal creation.
        jq -n --arg type "$kind" '{type:$type}' > "$NAS_CURL_RESULTS/validation-$kind-payload.json"
        request_case "jv-$kind-required" POST /api/jv/create "$NAS_CURL_RESULTS/validation-$kind-payload.json" valid required
    done
else
    row="$(awk -F '\t' -v entry="$entry" '$1 == entry {print}' "$script_dir/endpoints.tsv")"
    [[ -n "$row" ]] || { echo "Unknown entry: $entry"; exit 2; }
    IFS=$'\t' read -r name method route file <<< "$row"
    payload="$script_dir/payloads/$file"
    case "$entry" in *_create|*_update|*_delete|jv_*)
        $write && [[ "$confirm" == "$NAS_CURL_DB" && "$NAS_CURL_DB" == naass_test_* ]] || {
            echo 'Writes need --write --confirm-db matching the naass_test_* database.' >&2; exit 2;
        }
        [[ -n "${NAS_CURL_RUN:-}" && "$NAS_CURL_RUN" =~ ^[A-Za-z0-9-]+$ ]] || {
            echo 'Set NAS_CURL_RUN to a unique run ID; use the same ID for related CRUD calls.' >&2; exit 2;
        }
    esac
    jq --slurpfile replacements "$script_dir/values.json" --argjson section "${NAS_CURL_SECTION_ID:-0}" \
      'walk(if type == "string" then ($replacements[0][.] // .) else . end)
       | if $section > 0 and has("section_id") then .section_id = $section else . end
       | if $section > 0 and has("employee_section") then .employee_section = $section else . end' \
      "$payload" > "$NAS_CURL_RESULTS/$name-resolved.json"
    payload="$NAS_CURL_RESULTS/$name-resolved.json"
    if rg -q 'REPLACE_' "$payload"; then
        echo "Fill placeholders in $payload first (section_id must be a JSON number)." >&2; exit 2
    fi
    if [[ -n "${NAS_CURL_RUN:-}" ]]; then
        # The current endpoint rejects non-numeric department CRM inputs.
        # Pass a stable numeric CRM ID for all department/employee calls.
        NAS_CURL_DEPARTMENT_CRM="${NAS_CURL_DEPARTMENT_CRM:-190614001}"
        jq --arg prefix "NAS-CURL-$NAS_CURL_RUN" --arg dept "$NAS_CURL_DEPARTMENT_CRM" \
          'walk(if . == "NAS-CURL-DEPARTMENT" then $dept elif type == "string" then gsub("NAS-CURL"; $prefix) else . end)' \
          "$payload" > "$NAS_CURL_RESULTS/$name-payload.json"
        payload="$NAS_CURL_RESULTS/$name-payload.json"
    fi
    request_case "$name" "$method" "$route" "$payload" valid success
fi
echo "SUMMARY: $passed passed, $failed failed; responses: $NAS_CURL_RESULTS"
echo "Selected database: $NAS_CURL_DB. API token not included in result files."
[[ "$failed" -eq 0 ]]
