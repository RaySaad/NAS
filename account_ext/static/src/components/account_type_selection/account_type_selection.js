/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { AccountTypeSelection } from '@account/components/account_type_selection/account_type_selection';
import { patch } from "@web/core/utils/patch";

patch(AccountTypeSelection.prototype, {
    get hierarchyOptions() {
        const hierarchyOptions = super.hierarchyOptions;
        const opts = this.options;
        const mainOption = { name: _t('Main'), children: opts.filter(x => x[0] && x[0].startsWith('main')) }
        hierarchyOptions.splice( 1, 0, mainOption);
        return hierarchyOptions;
    },
});
