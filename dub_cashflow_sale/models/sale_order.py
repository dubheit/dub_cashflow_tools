from odoo import models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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

    def action_confirm(self):
        result = super().action_confirm()
        self.env['cashflow.config'].process_records(self, 'confirm')
        return result

    def action_cancel(self):
        result = super().action_cancel()
        self.env['cashflow.config'].process_records(self, 'cancel')
        return result

    def action_draft(self):
        result = super().action_draft()
        self.env['cashflow.config'].process_records(self, 'draft')
        return result

    def _cashflow_amount_to_invoice(self):
        """Amount of the order not yet covered by posted invoices.

        Computed on quantities: amount_to_invoice of Odoo is 0 for goods not
        yet delivered under the "delivery" invoice policy, but the order still
        has to be invoiced and paid.
        """
        self.ensure_one()
        amount = 0.0
        for line in self.order_line:
            if line.product_uom_qty > 0:
                amount += (
                    line.price_total
                    * (line.product_uom_qty - line.qty_invoiced_posted)
                    / line.product_uom_qty
                )
        return max(amount, 0.0)
