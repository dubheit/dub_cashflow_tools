from odoo import models, fields


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

    def _projected_riba_usage_at_date(self, target_date):
        """Ri.Ba. portfolio still outstanding at ``target_date``.

        A presented (``confirmed``) effetto consumes the SBF/advance line from
        presentation until it matures: effects whose ``due_date`` has passed by
        ``target_date`` are collected and free the castelletto, so only effects
        maturing strictly after ``target_date`` still weigh on the line.

        This mirrors the "SALDO PTF" column of a manual treasury sheet, where
        the residual grows back as each effetto reaches its due date.
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
            ("due_date", ">", target_date),
        ])
        return sum(lines.mapped("amount"))

    def _projected_used_at_date(self, target_date, items_by_journal=None,
                                invoices=None):
        """Add the projected Ri.Ba. portfolio to the invoice-based projection
        for the credit types backed by presented effetti."""
        used = super()._projected_used_at_date(
            target_date, items_by_journal=items_by_journal, invoices=invoices,
        )
        if self.credit_type in ("advance", "discount", "sbf", "factoring"):
            target_date = fields.Date.to_date(target_date)
            used += self._projected_riba_usage_at_date(target_date)
        return used

    def _get_current_usage(self):
        """Live used amount (not relying on the stored compute), used by
        the Ri.Ba. issue wizard to show an up-to-date residual."""
        self.ensure_one()
        if not self.auto_compute_usage:
            return self.manual_used_amount
        if self.credit_type == "overdraft":
            return self._get_overdraft_usage()
        return self._get_invoice_based_usage()
