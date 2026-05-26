from odoo import fields, models


class RibaConfiguration(models.Model):
    _inherit = "riba.configuration"

    credit_line_id = fields.Many2one(
        "treasury.credit.line",
        string="Castelletto",
        domain="[('credit_type', 'in', ('sbf', 'discount', 'advance')),"
               " ('company_id', '=', company_id)]",
        help="Linea di credito (castelletto) consumata dagli effetti presentati "
             "con questa configurazione Ri.Ba. L'utilizzo SBF del castelletto è "
             "calcolato dagli effetti in stato 'Presentata'.",
    )
