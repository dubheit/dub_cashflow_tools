from odoo import api, fields, models


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
    castelletto_expiry = fields.Date(
        related="credit_line_id.expiry_date",
        string="Scadenza castelletto",
    )
    castelletto_state = fields.Selection(
        related="credit_line_id.state",
        string="Stato castelletto",
    )

    @api.depends("configuration_id", "credit_line_id")
    def _compute_castelletto(self):
        for wiz in self:
            cl = wiz.credit_line_id
            if cl:
                used = cl._get_current_usage()
                wiz.castelletto_limit = cl.limit_amount
                wiz.castelletto_used = used
                wiz.castelletto_available = cl.limit_amount - used
            else:
                wiz.castelletto_limit = 0.0
                wiz.castelletto_used = 0.0
                wiz.castelletto_available = 0.0
