from odoo import models, fields, api


class CashflowItem(models.Model):
    _name = 'cashflow.item'
    _description = 'Cashflow Item'
    _order = 'date, id'

    entry_id = fields.Many2one('cashflow.entry', required=True, ondelete='cascade')
    date = fields.Date(required=True)
    amount = fields.Monetary(currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', required=True)
    type = fields.Selection([('in', 'Cash In'), ('out', 'Cash Out')], required=True)
    partner_id = fields.Many2one('res.partner')
    description = fields.Char()

    # Related fields from entry
    source_model = fields.Char(related='entry_id.model_label', string='Source', store=True)
    entry_name = fields.Char(related='entry_id.name', string='Entry Name')
    entry_type = fields.Selection(related='entry_id.entry_type', string='Entry Type', store=True)
    state = fields.Selection(related='entry_id.state', string='Status', store=True)
    model_id = fields.Many2one(related='entry_id.model_id', string='Source Model', store=True)
    journal_id = fields.Many2one(related='entry_id.journal_id', string='Bank', store=True)

    # Computed fields for reporting
    amount_in = fields.Monetary(
        string='Cash In',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    amount_out = fields.Monetary(
        string='Cash Out',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    amount_signed = fields.Monetary(
        string='Balance',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help='Positive for Cash In, negative for Cash Out',
    )

    @api.depends('amount', 'type')
    def _compute_amounts(self):
        for item in self:
            if item.type == 'in':
                item.amount_in = item.amount
                item.amount_out = 0
                item.amount_signed = item.amount
            else:
                item.amount_in = 0
                item.amount_out = item.amount
                item.amount_signed = -item.amount
