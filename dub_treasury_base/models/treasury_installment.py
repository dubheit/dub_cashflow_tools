from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TreasuryInstallment(models.Model):
    _name = 'treasury.installment'
    _description = 'Treasury Installment'
    _order = 'instrument_id, sequence, date'

    instrument_id = fields.Many2one(
        'treasury.financial.instrument',
        string='Financial Instrument',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    # Related fields
    company_id = fields.Many2one(
        related='instrument_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='instrument_id.currency_id',
        store=True,
        readonly=True,
    )
    instrument_type = fields.Selection(
        related='instrument_id.instrument_type',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        related='instrument_id.partner_id',
        store=True,
        readonly=True,
    )
    flow_direction = fields.Selection(
        related='instrument_id.flow_direction',
        store=True,
        readonly=True,
    )

    # Installment details
    date = fields.Date(
        string='Due Date',
        required=True,
    )
    principal = fields.Monetary(
        string='Principal',
        currency_field='currency_id',
        required=True,
    )
    interest = fields.Monetary(
        string='Interest',
        currency_field='currency_id',
        required=True,
    )
    total = fields.Monetary(
        string='Total',
        currency_field='currency_id',
        compute='_compute_total',
        store=True,
    )

    # Additional charges
    fees = fields.Monetary(
        string='Fees',
        currency_field='currency_id',
        default=0.0,
    )
    insurance = fields.Monetary(
        string='Insurance',
        currency_field='currency_id',
        default=0.0,
    )

    # Payment info
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('due', 'Due'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue'),
        ],
        string='Status',
        default='draft',
        required=True,
    )
    payment_date = fields.Date(
        string='Payment Date',
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Payment',
        help='Linked payment record',
    )
    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        help='Linked journal entry',
    )
    generated_move_ids = fields.One2many(
        'account.move',
        'generating_installment_id',
        string='Generated Entries',
        readonly=True,
    )
    is_payment_move_posted = fields.Boolean(
        string='Payment Entry Posted',
        compute='_compute_is_payment_move_posted',
        store=True,
    )
    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Vendor Bill',
        domain="[('move_type', 'in', ['in_invoice', 'in_refund'])]",
        copy=False,
        help='Linked vendor bill for this installment',
    )

    # Residual info
    residual_before = fields.Monetary(
        string='Residual Before',
        currency_field='currency_id',
        help='Residual principal before this installment',
    )
    residual_after = fields.Monetary(
        string='Residual After',
        currency_field='currency_id',
        compute='_compute_residual_after',
        store=True,
    )

    notes = fields.Text(string='Notes')

    @api.depends('principal', 'interest', 'fees', 'insurance')
    def _compute_total(self):
        for installment in self:
            installment.total = (
                installment.principal +
                installment.interest +
                installment.fees +
                installment.insurance
            )

    @api.depends('residual_before', 'principal')
    def _compute_residual_after(self):
        for installment in self:
            if installment.residual_before:
                installment.residual_after = installment.residual_before - installment.principal
            else:
                installment.residual_after = 0.0

    @api.depends('generated_move_ids', 'generated_move_ids.state')
    def _compute_is_payment_move_posted(self):
        for installment in self:
            payment_moves = installment.generated_move_ids.filtered(
                lambda m: m.is_treasury_payment_move
            )
            installment.is_payment_move_posted = any(
                m.state == 'posted' for m in payment_moves
            )

    def action_set_due(self):
        """Mark installment as due."""
        self.write({'state': 'due'})

    def action_mark_paid(self):
        """Mark installment as paid."""
        self.write({
            'state': 'paid',
            'payment_date': fields.Date.today(),
        })

    def action_mark_overdue(self):
        """Mark installment as overdue."""
        self.write({'state': 'overdue'})

    @api.model
    def _cron_check_due_dates(self):
        """Cron job to update installment states based on due dates."""
        today = fields.Date.today()

        # Mark due installments
        due_installments = self.search([
            ('state', '=', 'draft'),
            ('date', '<=', today),
        ])
        due_installments.write({'state': 'due'})

        # Mark overdue installments
        overdue_installments = self.search([
            ('state', '=', 'due'),
            ('date', '<', today),
        ])
        overdue_installments.write({'state': 'overdue'})

    def action_create_payment(self):
        """Create a payment for this installment."""
        self.ensure_one()
        if self.state == 'paid':
            raise ValidationError(_('This installment is already paid.'))

        instrument = self.instrument_id
        payment_type = 'outbound' if instrument.flow_direction == 'inbound' else 'inbound'

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Payment'),
            'res_model': 'account.payment',
            'view_mode': 'form',
            'context': {
                'default_payment_type': payment_type,
                'default_partner_id': instrument.partner_id.id,
                'default_amount': self.total,
                'default_ref': f'{instrument.name} - Installment {self.sequence}',
            },
            'target': 'new',
        }

    def _prepare_payment_move_vals(self):
        """Prepare values for installment payment journal entry.

        For inbound loans:
        Debit: Long-term liability (capital reduction)
        Debit: Interest expense (interest payment)
        Credit: Short-term liability (payment from short-term account)

        For outbound loans:
        Debit: Short-term asset (payment received)
        Credit: Long-term asset (capital reduction)
        Credit: Interest income (interest received)
        """
        self.ensure_one()
        instrument = self.instrument_id
        instrument._validate_accounting_config()

        if not instrument.interest_account_id:
            raise ValidationError(
                _('Interest account not configured for %(name)s.',
                  name=instrument.name)
            )

        lines = []

        if instrument.flow_direction == 'inbound':
            # Inbound: paying a loan
            # Capital part - reduce liability
            if self.principal:
                lines.append((0, 0, {
                    'name': _('Principal - Installment %(seq)s', seq=self.sequence),
                    'account_id': instrument.long_term_account_id.id,
                    'debit': self.principal,
                    'credit': 0.0,
                    'partner_id': instrument.partner_id.id if instrument.partner_id else False,
                }))
            # Interest part - expense
            if self.interest:
                lines.append((0, 0, {
                    'name': _('Interest - Installment %(seq)s', seq=self.sequence),
                    'account_id': instrument.interest_account_id.id,
                    'debit': self.interest,
                    'credit': 0.0,
                }))
            # Total - from short-term liability (or bank)
            payment_account = instrument.short_term_account_id or instrument.disbursement_account_id
            lines.append((0, 0, {
                'name': _('Payment - %(name)s #%(seq)s', name=instrument.name, seq=self.sequence),
                'account_id': payment_account.id,
                'debit': 0.0,
                'credit': self.total,
                'partner_id': instrument.partner_id.id if instrument.partner_id else False,
            }))
        else:
            # Outbound: receiving payment on a loan granted
            payment_account = instrument.short_term_account_id or instrument.disbursement_account_id
            lines.append((0, 0, {
                'name': _('Receipt - %(name)s #%(seq)s', name=instrument.name, seq=self.sequence),
                'account_id': payment_account.id,
                'debit': self.total,
                'credit': 0.0,
                'partner_id': instrument.partner_id.id if instrument.partner_id else False,
            }))
            # Capital part - reduce asset
            if self.principal:
                lines.append((0, 0, {
                    'name': _('Principal - Installment %(seq)s', seq=self.sequence),
                    'account_id': instrument.long_term_account_id.id,
                    'debit': 0.0,
                    'credit': self.principal,
                    'partner_id': instrument.partner_id.id if instrument.partner_id else False,
                }))
            # Interest part - income
            if self.interest:
                lines.append((0, 0, {
                    'name': _('Interest - Installment %(seq)s', seq=self.sequence),
                    'account_id': instrument.interest_account_id.id,
                    'debit': 0.0,
                    'credit': self.interest,
                }))

        return {
            'move_type': 'entry',
            'date': self.date,
            'ref': _('%(name)s - Installment %(seq)s', name=instrument.name, seq=self.sequence),
            'journal_id': instrument.journal_id.id,
            'company_id': instrument.company_id.id,
            'currency_id': instrument.currency_id.id,
            'generating_installment_id': self.id,
            'is_treasury_payment_move': True,
            'line_ids': lines,
        }

    def action_generate_payment_entry(self):
        """Generate payment journal entry for this installment."""
        self.ensure_one()
        if self.is_payment_move_posted:
            raise ValidationError(
                _('Payment entry already posted for installment %(seq)s.',
                  seq=self.sequence)
            )

        move_vals = self._prepare_payment_move_vals()
        move = self.env['account.move'].create(move_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Payment Entry'),
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }

    def action_view_moves(self):
        """View all generated journal entries for this installment."""
        self.ensure_one()
        if len(self.generated_move_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Journal Entry'),
                'res_model': 'account.move',
                'res_id': self.generated_move_ids.id,
                'view_mode': 'form',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entries'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.generated_move_ids.ids)],
        }
