from odoo import models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        self._delete_purchase_order_cashflow(moves)
        return moves

    def _delete_purchase_order_cashflow(self, moves):
        """Delete cashflow entries for purchase orders linked to these bills."""
        purchase_orders = self.env['purchase.order']
        for move in moves:
            if move.move_type in ('in_invoice', 'in_refund'):
                for line in move.invoice_line_ids:
                    if line.purchase_line_id:
                        purchase_orders |= line.purchase_line_id.order_id

        if purchase_orders:
            entries = self.env['cashflow.entry'].search([
                ('model', '=', 'purchase.order'),
                ('res_id', 'in', purchase_orders.ids),
            ])
            if entries:
                entries.unlink()
