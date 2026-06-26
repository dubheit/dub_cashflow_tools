from odoo import models, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

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

    def button_confirm(self):
        result = super().button_confirm()
        self.env['cashflow.config'].process_records(self, 'confirm')
        return result

    def button_cancel(self):
        result = super().button_cancel()
        self.env['cashflow.config'].process_records(self, 'cancel')
        return result

    def button_draft(self):
        result = super().button_draft()
        self.env['cashflow.config'].process_records(self, 'draft')
        return result
