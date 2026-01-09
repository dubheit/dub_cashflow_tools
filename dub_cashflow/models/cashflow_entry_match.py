from odoo import models, fields, api


class CashflowEntryMatch(models.Model):
    _name = 'cashflow.entry.match'
    _description = 'Cashflow Entry Match'
    _order = 'create_date desc'

    recurring_entry_id = fields.Many2one(
        'cashflow.entry',
        string='Recurring Entry',
        required=True,
        ondelete='cascade',
        domain=[('source_type', '=', 'recurring')],
    )
    actual_entry_id = fields.Many2one(
        'cashflow.entry',
        string='Actual Entry',
        required=True,
        ondelete='cascade',
        domain=[('source_type', '!=', 'recurring')],
    )
    state = fields.Selection([
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
    ], default='pending', required=True)

    # Display fields
    recurring_date = fields.Date(related='recurring_entry_id.date', string='Recurring Date')
    recurring_amount = fields.Float(compute='_compute_amounts', string='Recurring Amount')
    actual_date = fields.Date(related='actual_entry_id.date', string='Actual Date')
    actual_amount = fields.Float(compute='_compute_amounts', string='Actual Amount')
    amount_difference = fields.Float(compute='_compute_amounts', string='Difference')

    @api.depends('recurring_entry_id.item_ids.amount', 'actual_entry_id.item_ids.amount')
    def _compute_amounts(self):
        for match in self:
            match.recurring_amount = sum(match.recurring_entry_id.item_ids.mapped('amount'))
            match.actual_amount = sum(match.actual_entry_id.item_ids.mapped('amount'))
            match.amount_difference = match.actual_amount - match.recurring_amount

    def action_confirm(self):
        """Confirm match: delete recurring entry, keep actual entry."""
        for match in self:
            if match.state == 'pending':
                recurring = match.recurring_entry_id
                match.state = 'confirmed'
                # Clear the match_id on actual entry before deleting recurring
                match.actual_entry_id.write({'match_id': False})
                recurring.unlink()
        return True

    def action_reject(self):
        """Reject match: keep both entries, remove link."""
        for match in self:
            if match.state == 'pending':
                match.recurring_entry_id.write({'match_id': False})
                match.actual_entry_id.write({'match_id': False})
                match.state = 'rejected'
        return True
