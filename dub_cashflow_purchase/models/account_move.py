from odoo import models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        self._refresh_purchase_order_cashflow(moves)
        return moves

    def _refresh_purchase_order_cashflow(self, moves):
        """Have the purchase orders of these bills recomputed (see
        dub_cashflow_sale: the order config filter drops a billed order)."""
        purchase_orders = moves.filtered(
            lambda move: move.move_type in ('in_invoice', 'in_refund')
        ).invoice_line_ids.purchase_line_id.order_id
        self.env['cashflow.config'].process_records(purchase_orders, 'write')
