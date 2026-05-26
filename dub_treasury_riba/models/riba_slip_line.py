from odoo import models


class RibaSlipLine(models.Model):
    _inherit = "riba.slip.line"

    def write(self, vals):
        """Refresh the linked castelletto usage whenever a slip line
        changes state (presented / collected / bounced / cancelled), so
        the stored ``used_amount`` of the credit line stays in sync even
        though there is no direct relational dependency path."""
        res = super().write(vals)
        if "state" in vals:
            credit_lines = self.slip_id.config_id.credit_line_id
            if credit_lines:
                credit_lines._compute_used_amount()
                credit_lines._compute_available_amount()
        return res
