# Deferred Expense Account by Product — Odoo 19

Small Odoo 19 Enterprise module that lets deferred expenses use different prepaid accounts instead of one global account for every expense.

## Resolution order

For a vendor bill line with Deferred Start/End dates:

1. **Vendor bill line → Prepaid Account** (manual override)
2. **Product → Deferred Expense Account**
3. **Product Category → Deferred Expense Account** (parent categories are also checked)
4. **Accounting Settings → Deferred Expense** (standard Odoo fallback)

The module does not replace Odoo's deferred-expense engine. It extends the native deferred line-value hook and substitutes only the standard company deferred-expense leg.

## Setup

1. Install the module `account_deferred_expense_account`.
2. Keep the standard Odoo Deferred Expense journal/account configured in Accounting Settings; it remains the fallback.
3. On a Product, open **Accounting** and set **Deferred Expense Account**, or set it on the Product Category.
4. Optionally enable the **Prepaid Account** column on a vendor bill line and override it for that individual line.
5. Set Deferred Start Date / Deferred End Date as usual and post the bill.

## Example

- Vehicle Insurance product → `104021 Prepaid Vehicle Insurance`
- Vehicle Registration product → `104022 Prepaid Vehicle Registration`
- Maintenance Contract product → `104023 Prepaid Vehicle Maintenance`
- Anything without a specific setup → standard company account, e.g. `104020 Prepaid Expenses`

## Notes

- Requires Odoo 19 Enterprise `account_accountant` because native deferred-expense fields and generation are provided by that module.
- Only vendor-bill deferred expenses are changed. Deferred revenue/customer invoices continue using standard Odoo behavior.
- Allowed prepaid accounts are Current Assets, Prepayments, or Non-current Assets.
