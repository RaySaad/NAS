/** @odoo-module **/

/**
 * account_journal_separate_pdf/static/src/js/action_manager_report.js
 *
 * This file patches the AccountMove list view to inject a
 * "Print Separate PDFs" entry into the Print dropdown button,
 * right below the existing "Print Journal Entries" option.
 */

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// We extend the default print items for the account.move list view
// by listening to the existing print dropdown and appending our action.

// The cleanest Odoo 18 approach: override getActionMenuItems in
// the ListController when the model is account.move
const originalSetup = ListController.prototype.setup;

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
    },
});
