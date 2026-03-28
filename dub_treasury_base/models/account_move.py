from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Link to treasury installment that generated this entry
    generating_installment_id = fields.Many2one(
        'treasury.installment',
        string='Generating Installment',
        readonly=True,
        index=True,
        ondelete='cascade',
        copy=False,
    )

    # Related field for quick access to instrument
    treasury_instrument_id = fields.Many2one(
        'treasury.financial.instrument',
        string='Treasury Instrument',
        related='generating_installment_id.instrument_id',
        store=True,
        readonly=True,
    )

    # Flag to distinguish payment moves from reclassification moves
    is_treasury_payment_move = fields.Boolean(
        string='Is Treasury Payment Move',
        default=False,
        help='True for principal+interest payment entries, '
             'False for reclassification entries',
    )

    # Link for credit line entries
    credit_line_id = fields.Many2one(
        'treasury.credit.line',
        string='Credit Line',
        readonly=True,
        index=True,
        ondelete='set null',
        copy=False,
    )

    # Type of credit line movement
    credit_line_movement_type = fields.Selection(
        selection=[
            ('utilization', 'Utilization (Drawing)'),
            ('repayment', 'Repayment'),
            ('interest', 'Interest Charge'),
        ],
        string='Credit Line Movement Type',
    )

    # Link to financial instruments (for vendor bills)
    # This is the reverse of vendor_bill_ids on treasury.financial.instrument
    treasury_instrument_ids = fields.Many2many(
        'treasury.financial.instrument',
        'treasury_instrument_vendor_bill_rel',
        'move_id',
        'instrument_id',
        string='Financial Instruments',
        domain="[('company_id', '=', company_id)]",
        help='Financial instruments linked to this invoice',
    )

    # Link to credit lines (for all invoice types)
    # This is the reverse of linked_invoice_ids on treasury.credit.line
    credit_line_ids = fields.Many2many(
        'treasury.credit.line',
        'treasury_credit_line_vendor_bill_rel',
        'move_id',
        'credit_line_id',
        string='Credit Lines',
        domain="[('company_id', '=', company_id)]",
        help='Credit lines linked to this invoice (customer invoices for '
             'advance/SBF/factoring, vendor bills for costs)',
    )
