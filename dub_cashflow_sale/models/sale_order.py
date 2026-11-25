from odoo import api, fields, models


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
        """Amount of the order not yet covered by posted invoices, in the
        order currency.

        Computed on quantities: amount_to_invoice of Odoo is 0 for goods not
        yet delivered under the "delivery" invoice policy, but the order still
        has to be invoiced and paid. Posted down payments are subtracted: the
        down payment lines have no quantity, and their invoices are forecast
        (or paid) on their own.
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
        amount -= self._cashflow_posted_down_payments()
        return max(amount, 0.0)

    def _cashflow_posted_down_payments(self):
        """Down payments invoiced by posted invoices, in the order currency.

        The deduction line of the final invoice is negative and nets them
        back, refunds subtract.
        """
        self.ensure_one()
        amount = 0.0
        down_payment_lines = self.order_line.filtered('is_downpayment')
        for invoice_line in down_payment_lines.invoice_lines:
            move = invoice_line.move_id
            if move.state != 'posted':
                continue
            sign = -1 if move.move_type == 'out_refund' else 1
            amount += sign * move.currency_id._convert(
                invoice_line.price_total, self.currency_id, self.company_id,
                move.invoice_date or fields.Date.context_today(self))
        return amount

    def _cashflow_forecast_amount(self):
        """Forecast amount in the company currency, at today's rate: the
        uninvoiced remainder of a confirmed order, the total of a quotation."""
        self.ensure_one()
        if self.state == 'sale':
            amount = self._cashflow_amount_to_invoice()
        else:
            amount = self.amount_total
        company = self.company_id
        return self.currency_id._convert(
            amount, company.currency_id, company, fields.Date.context_today(self))
