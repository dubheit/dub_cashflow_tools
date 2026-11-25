from odoo import models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        self._refresh_sale_order_cashflow(moves)
        return moves

    def write(self, vals):
        result = super().write(vals)
        if 'state' in vals:
            # Posting, resetting or cancelling an invoice changes what the
            # order still has to invoice.
            self._refresh_sale_order_cashflow(self)
        return result

    def _refresh_sale_order_cashflow(self, moves):
        """Have the sale orders of these invoices recomputed.

        The order forecasts what the posted invoices do not cover yet, so it
        is recomputed when an invoice is created or changes state. Deleting
        its entries here cleared the whole ORM cache in the middle of the
        invoice creation: the queued recomputation does the work.
        """
        sale_orders = moves.filtered(
            lambda move: move.move_type in ('out_invoice', 'out_refund')
        ).invoice_line_ids.sale_line_ids.order_id
        self.env['cashflow.config'].process_records(sale_orders, 'write')
