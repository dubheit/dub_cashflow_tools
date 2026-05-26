from odoo import models


class TreasuryCreditLine(models.Model):
    _inherit = "treasury.credit.line"

    def _get_riba_usage(self):
        """Usage coming from presented (not yet collected) Ri.Ba. effetti.

        Sums the amount of ``riba.slip.line`` in state ``confirmed``
        (presented to the bank, advance outstanding) whose slip
        configuration points to this credit line. Collected (``paid``),
        bounced (``past_due``) or cancelled lines free the castelletto.
        """
        self.ensure_one()
        configs = self.env["riba.configuration"].search(
            [("credit_line_id", "=", self.id)]
        )
        if not configs:
            return 0.0
        lines = self.env["riba.slip.line"].search([
            ("slip_id.config_id", "in", configs.ids),
            ("state", "=", "confirmed"),
        ])
        return sum(lines.mapped("amount"))

    def _get_invoice_based_usage(self):
        """Add presented Ri.Ba. effetti on top of the standard
        invoice-based usage (advance/sbf/factoring/discount)."""
        return super()._get_invoice_based_usage() + self._get_riba_usage()

    def _get_current_usage(self):
        """Live used amount (not relying on the stored compute), used by
        the Ri.Ba. issue wizard to show an up-to-date residual."""
        self.ensure_one()
        if not self.auto_compute_usage:
            return self.manual_used_amount
        if self.credit_type == "overdraft":
            return self._get_overdraft_usage()
        return self._get_invoice_based_usage()
