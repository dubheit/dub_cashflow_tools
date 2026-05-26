from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RibaIssue(models.TransientModel):
    _inherit = "riba.issue"

    credit_line_id = fields.Many2one(
        "treasury.credit.line",
        related="configuration_id.credit_line_id",
        string="Castelletto",
    )
    castelletto_currency_id = fields.Many2one(
        related="credit_line_id.currency_id",
    )
    castelletto_limit = fields.Monetary(
        string="Plafond",
        compute="_compute_castelletto",
        currency_field="castelletto_currency_id",
    )
    castelletto_used = fields.Monetary(
        string="Utilizzato",
        compute="_compute_castelletto",
        currency_field="castelletto_currency_id",
    )
    castelletto_available = fields.Monetary(
        string="Residuo disponibile",
        compute="_compute_castelletto",
        currency_field="castelletto_currency_id",
    )
    issue_amount = fields.Monetary(
        string="Importo in emissione",
        compute="_compute_castelletto",
        currency_field="castelletto_currency_id",
    )
    castelletto_after = fields.Monetary(
        string="Residuo dopo emissione",
        compute="_compute_castelletto",
        currency_field="castelletto_currency_id",
    )
    castelletto_over = fields.Boolean(
        string="Plafond superato",
        compute="_compute_castelletto",
    )
    castelletto_expiry = fields.Date(
        related="credit_line_id.expiry_date",
        string="Scadenza castelletto",
    )
    castelletto_state = fields.Selection(
        related="credit_line_id.state",
        string="Stato castelletto",
    )

    def _get_issue_amount(self):
        """Total residual of the move lines this wizard is about to issue."""
        active_ids = self.env.context.get("active_ids") or []
        move_lines = self.env["account.move.line"].browse(active_ids).exists()
        return sum(abs(line.amount_residual) for line in move_lines)

    @api.depends("configuration_id", "credit_line_id")
    def _compute_castelletto(self):
        for wiz in self:
            cl = wiz.credit_line_id
            issue_amount = wiz._get_issue_amount()
            wiz.issue_amount = issue_amount
            if cl:
                used = cl._get_current_usage()
                available = cl.limit_amount - used
                wiz.castelletto_limit = cl.limit_amount
                wiz.castelletto_used = used
                wiz.castelletto_available = available
                wiz.castelletto_after = available - issue_amount
                wiz.castelletto_over = issue_amount > available
            else:
                wiz.castelletto_limit = 0.0
                wiz.castelletto_used = 0.0
                wiz.castelletto_available = 0.0
                wiz.castelletto_after = 0.0
                wiz.castelletto_over = False

    def create_list(self):
        self.ensure_one()
        if self.castelletto_over:
            raise UserError(
                _(
                    "Emissione bloccata: l'importo da presentare (%(amount)s) "
                    "supera il residuo disponibile del castelletto %(line)s "
                    "(%(available)s). Riduci le scadenze selezionate o usa "
                    "un'altra banca/configurazione.",
                    amount=self.issue_amount,
                    line=self.credit_line_id.display_name,
                    available=self.castelletto_available,
                )
            )
        return super().create_list()
