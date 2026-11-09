from odoo import models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_opportunity_cashflow()
        return records

    def write(self, vals):
        # A quotation moved to another opportunity, or cancelled, gives the
        # forecast back to the opportunity it leaves.
        old_opportunities = self.opportunity_id
        result = super().write(vals)
        if 'opportunity_id' in vals or 'state' in vals:
            (old_opportunities | self.opportunity_id)._refresh_cashflow()
        return result

    def _refresh_opportunity_cashflow(self):
        """Have the opportunities of these orders recomputed.

        The quotation now carries the forecast: the opportunity config filter
        drops an opportunity with a live quotation, so its entries go away
        when the queued recomputation runs.
        """
        self.opportunity_id._refresh_cashflow()
