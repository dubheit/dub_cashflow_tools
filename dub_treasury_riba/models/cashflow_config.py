from odoo import models


class CashflowConfig(models.Model):
    _inherit = "cashflow.config"

    def _is_superseded(self, record):
        """An invoice installment inside a presented effetto is forecast by
        the effetto (on the bank of its credit line), not by the invoice."""
        if record._name == "account.move.line":
            slip_move_line = self.env["riba.slip.move.line"].sudo().search([
                ("move_line_id", "=", record.id),
                ("riba_line_id.state", "in", ("confirmed", "credited")),
            ], limit=1)
            if slip_move_line:
                return True
        return super()._is_superseded(record)
