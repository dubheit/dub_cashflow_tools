from odoo import models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        self._refresh_sale_order_cashflow(moves)
        return moves

    def _refresh_sale_order_cashflow(self, moves):
        """Have the sale orders of these invoices recomputed.

        The invoice now carries the forecast: the sale order config filter
        drops an order that has an invoice, so its entries go away when the
        queued recomputation runs. Deleting them here cleared the whole ORM
        cache in the middle of the invoice creation.
        """
        sale_orders = moves.filtered(
            lambda move: move.move_type in ('out_invoice', 'out_refund')
        ).invoice_line_ids.sale_line_ids.order_id
        self.env['cashflow.config'].process_records(sale_orders, 'write')
