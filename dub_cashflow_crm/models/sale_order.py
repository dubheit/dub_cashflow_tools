from odoo import models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_opportunity_cashflow()
        return records

    def write(self, vals):
        # The opportunity forecasts until an order is confirmed: confirming
        # (state 'sale', written by action_confirm), cancelling or moving an
        # order recomputes the opportunities it leaves or joins.
        old_opportunities = self.opportunity_id
        result = super().write(vals)
        if 'opportunity_id' in vals or 'state' in vals:
            (old_opportunities | self.opportunity_id)._refresh_cashflow()
        return result

    def _refresh_opportunity_cashflow(self):
        """Have the opportunities of these orders recomputed.

        The opportunity keeps its forecast next to a quotation: the config
        filter drops it only once a linked order is confirmed, when the queued
        recomputation runs.
        """
        self.opportunity_id._refresh_cashflow()
