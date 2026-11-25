from odoo import models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        self._refresh_purchase_order_cashflow(moves)
        return moves

    def write(self, vals):
        result = super().write(vals)
        if 'state' in vals:
            # Posting, resetting or cancelling a bill changes what the order
            # still has to be billed.
            self._refresh_purchase_order_cashflow(self)
        return result

    def _refresh_purchase_order_cashflow(self, moves):
        """Have the purchase orders of these bills recomputed.

        The order forecasts what the posted bills do not cover yet, so it is
        recomputed when a bill is created or changes state.
        """
        purchase_orders = moves.filtered(
            lambda move: move.move_type in ('in_invoice', 'in_refund')
        ).invoice_line_ids.purchase_line_id.order_id
        if purchase_orders:
            self.env['cashflow.config'].process_records(purchase_orders, 'write')
