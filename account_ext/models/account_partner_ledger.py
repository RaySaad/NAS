# -*- coding: utf-8 -*-
from odoo import models


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def _get_report_line_partners(self, options, partner, partner_values, level_shift=0):
        res = super()._get_report_line_partners(options, partner, partner_values, level_shift=level_shift)
        if partner and partner.customer_code:
            res['name'] = f"[{partner.customer_code}] {res['name']}"
        return res
