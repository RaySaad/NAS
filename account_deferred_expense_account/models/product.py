from odoo import fields, models


DEFERRED_EXPENSE_ACCOUNT_DOMAIN = "[('account_type', 'in', ('asset_current', 'asset_prepayments', 'asset_non_current'))]"


class ProductCategory(models.Model):
    _inherit = "product.category"

    property_deferred_expense_account_categ_id = fields.Many2one(
        comodel_name="account.account",
        company_dependent=True,
        string="Deferred Expense Account",
        domain=DEFERRED_EXPENSE_ACCOUNT_DOMAIN,
        ondelete="restrict",
        tracking=True,
        help=(
            "Default prepaid/deferred expense account for products in this category. "
            "If empty, the parent category is checked, then Odoo's company-level "
            "Deferred Expense account is used."
        ),
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    property_deferred_expense_account_id = fields.Many2one(
        comodel_name="account.account",
        company_dependent=True,
        string="Deferred Expense Account",
        domain=DEFERRED_EXPENSE_ACCOUNT_DOMAIN,
        ondelete="restrict",
        help=(
            "Prepaid/deferred expense account to use when this product is deferred on a vendor bill. "
            "Keep it empty to use the product category, then Odoo's company-level Deferred Expense account."
        ),
    )

    def _get_deferred_expense_account(self):
        """Return the product/category deferred expense account, excluding company fallback."""
        self.ensure_one()
        return (
            self.property_deferred_expense_account_id
            or self._get_category_account("property_deferred_expense_account_categ_id")
        )
