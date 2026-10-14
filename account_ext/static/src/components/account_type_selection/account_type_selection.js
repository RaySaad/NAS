/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { AccountTypeSelection } from '@account/components/account_type_selection/account_type_selection';
import { patch } from "@web/core/utils/patch";

patch(AccountTypeSelection.prototype, {
    setup() {
        super.setup();
        this.groups.splice(1, 0, {
            label: _t('Main'),
            choices: this.choices.filter((choice) => choice.value.startsWith('main')),
            section: 'balance_sheet',
        });
    },
});
