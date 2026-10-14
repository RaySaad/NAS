// Isolated patch tests. No Odoo server or browser is started.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
function patch(target, extension) {
    const parent = Object.create(Object.getPrototypeOf(target));
    Object.defineProperties(parent, Object.getOwnPropertyDescriptors(target));
    Object.setPrototypeOf(extension, parent);
    Object.defineProperties(target, Object.getOwnPropertyDescriptors(extension));
}
function loadPatch(filename, componentName, component) {
    const source = fs.readFileSync(path.join(root, filename), 'utf8').replace(/^import[^\n]*\n/gm, '');
    new Function(componentName, 'patch', '_t', source)(component, patch, (text) => text);
}
class AccountTypeSelection {
    setup() {
        this.groups = [{label: 'Assets'}, {label: 'Liabilities'}];
    }
    get choices() {
        return [{value: 'main_account', label: 'Main'}, {value: 'asset_cash', label: 'Cash'}];
    }
}
loadPatch('account_ext/static/src/components/account_type_selection/account_type_selection.js', 'AccountTypeSelection', AccountTypeSelection);
const selection = new AccountTypeSelection();
selection.setup();
assert.equal(selection.groups[1].label, 'Main');
assert.equal(selection.groups[1].choices[0].value, 'main_account');
assert.equal(selection.groups[1].section, 'balance_sheet');

class AnalyticDistribution {
    recordProps() {
        return {fields: {x_plan1_id: {domain: [['root_plan_id', '=', 1]]}}};
    }
}
loadPatch('analytic_operating_unit/static/src/components/analytic_distribution.esm.js', 'AnalyticDistribution', AnalyticDistribution);
const distribution = new AnalyticDistribution();
distribution.props = {record: {data: {operating_unit_id: {id: 8, display_name: 'OU8'}}}};
assert.deepEqual(distribution.recordProps({}).fields.x_plan1_id.domain.slice(1),
    ['|', ['operating_unit_ids', 'in', [8]], ['operating_unit_ids', '=', false]]);
distribution.props.record.data.operating_unit_id = false;
assert.deepEqual(distribution.recordProps({}).fields.x_plan1_id.domain, [['root_plan_id', '=', 1]]);
console.log('PASS: account-type choices, analytic OU domain, and unset-OU fallback');
