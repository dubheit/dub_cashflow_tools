from odoo import models, fields


class TreasuryAvailabilityReport(models.TransientModel):
    _name = 'treasury.availability.report'
    _description = 'Credit Line Availability (projected)'
    _order = 'date, credit_line_id'

    wizard_id = fields.Many2one(
        'treasury.availability.wizard',
        ondelete='cascade',
        index=True,
    )
    date = fields.Date(required=True)
    credit_line_id = fields.Many2one('treasury.credit.line', required=True)
    bank_id = fields.Many2one(
        related='credit_line_id.bank_id',
        store=True,
        string='Bank',
    )
    company_id = fields.Many2one('res.company')
    currency_id = fields.Many2one('res.currency')
    limit_amount = fields.Monetary(currency_field='currency_id')
    used_at_date = fields.Monetary(currency_field='currency_id')
    available_at_date = fields.Monetary(currency_field='currency_id')
    utilization_rate_at_date = fields.Float(string='Utilization (%)')
