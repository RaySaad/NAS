from odoo import api, fields, models

from .product import DEFERRED_EXPENSE_ACCOUNT_DOMAIN


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    deferred_expense_account_override_id = fields.Many2one(
        comodel_name="account.account",
        string="Prepaid Account",
        domain=DEFERRED_EXPENSE_ACCOUNT_DOMAIN,
        ondelete="restrict",
        check_company=True,
        help=(
            "Optional deferred expense account for this vendor bill line. "
            "If empty, the module uses the product setting, then product category, "
            "then Odoo's company-level Deferred Expense account."
        ),
    )

    def _get_effective_deferred_expense_account(self):
        """Resolve line -> product -> category -> company deferred expense account."""
        self.ensure_one()

        if self.deferred_expense_account_override_id:
            return self.deferred_expense_account_override_id

        if self.product_id:
            product_tmpl = self.product_id.product_tmpl_id.with_company(self.company_id)
            product_account = product_tmpl._get_deferred_expense_account()
            if product_account:
                return product_account

        return self.company_id.deferred_expense_account_id

    @api.model
    def _get_deferred_lines_values(self, account_id, balance, ref, analytic_distribution, line=None):
        """
        Replace only the standard company deferred-expense leg with the account
        resolved for the source vendor-bill line.

        This keeps Odoo's native deferred-entry generation intact and changes only
        the balance-sheet account used by the deferred-expense leg.
        """
        if line and not isinstance(line, dict) and line.move_id.is_purchase_document():
            company_default = line.company_id.deferred_expense_account_id
            if company_default and account_id == company_default.id:
                effective_account = line._get_effective_deferred_expense_account()
                if effective_account:
                    account_id = effective_account.id

        return super()._get_deferred_lines_values(
            account_id,
            balance,
            ref,
            analytic_distribution,
            line=line,
        )
