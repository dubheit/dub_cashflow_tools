from odoo import models, api


class CrmLead(models.Model):
    _inherit = 'crm.lead'

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

    def action_set_won_rainbowman(self):
        """Override to update cashflow when opportunity is won."""
        result = super().action_set_won_rainbowman()
        self.env['cashflow.config'].process_records(self, 'write')
        return result

    def action_set_lost(self, **additional_values):
        """Override to delete cashflow when opportunity is lost."""
        result = super().action_set_lost(**additional_values)
        # When lost, delete the cashflow entry
        self.env['cashflow.config'].process_records(self, 'cancel')
        return result
