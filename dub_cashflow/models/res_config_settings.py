from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cashflow_matching_behavior = fields.Selection(
        selection=[
            ('delete', 'Delete recurring entry'),
            ('convert', 'Convert to invoice entry'),
        ],
        string='Matching Behavior',
        default='delete',
        config_parameter='dub_cashflow.matching_behavior',
        help='When a recurring entry is matched with an actual invoice:\n'
             '- Delete: Remove the recurring entry and create a new one from the invoice\n'
             '- Convert: Update the recurring entry to link it to the invoice',
    )
