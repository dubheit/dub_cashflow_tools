from odoo import models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        self._delete_sale_order_cashflow(moves)
        return moves

    def _delete_sale_order_cashflow(self, moves):
        """Delete cashflow entries for sale orders linked to these invoices."""
        # Get sale orders linked to these invoices
        sale_orders = self.env['sale.order']
        for move in moves:
            if move.move_type in ('out_invoice', 'out_refund'):
                # Get sale orders from invoice lines
                for line in move.invoice_line_ids:
                    if line.sale_line_ids:
                        sale_orders |= line.sale_line_ids.mapped('order_id')

        if sale_orders:
            # Delete cashflow entries for these sale orders
            entries = self.env['cashflow.entry'].search([
                ('model', '=', 'sale.order'),
                ('res_id', 'in', sale_orders.ids),
            ])
            if entries:
                entries.unlink()
