from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TreasuryAccount(models.Model):
    _name = 'treasury.account'
    _description = 'Treasury Account'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)

    account_type = fields.Selection(
        selection=[
            ('bank', 'Bank Account'),
            ('cash', 'Cash'),
            ('internal', 'Internal Account'),
        ],
        string='Account Type',
        required=True,
        default='bank',
        tracking=True,
    )

    # Link to Odoo accounting
    journal_id = fields.Many2one(
        'account.journal',
        string='Accounting Journal',
        domain="[('type', 'in', ['bank', 'cash'])]",
        tracking=True,
        help='Link to the accounting journal for this treasury account',
    )

    # Bank details
    bank_id = fields.Many2one(
        'res.bank',
        string='Bank',
        tracking=True,
    )
    bank_account_id = fields.Many2one(
        'res.partner.bank',
        string='Bank Account',
        tracking=True,
        help='Bank account with IBAN details',
    )
    iban = fields.Char(
        string='IBAN',
        related='bank_account_id.acc_number',
        readonly=True,
    )
    bic = fields.Char(
        string='BIC/SWIFT',
        related='bank_account_id.bank_bic',
        readonly=True,
    )

    # Currency
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )

    # Opening balance
    opening_balance = fields.Monetary(
        string='Opening Balance',
        currency_field='currency_id',
        tracking=True,
    )
    opening_date = fields.Date(
        string='Opening Date',
        tracking=True,
    )

    # Cash reserve associated with this account, available on top of the credit
    # lines when projecting liquidity (minimum cash reserve / float / petty
    # cash). Generic; the tenant sets it per account. Default 0.
    cash_buffer = fields.Monetary(
        string='Cash Buffer',
        currency_field='currency_id',
        tracking=True,
        help='Cash reserve available in addition to the credit lines when '
             'projecting treasury liquidity. Leave 0 if not used.',
    )

    # Computed balances
    current_balance = fields.Monetary(
        string='Current Balance',
        currency_field='currency_id',
        compute='_compute_balances',
        store=False,
    )
    available_balance = fields.Monetary(
        string='Available Balance',
        currency_field='currency_id',
        compute='_compute_balances',
        store=False,
        help='Current balance plus available credit lines',
    )

    # Related records
    credit_line_ids = fields.One2many(
        'treasury.credit.line',
        'account_id',
        string='Credit Lines',
    )
    financial_instrument_ids = fields.One2many(
        'treasury.financial.instrument',
        'account_id',
        string='Financial Instruments',
    )

    # Credit lines summary
    total_credit_limit = fields.Monetary(
        string='Total Credit Limit',
        currency_field='currency_id',
        compute='_compute_credit_summary',
    )
    total_credit_used = fields.Monetary(
        string='Credit Used',
        currency_field='currency_id',
        compute='_compute_credit_summary',
    )
    total_credit_available = fields.Monetary(
        string='Credit Available',
        currency_field='currency_id',
        compute='_compute_credit_summary',
    )

    # Notes
    notes = fields.Html(string='Notes')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'The code must be unique per company!'),
    ]

    @api.depends('journal_id', 'opening_balance', 'credit_line_ids.available_amount')
    def _compute_balances(self):
        for account in self:
            balance = account.opening_balance or 0.0

            # Get balance from linked journal if available
            if account.journal_id:
                # Use journal's default account balance
                if account.journal_id.default_account_id:
                    domain = [
                        ('account_id', '=', account.journal_id.default_account_id.id),
                        ('parent_state', '=', 'posted'),
                        ('company_id', '=', account.company_id.id),
                    ]
                    move_lines = self.env['account.move.line'].search(domain)
                    balance = sum(move_lines.mapped('balance'))

            account.current_balance = balance

            # Available = current + available credit
            credit_available = sum(account.credit_line_ids.filtered(
                lambda l: l.state == 'active'
            ).mapped('available_amount'))
            account.available_balance = balance + credit_available

    @api.depends('credit_line_ids.limit_amount', 'credit_line_ids.used_amount', 'credit_line_ids.state')
    def _compute_credit_summary(self):
        for account in self:
            active_lines = account.credit_line_ids.filtered(lambda l: l.state == 'active')
            account.total_credit_limit = sum(active_lines.mapped('limit_amount'))
            account.total_credit_used = sum(active_lines.mapped('used_amount'))
            account.total_credit_available = sum(active_lines.mapped('available_amount'))

    @api.constrains('journal_id', 'company_id')
    def _check_journal_company(self):
        for account in self:
            if account.journal_id and account.journal_id.company_id != account.company_id:
                raise ValidationError(
                    _('The journal must belong to the same company as the treasury account.')
                )

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id:
            self.bank_id = self.journal_id.bank_id
            self.bank_account_id = self.journal_id.bank_account_id
            self.currency_id = self.journal_id.currency_id or self.env.company.currency_id
            if not self.name:
                self.name = self.journal_id.name

    @api.onchange('bank_account_id')
    def _onchange_bank_account_id(self):
        if self.bank_account_id:
            self.bank_id = self.bank_account_id.bank_id

    def action_view_journal_entries(self):
        """Open journal entries related to this treasury account."""
        self.ensure_one()
        if not self.journal_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entries'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('journal_id', '=', self.journal_id.id)],
            'context': {'default_journal_id': self.journal_id.id},
        }

    def action_view_credit_lines(self):
        """Open credit lines for this treasury account."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Credit Lines'),
            'res_model': 'treasury.credit.line',
            'view_mode': 'list,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }
