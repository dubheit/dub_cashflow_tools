import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _logger.info("CASHFLOW: partial_reconcile.create() called with %s records: %s", len(records), records.ids)
        self.env['cashflow.config'].process_records(records, 'create')
        return records

    def unlink(self):
        _logger.info("CASHFLOW: partial_reconcile.unlink() called with %s records: %s", len(self), self.ids)
        self.env['cashflow.config'].process_records(self, 'unlink')
        return super().unlink()
