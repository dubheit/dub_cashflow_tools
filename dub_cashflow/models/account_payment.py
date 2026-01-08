import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _logger.info("CASHFLOW: account.payment.create() ids=%s", records.ids)
        self.env['cashflow.config'].process_records(records, 'create')
        return records

    def write(self, vals):
        result = super().write(vals)
        _logger.info("CASHFLOW: account.payment.write() ids=%s, vals=%s", self.ids, list(vals.keys()))
        self.env['cashflow.config'].process_records(self, 'write')
        return result

    def action_post(self):
        result = super().action_post()
        _logger.info("CASHFLOW: account.payment.action_post() ids=%s, states=%s", self.ids, self.mapped('state'))
        self.env['cashflow.config'].process_records(self, 'write')
        return result

    def unlink(self):
        _logger.info("CASHFLOW: account.payment.unlink() ids=%s", self.ids)
        self.env['cashflow.config'].process_records(self, 'unlink')
        return super().unlink()
