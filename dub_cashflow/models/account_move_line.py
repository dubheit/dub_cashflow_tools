from odoo import models, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env['cashflow.config'].process_records(records, 'create')
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env['cashflow.config'].process_records(self, 'write')
        return result

    def unlink(self):
        self.env['cashflow.config'].process_records(self, 'unlink')
        return super().unlink()

    def copy(self, default=None):
        new_record = super().copy(default=default)
        self.env['cashflow.config'].process_records(new_record, 'copy')
        return new_record
