from odoo import api, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env['cashflow.config'].process_records(records, 'create')
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env['cashflow.config'].process_records(self, 'write')
        return result

    def unlink(self):
        self.env['cashflow.config'].process_records(self, 'unlink')
        return super().unlink()

    def button_confirm(self):
        result = super().button_confirm()
        self.env['cashflow.config'].process_records(self, 'confirm')
        return result

    def button_cancel(self):
        result = super().button_cancel()
        self.env['cashflow.config'].process_records(self, 'cancel')
        return result

    def button_draft(self):
        result = super().button_draft()
        self.env['cashflow.config'].process_records(self, 'draft')
        return result

    def _cashflow_amount_to_invoice(self):
        """Amount of the order not yet covered by posted vendor bills.

        Computed on quantities and on posted bills only: a draft bill has a
        draft (hidden) forecast of its own, so the order keeps its amount
        until the bill is posted.
        """
        self.ensure_one()
        amount = 0.0
        for line in self.order_line:
            if line.product_qty > 0:
                amount += (
                    line.price_total
                    * (line.product_qty - line._cashflow_posted_billed_qty())
                    / line.product_qty
                )
        return max(amount, 0.0)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _cashflow_posted_billed_qty(self):
        """Quantity billed by posted vendor bills, in the line unit.

        Same rule as qty_invoiced (refunds subtract), without draft bills.
        """
        self.ensure_one()
        qty = 0.0
        for bill_line in self.invoice_lines:
            move = bill_line.move_id
            if move.state != 'posted':
                continue
            if move.move_type == 'in_invoice':
                sign = 1
            elif move.move_type == 'in_refund':
                sign = -1
            else:
                continue
            qty += sign * bill_line.product_uom_id._compute_quantity(
                bill_line.quantity, self.product_uom)
        return qty
