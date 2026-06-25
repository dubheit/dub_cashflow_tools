from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class TreasuryFinancialInstrument(models.Model):
    _name = 'treasury.financial.instrument'
    _description = 'Treasury Financial Instrument'
    _order = 'start_date desc, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
    )
    reference = fields.Char(
        string='Contract Reference',
        tracking=True,
    )
    account_id = fields.Many2one(
        'treasury.account',
        string='Treasury Account',
        tracking=True,
        help='Treasury account linked to this instrument',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )

    instrument_type = fields.Selection(
        selection=[
            ('loan', 'Bank Loan (Finanziamento)'),
            ('mortgage', 'Mortgage (Mutuo)'),
            ('leasing', 'Leasing'),
            ('bond', 'Bond (Obbligazione)'),
            ('partner_loan', 'Partner Loan (Prestito soci)'),
            ('factoring', 'Factoring Agreement'),
            ('other', 'Other'),
        ],
        string='Instrument Type',
        required=True,
        default='loan',
        tracking=True,
    )

    # Flow direction
    flow_direction = fields.Selection(
        selection=[
            ('inbound', 'Inbound (Financing received)'),
            ('outbound', 'Outbound (Financing granted)'),
        ],
        string='Flow Direction',
        required=True,
        default='inbound',
        tracking=True,
        help='Inbound: money received (loan from bank)\n'
             'Outbound: money granted (loan to partners)',
    )

    # Partner (bank, leasing company, partner)
    partner_id = fields.Many2one(
        'res.partner',
        string='Counterpart',
        tracking=True,
        help='Bank, leasing company, or partner',
    )

    # Amounts
    principal_amount = fields.Monetary(
        string='Principal Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    disbursed_amount = fields.Monetary(
        string='Disbursed Amount',
        currency_field='currency_id',
        tracking=True,
        help='Amount actually disbursed (may differ from principal)',
    )
    residual_principal = fields.Monetary(
        string='Residual Principal',
        currency_field='currency_id',
        compute='_compute_residual',
        store=True,
    )
    total_interest = fields.Monetary(
        string='Total Interest',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    total_paid = fields.Monetary(
        string='Total Paid',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )

    # Interest
    interest_rate = fields.Float(
        string='Interest Rate (%)',
        digits=(5, 4),
        tracking=True,
    )
    rate_type = fields.Selection(
        selection=[
            ('fixed', 'Fixed Rate'),
            ('variable', 'Variable Rate'),
            ('mixed', 'Mixed'),
        ],
        string='Rate Type',
        default='fixed',
        tracking=True,
    )
    spread = fields.Float(
        string='Spread (%)',
        digits=(5, 4),
        tracking=True,
        help='Spread over reference rate for variable rates',
    )
    reference_rate = fields.Selection(
        selection=[
            ('euribor_1m', 'Euribor 1M'),
            ('euribor_3m', 'Euribor 3M'),
            ('euribor_6m', 'Euribor 6M'),
            ('euribor_12m', 'Euribor 12M'),
            ('other', 'Other'),
        ],
        string='Reference Rate',
    )

    # Dates
    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
    )
    first_installment_date = fields.Date(
        string='First Installment Date',
        tracking=True,
    )

    # Installments
    installment_ids = fields.One2many(
        'treasury.installment',
        'instrument_id',
        string='Installments',
    )
    installment_count = fields.Integer(
        string='Number of Installments',
        compute='_compute_installment_count',
    )
    installment_frequency = fields.Selection(
        selection=[
            ('monthly', 'Monthly'),
            ('bimonthly', 'Bi-Monthly'),
            ('quarterly', 'Quarterly'),
            ('semi_annual', 'Semi-Annual'),
            ('annual', 'Annual'),
            ('bullet', 'Bullet (Single payment)'),
        ],
        string='Installment Frequency',
        default='monthly',
        tracking=True,
    )
    total_installments = fields.Integer(
        string='Total Number of Installments',
        tracking=True,
    )

    # Amortization
    amortization_type = fields.Selection(
        selection=[
            ('french', 'French (Constant installment)'),
            ('italian', 'Italian (Constant principal)'),
            ('bullet', 'Bullet'),
            ('custom', 'Custom'),
        ],
        string='Amortization Type',
        default='french',
        tracking=True,
    )

    # Status
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('closed', 'Closed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    # Additional info
    purpose = fields.Char(
        string='Purpose',
        tracking=True,
    )
    guarantee_type = fields.Selection(
        selection=[
            ('none', 'None'),
            ('mortgage', 'Mortgage'),
            ('pledge', 'Pledge'),
            ('personal', 'Personal Guarantee'),
            ('confidi', 'Confidi'),
            ('mcc', 'MCC (Fondo di Garanzia)'),
            ('other', 'Other'),
        ],
        string='Guarantee Type',
        default='none',
        tracking=True,
    )
    guarantee_notes = fields.Text(string='Guarantee Notes')
    notes = fields.Html(string='Notes')

    # Accounting configuration
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        tracking=True,
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        help='Journal for accounting entries',
    )
    long_term_account_id = fields.Many2one(
        'account.account',
        string='Long-term Account',
        tracking=True,
        help='Liability (inbound) or Asset (outbound) account for maturities > 12 months',
    )
    short_term_account_id = fields.Many2one(
        'account.account',
        string='Short-term Account',
        tracking=True,
        help='Liability (inbound) or Asset (outbound) account for maturities <= 12 months',
    )
    interest_account_id = fields.Many2one(
        'account.account',
        string='Interest Account',
        tracking=True,
        help='Interest expense (inbound) or income (outbound) account',
    )
    disbursement_account_id = fields.Many2one(
        'account.account',
        string='Disbursement Account',
        tracking=True,
        help='Bank account for loan disbursement',
    )

    # Accounting options
    enable_lt_st_reclassification = fields.Boolean(
        string='Enable LT/ST Reclassification',
        default=False,
        tracking=True,
        help='If enabled, generate monthly reclassification entries '
             'from long-term to short-term for installments due within 12 months',
    )

    # Accounting links
    disbursement_move_id = fields.Many2one(
        'account.move',
        string='Disbursement Entry',
        readonly=True,
        copy=False,
        help='Journal entry for initial loan disbursement',
    )
    vendor_bill_ids = fields.Many2many(
        'account.move',
        'treasury_instrument_vendor_bill_rel',
        'instrument_id',
        'move_id',
        string='Linked Vendor Bills',
        domain="[('move_type', 'in', ['in_invoice', 'in_refund'])]",
        copy=False,
        help='Vendor invoices related to this financial instrument',
    )
    move_ids = fields.One2many(
        'account.move',
        'treasury_instrument_id',
        string='Journal Entries',
        readonly=True,
    )
    move_count = fields.Integer(
        string='Entries Count',
        compute='_compute_move_count',
    )

    @api.depends('installment_ids.principal', 'installment_ids.state', 'principal_amount')
    def _compute_residual(self):
        for instrument in self:
            paid_principal = sum(
                instrument.installment_ids.filtered(
                    lambda i: i.state == 'paid'
                ).mapped('principal')
            )
            instrument.residual_principal = instrument.principal_amount - paid_principal

    @api.depends('installment_ids.interest', 'installment_ids.total', 'installment_ids.state')
    def _compute_totals(self):
        for instrument in self:
            instrument.total_interest = sum(instrument.installment_ids.mapped('interest'))
            instrument.total_paid = sum(
                instrument.installment_ids.filtered(
                    lambda i: i.state == 'paid'
                ).mapped('total')
            )

    @api.depends('installment_ids')
    def _compute_installment_count(self):
        for instrument in self:
            instrument.installment_count = len(instrument.installment_ids)

    @api.depends('move_ids', 'disbursement_move_id')
    def _compute_move_count(self):
        for instrument in self:
            count = len(instrument.move_ids)
            if instrument.disbursement_move_id:
                count += 1
            instrument.move_count = count

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for instrument in self:
            if instrument.start_date and instrument.end_date:
                if instrument.start_date > instrument.end_date:
                    raise ValidationError(_('Start date must be before end date.'))

    def action_activate(self):
        """Activate the financial instrument."""
        self.write({'state': 'active'})

    def action_close(self):
        """Close the financial instrument."""
        for instrument in self:
            unpaid = instrument.installment_ids.filtered(lambda i: i.state != 'paid')
            if unpaid:
                raise ValidationError(
                    _('Cannot close instrument with unpaid installments. '
                      'Remaining: %(count)s installments',
                      count=len(unpaid))
                )
        self.write({'state': 'closed'})

    def action_cancel(self):
        """Cancel the financial instrument."""
        self.write({'state': 'cancelled'})

    def _validate_accounting_config(self):
        """Validate that accounting configuration is complete for entry generation."""
        self.ensure_one()
        missing = []
        if not self.journal_id:
            missing.append(_('Journal'))
        if not self.long_term_account_id:
            missing.append(_('Long-term Account'))
        if not self.disbursement_account_id:
            missing.append(_('Disbursement Account'))

        if missing:
            raise ValidationError(
                _('Missing accounting configuration for %(name)s:\n%(fields)s',
                  name=self.name,
                  fields='\n'.join(f'- {f}' for f in missing))
            )

    def _prepare_disbursement_move_vals(self):
        """Prepare values for disbursement journal entry."""
        self.ensure_one()
        amount = self.disbursed_amount or self.principal_amount

        if self.flow_direction == 'inbound':
            # Finanziamento ricevuto: Dare Banca, Avere Passività
            lines = [
                (0, 0, {
                    'name': _('Disbursement - %(name)s', name=self.name),
                    'account_id': self.disbursement_account_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': _('Loan - %(name)s', name=self.name),
                    'account_id': self.long_term_account_id.id,
                    'debit': 0.0,
                    'credit': amount,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                }),
            ]
        else:
            # Finanziamento concesso: Dare Credito, Avere Banca
            lines = [
                (0, 0, {
                    'name': _('Loan granted - %(name)s', name=self.name),
                    'account_id': self.long_term_account_id.id,
                    'debit': amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                }),
                (0, 0, {
                    'name': _('Disbursement - %(name)s', name=self.name),
                    'account_id': self.disbursement_account_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ]

        return {
            'move_type': 'entry',
            'date': self.start_date,
            'ref': _('Disbursement %(ref)s', ref=self.reference or self.name),
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'line_ids': lines,
        }

    def action_generate_disbursement_entry(self):
        """Generate the disbursement journal entry."""
        self.ensure_one()
        if self.disbursement_move_id:
            raise ValidationError(
                _('Disbursement entry already exists for %(name)s.',
                  name=self.name)
            )

        self._validate_accounting_config()

        move_vals = self._prepare_disbursement_move_vals()
        move = self.env['account.move'].create(move_vals)
        self.disbursement_move_id = move

        return {
            'type': 'ir.actions.act_window',
            'name': _('Disbursement Entry'),
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }

    def action_view_moves(self):
        """Open all related journal entries."""
        self.ensure_one()
        move_ids = self.move_ids.ids
        if self.disbursement_move_id:
            move_ids.append(self.disbursement_move_id.id)

        if len(move_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Journal Entry'),
                'res_model': 'account.move',
                'res_id': move_ids[0],
                'view_mode': 'form',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entries'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', move_ids)],
        }

    def action_generate_installments(self):
        """Generate installment schedule."""
        self.ensure_one()
        if self.installment_ids:
            raise ValidationError(
                _('Installments already exist. Delete them first to regenerate.')
            )

        if not self.total_installments or self.total_installments <= 0:
            raise ValidationError(_('Please set the total number of installments.'))

        if self.amortization_type == 'bullet':
            self._generate_bullet_installment()
        elif self.amortization_type == 'french':
            self._generate_french_installments()
        elif self.amortization_type == 'italian':
            self._generate_italian_installments()
        else:
            raise ValidationError(_('Custom amortization requires manual entry of installments.'))

        return True

    def _get_period_months(self):
        """Get number of months between installments."""
        frequency_months = {
            'monthly': 1,
            'bimonthly': 2,
            'quarterly': 3,
            'semi_annual': 6,
            'annual': 12,
            'bullet': 0,
        }
        return frequency_months.get(self.installment_frequency, 1)

    def _generate_bullet_installment(self):
        """Generate single bullet payment at end."""
        self.env['treasury.installment'].create({
            'instrument_id': self.id,
            'sequence': 1,
            'date': self.end_date,
            'residual_before': self.principal_amount,
            'principal': self.principal_amount,
            'interest': self._calculate_total_interest(),
        })

    def _calculate_total_interest(self):
        """Calculate total interest for bullet payment."""
        if not self.interest_rate or not self.start_date or not self.end_date:
            return 0.0
        days = (self.end_date - self.start_date).days
        return self.principal_amount * (self.interest_rate / 100) * (days / 365)

    def _generate_french_installments(self):
        """Generate French (constant installment) amortization schedule."""
        n = self.total_installments
        r = (self.interest_rate / 100) / 12  # Monthly rate
        P = self.principal_amount

        if r > 0:
            # PMT formula
            installment_amount = P * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
        else:
            installment_amount = P / n

        remaining = P
        period_months = self._get_period_months()
        current_date = self.first_installment_date or self.start_date

        for seq in range(1, n + 1):
            interest = remaining * r * period_months if r > 0 else 0
            principal = installment_amount - interest

            # Last installment adjustment
            if seq == n:
                principal = remaining
                interest = installment_amount - principal if installment_amount > principal else 0

            self.env['treasury.installment'].create({
                'instrument_id': self.id,
                'sequence': seq,
                'date': current_date,
                'residual_before': remaining,
                'principal': principal,
                'interest': interest,
            })

            remaining -= principal
            current_date = current_date + relativedelta(months=period_months)

    def _generate_italian_installments(self):
        """Generate Italian (constant principal) amortization schedule."""
        n = self.total_installments
        r = (self.interest_rate / 100) / 12  # Monthly rate
        P = self.principal_amount
        constant_principal = P / n

        remaining = P
        period_months = self._get_period_months()
        current_date = self.first_installment_date or self.start_date

        for seq in range(1, n + 1):
            interest = remaining * r * period_months if r > 0 else 0
            principal = constant_principal

            # Last installment adjustment
            if seq == n:
                principal = remaining

            self.env['treasury.installment'].create({
                'instrument_id': self.id,
                'sequence': seq,
                'date': current_date,
                'residual_before': remaining,
                'principal': principal,
                'interest': interest,
            })

            remaining -= principal
            current_date = current_date + relativedelta(months=period_months)

    def action_view_installments(self):
        """Open installments view."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Installments'),
            'res_model': 'treasury.installment',
            'view_mode': 'list,form',
            'domain': [('instrument_id', '=', self.id)],
            'context': {'default_instrument_id': self.id},
        }
