import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Delete cashflow entries for linked opportunities
        self._delete_opportunity_cashflow(records)
        return records

    def write(self, vals):
        result = super().write(vals)
        # If opportunity_id is set, delete its cashflow
        if 'opportunity_id' in vals:
            self._delete_opportunity_cashflow(self)
        return result

    def _delete_opportunity_cashflow(self, orders):
        """Delete cashflow entries linked to opportunities when sale order is created."""
        opportunity_ids = orders.mapped('opportunity_id').ids
        if not opportunity_ids:
            return

        # Find and delete cashflow entries linked to these opportunities
        entries = self.env['cashflow.entry'].search([
            ('model', '=', 'crm.lead'),
            ('res_id', 'in', opportunity_ids),
        ])
        if entries:
            _logger.info(
                "Deleting %s cashflow entries for opportunities %s (sale orders created)",
                len(entries), opportunity_ids
            )
            entries.unlink()
