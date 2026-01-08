import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _inverse_tax_totals(self):
        """Override to handle tax_totals=False case (Odoo 18 bug workaround).

        Original Odoo code fails when tax_totals is False instead of a dict.
        This override adds the necessary check before iterating.
        """
        with self._disable_recursion({'records': self}, 'skip_invoice_sync') as disabled:
            if disabled:
                return
        with self._sync_dynamic_line(
            existing_key_fname='term_key',
            needed_vals_fname='needed_terms',
            needed_dirty_fname='needed_terms_dirty',
            line_type='payment_term',
            container={'records': self},
        ):
            for move in self:
                if not move.is_invoice(include_receipts=True):
                    continue
                invoice_totals = move.tax_totals

                # FIX: Skip if tax_totals is False/empty (Odoo 18 bug)
                if not invoice_totals or not isinstance(invoice_totals, dict):
                    continue

                for subtotal in invoice_totals.get('subtotals', []):
                    for tax_group in subtotal.get('tax_groups', []):
                        tax_lines = move.line_ids.filtered(lambda line: line.tax_group_id.id == tax_group['id'])

                        if tax_lines:
                            first_tax_line = tax_lines[0]
                            tax_group_old_amount = sum(tax_lines.mapped('amount_currency'))
                            sign = -1 if move.is_inbound() else 1
                            delta_amount = tax_group_old_amount * sign - tax_group['tax_amount_currency']

                            if not move.currency_id.is_zero(delta_amount):
                                first_tax_line.amount_currency -= delta_amount * sign
            self._compute_amount()

    def _get_cashflow_lines(self):
        """Get lines that may generate cashflow entries."""
        return self.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
        )

    def write(self, vals):
        result = super().write(vals)
        # If payment_state changes, re-process the cashflow for invoice lines
        if 'payment_state' in vals:
            _logger.info("CASHFLOW: account.move.write() payment_state changed to %s for moves %s", vals.get('payment_state'), self.ids)
            # Invalidate cache to ensure lines see the updated payment_state
            self.invalidate_recordset(['payment_state'])
            lines = self._get_cashflow_lines()
            if lines:
                # Also invalidate the lines' cache for the move_id relationship
                lines.invalidate_recordset(['move_id'])
                self.env['cashflow.config'].process_records(lines, 'write')
        return result

    def action_post(self):
        result = super().action_post()
        # Process the receivable/payable lines after posting is complete
        lines = self._get_cashflow_lines()
        if lines:
            self.env['cashflow.config'].process_records(lines, 'post')
        return result

    def button_draft(self):
        result = super().button_draft()
        # Process the receivable/payable lines after reverting to draft
        lines = self._get_cashflow_lines()
        if lines:
            self.env['cashflow.config'].process_records(lines, 'draft')
        return result

    def button_cancel(self):
        result = super().button_cancel()
        # Process the receivable/payable lines after cancellation
        lines = self._get_cashflow_lines()
        if lines:
            self.env['cashflow.config'].process_records(lines, 'cancel')
        return result
