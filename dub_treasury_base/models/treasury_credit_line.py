from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval, datetime as safe_datetime
from datetime import date


class TreasuryCreditLine(models.Model):
    _name = 'treasury.credit.line'
    _description = 'Treasury Credit Line'
    _order = 'account_id, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
    )
    account_id = fields.Many2one(
        'treasury.account',
        string='Treasury Account',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    company_id = fields.Many2one(
        related='account_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='account_id.currency_id',
        store=True,
        readonly=True,
    )

    credit_type = fields.Selection(
        selection=[
            ('overdraft', 'Overdraft (Scoperto di conto)'),
            ('advance', 'Advance on Invoices (Anticipo fatture)'),
            ('discount', 'Bills Discount (Sconto effetti)'),
            ('factoring', 'Factoring'),
            ('sbf', 'Subject to Collection (SBF)'),
            ('other', 'Other'),
        ],
        string='Credit Type',
        required=True,
        default='overdraft',
        tracking=True,
    )

    # Amounts
    limit_amount = fields.Monetary(
        string='Credit Limit',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    auto_compute_usage = fields.Boolean(
        string='Auto-compute Usage',
        default=True,
        help='If enabled, usage is computed from the journal balance (for overdraft) '
             'or must be updated via the Refresh button. Disable for manual entry.',
    )
    manual_used_amount = fields.Monetary(
        string='Manual Used Amount',
        currency_field='currency_id',
        tracking=True,
        help='Manually entered used amount (when auto-compute is disabled)',
    )
    used_amount = fields.Monetary(
        string='Used Amount',
        currency_field='currency_id',
        compute='_compute_used_amount',
        inverse='_inverse_used_amount',
        store=True,
        help='Amount currently used from this credit line',
    )
    available_amount = fields.Monetary(
        string='Available Amount',
        currency_field='currency_id',
        compute='_compute_available_amount',
        store=True,
    )
    utilization_rate = fields.Float(
        string='Utilization Rate (%)',
        compute='_compute_available_amount',
        store=True,
    )

    # Conditions
    interest_rate = fields.Float(
        string='Interest Rate (%)',
        digits=(5, 2),
        tracking=True,
    )
    spread = fields.Float(
        string='Spread (%)',
        digits=(5, 2),
        tracking=True,
        help='Spread over reference rate (Euribor, etc.)',
    )
    commission_rate = fields.Float(
        string='Commission (%)',
        digits=(5, 2),
        tracking=True,
        help='Annual commission on unused amount',
    )

    # Dates
    start_date = fields.Date(
        string='Start Date',
        tracking=True,
    )
    expiry_date = fields.Date(
        string='Expiry Date',
        tracking=True,
    )
    renewal_date = fields.Date(
        string='Next Renewal',
        tracking=True,
    )

    # Status
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    # Bank/Partner
    bank_id = fields.Many2one(
        'res.bank',
        string='Bank',
        related='account_id.bank_id',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Bank Partner',
        tracking=True,
        help='Bank as partner for accounting purposes',
    )

    # Covenants
    covenant_ids = fields.One2many(
        'treasury.covenant',
        'credit_line_id',
        string='Covenants',
    )

    # Notes
    notes = fields.Html(string='Notes')
    contract_reference = fields.Char(
        string='Contract Reference',
        tracking=True,
    )

    # Accounting configuration
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        tracking=True,
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        help='Journal for credit line accounting entries',
    )
    credit_account_id = fields.Many2one(
        'account.account',
        string='Credit Line Account',
        tracking=True,
        help='Liability account for the credit line balance',
    )
    bank_account_id = fields.Many2one(
        'account.account',
        string='Bank Account',
        tracking=True,
        help='Bank account for utilizations and repayments',
    )
    interest_account_id = fields.Many2one(
        'account.account',
        string='Interest Account',
        tracking=True,
        help='Interest expense account',
    )

    # Accounting links
    utilization_move_ids = fields.One2many(
        'account.move',
        'credit_line_id',
        string='Movements',
        readonly=True,
    )
    move_count = fields.Integer(
        string='Movements Count',
        compute='_compute_move_count',
    )

    # Linked invoices (customer invoices for advance/SBF/factoring, vendor bills for costs)
    linked_invoice_ids = fields.Many2many(
        'account.move',
        'treasury_credit_line_vendor_bill_rel',
        'credit_line_id',
        'move_id',
        string='Linked Invoices',
        domain="[('move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')), ('company_id', '=', company_id)]",
        help='Customer invoices (for advance, SBF, factoring) and vendor bills '
             '(for interest charges, fees) linked to this credit line',
    )
    linked_invoice_count = fields.Integer(
        string='Invoice Count',
        compute='_compute_linked_invoice_count',
    )

    @api.depends('linked_invoice_ids')
    def _compute_linked_invoice_count(self):
        for line in self:
            line.linked_invoice_count = len(line.linked_invoice_ids)

    @api.depends('auto_compute_usage', 'manual_used_amount', 'credit_type',
                 'account_id.journal_id', 'account_id.journal_id.default_account_id',
                 'linked_invoice_ids', 'linked_invoice_ids.amount_residual',
                 'linked_invoice_ids.state', 'linked_invoice_ids.payment_state')
    def _compute_used_amount(self):
        """Compute used amount based on settings and credit type."""
        for line in self:
            if not line.auto_compute_usage:
                # Manual mode: use manual_used_amount
                line.used_amount = line.manual_used_amount
            elif line.credit_type == 'overdraft':
                # Overdraft: compute from negative journal balance
                line.used_amount = line._get_overdraft_usage()
            else:
                # Other types (advance, sbf, factoring, etc.): compute from linked invoices
                line.used_amount = line._get_invoice_based_usage()

    def _inverse_used_amount(self):
        """Allow direct editing of used_amount by storing in manual field."""
        for line in self:
            line.manual_used_amount = line.used_amount

    def _get_overdraft_usage(self):
        """Calculate overdraft usage from journal balance.

        If the bank account has a negative balance, the absolute value
        represents the overdraft usage.
        """
        self.ensure_one()
        if not self.account_id or not self.account_id.journal_id:
            return 0.0

        journal = self.account_id.journal_id
        if not journal.default_account_id:
            return 0.0

        # Get the balance of the journal's default account
        domain = [
            ('account_id', '=', journal.default_account_id.id),
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        balance = sum(self.env['account.move.line'].search(domain).mapped('balance'))

        # If balance is negative, the overdraft is being used
        if balance < 0:
            return abs(balance)
        return 0.0

    def _get_invoice_based_usage(self):
        """Calculate usage from linked invoices.

        For credit types like advance, sbf, factoring, etc., the usage
        is the sum of unpaid linked invoices.
        """
        self.ensure_one()
        if not self.linked_invoice_ids:
            return 0.0

        # Sum the residual amount of posted, unpaid invoices
        total = 0.0
        for invoice in self.linked_invoice_ids:
            if invoice.state == 'posted' and invoice.payment_state not in ('paid', 'reversed'):
                # Use amount_residual for the unpaid portion
                total += abs(invoice.amount_residual)
        return total

    def action_refresh_usage(self):
        """Manually refresh the used amount calculation."""
        for line in self:
            if line.auto_compute_usage:
                if line.credit_type == 'overdraft':
                    # For overdraft, store the computed value
                    line.manual_used_amount = line._get_overdraft_usage()
                # For invoice-based types, the computation is automatic
                # Just invalidate to trigger recomputation
                line.invalidate_recordset(['used_amount', 'available_amount', 'utilization_rate'])
        return True

    @api.depends('limit_amount', 'used_amount')
    def _compute_available_amount(self):
        for line in self:
            line.available_amount = line.limit_amount - line.used_amount
            if line.limit_amount:
                line.utilization_rate = (line.used_amount / line.limit_amount) * 100
            else:
                line.utilization_rate = 0.0

    @api.constrains('used_amount', 'limit_amount')
    def _check_used_amount(self):
        for line in self:
            if line.used_amount > line.limit_amount:
                raise ValidationError(
                    _('Used amount (%(used)s) cannot exceed credit limit (%(limit)s).',
                      used=line.used_amount, limit=line.limit_amount)
                )

    @api.constrains('start_date', 'expiry_date')
    def _check_dates(self):
        for line in self:
            if line.start_date and line.expiry_date and line.start_date > line.expiry_date:
                raise ValidationError(_('Start date must be before expiry date.'))

    def action_activate(self):
        """Activate the credit line."""
        self.write({'state': 'active'})

    def action_close(self):
        """Close the credit line."""
        for line in self:
            if line.used_amount > 0:
                raise ValidationError(
                    _('Cannot close credit line with used amount. Current usage: %(amount)s',
                      amount=line.used_amount)
                )
        self.write({'state': 'closed'})

    def action_expire(self):
        """Mark the credit line as expired."""
        self.write({'state': 'expired'})

    @api.model
    def _cron_check_expiry(self):
        """Cron job to check and update expired credit lines."""
        today = date.today()
        expired_lines = self.search([
            ('state', '=', 'active'),
            ('expiry_date', '<', today),
        ])
        expired_lines.write({'state': 'expired'})

    @api.depends('utilization_move_ids')
    def _compute_move_count(self):
        for line in self:
            line.move_count = len(line.utilization_move_ids)

    def _validate_accounting_config(self):
        """Validate that accounting configuration is complete."""
        self.ensure_one()
        missing = []
        if not self.journal_id:
            missing.append(_('Journal'))
        if not self.credit_account_id:
            missing.append(_('Credit Line Account'))
        if not self.bank_account_id:
            missing.append(_('Bank Account'))

        if missing:
            raise ValidationError(
                _('Missing accounting configuration for %(name)s:\n%(fields)s',
                  name=self.name,
                  fields='\n'.join(f'- {f}' for f in missing))
            )

    def _prepare_utilization_move_vals(self, amount, memo=False):
        """Prepare values for utilization (drawing) journal entry.

        Debit: Bank account (receiving cash)
        Credit: Credit line liability (increasing debt)
        """
        self.ensure_one()
        self._validate_accounting_config()

        return {
            'move_type': 'entry',
            'date': date.today(),
            'ref': memo or _('Utilization - %(name)s', name=self.name),
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'credit_line_id': self.id,
            'credit_line_movement_type': 'utilization',
            'line_ids': [
                (0, 0, {
                    'name': _('Utilization - %(name)s', name=self.name),
                    'account_id': self.bank_account_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': _('Credit Line - %(name)s', name=self.name),
                    'account_id': self.credit_account_id.id,
                    'debit': 0.0,
                    'credit': amount,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                }),
            ],
        }

    def _prepare_repayment_move_vals(self, amount, memo=False):
        """Prepare values for repayment journal entry.

        Debit: Credit line liability (reducing debt)
        Credit: Bank account (paying cash)
        """
        self.ensure_one()
        self._validate_accounting_config()

        return {
            'move_type': 'entry',
            'date': date.today(),
            'ref': memo or _('Repayment - %(name)s', name=self.name),
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'credit_line_id': self.id,
            'credit_line_movement_type': 'repayment',
            'line_ids': [
                (0, 0, {
                    'name': _('Repayment - %(name)s', name=self.name),
                    'account_id': self.credit_account_id.id,
                    'debit': amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                }),
                (0, 0, {
                    'name': _('Bank Payment - %(name)s', name=self.name),
                    'account_id': self.bank_account_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }

    def _prepare_interest_move_vals(self, amount, memo=False):
        """Prepare values for interest charge journal entry.

        Debit: Interest expense
        Credit: Bank account (or credit line liability)
        """
        self.ensure_one()
        self._validate_accounting_config()

        if not self.interest_account_id:
            raise ValidationError(
                _('Interest account not configured for %(name)s.', name=self.name)
            )

        return {
            'move_type': 'entry',
            'date': date.today(),
            'ref': memo or _('Interest - %(name)s', name=self.name),
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'credit_line_id': self.id,
            'credit_line_movement_type': 'interest',
            'line_ids': [
                (0, 0, {
                    'name': _('Interest Expense - %(name)s', name=self.name),
                    'account_id': self.interest_account_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': _('Interest Payment - %(name)s', name=self.name),
                    'account_id': self.bank_account_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }

    def action_view_moves(self):
        """Open all related journal entries."""
        self.ensure_one()
        if len(self.utilization_move_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Journal Entry'),
                'res_model': 'account.move',
                'res_id': self.utilization_move_ids.id,
                'view_mode': 'form',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entries'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.utilization_move_ids.ids)],
        }

    def action_view_linked_invoices(self):
        """Open linked invoices."""
        self.ensure_one()
        if len(self.linked_invoice_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Invoice'),
                'res_model': 'account.move',
                'res_id': self.linked_invoice_ids.id,
                'view_mode': 'form',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.linked_invoice_ids.ids)],
        }


class TreasuryCovenant(models.Model):
    _name = 'treasury.covenant'
    _description = 'Financial Covenant'
    _order = 'credit_line_id, name'

    name = fields.Char(
        string='Covenant Name',
        required=True,
    )
    credit_line_id = fields.Many2one(
        'treasury.credit.line',
        string='Credit Line',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        related='credit_line_id.company_id',
        store=True,
        readonly=True,
    )
    covenant_type = fields.Selection(
        selection=[
            ('debt_equity', 'Debt/Equity Ratio'),
            ('current_ratio', 'Current Ratio'),
            ('interest_coverage', 'Interest Coverage'),
            ('dscr', 'Debt Service Coverage Ratio'),
            ('leverage', 'Leverage Ratio'),
            ('other', 'Other'),
        ],
        string='Type',
        required=True,
    )
    threshold_value = fields.Float(
        string='Threshold Value',
        required=True,
    )
    comparison = fields.Selection(
        selection=[
            ('>=', 'Greater or Equal'),
            ('<=', 'Less or Equal'),
            ('>', 'Greater Than'),
            ('<', 'Less Than'),
            ('=', 'Equal'),
        ],
        string='Comparison',
        required=True,
        default='>=',
    )
    current_value = fields.Float(
        string='Current Value',
    )
    is_compliant = fields.Boolean(
        string='Compliant',
        compute='_compute_is_compliant',
        store=True,
    )
    check_date = fields.Date(
        string='Last Check Date',
    )
    frequency = fields.Selection(
        selection=[
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('semi_annual', 'Semi-Annual'),
            ('annual', 'Annual'),
        ],
        string='Check Frequency',
        default='quarterly',
    )
    notes = fields.Text(string='Notes')

    # Account configuration for automatic calculation
    # Numerator = (add accounts) - (subtract accounts)
    numerator_add_account_ids = fields.Many2many(
        'account.account',
        'covenant_numerator_add_account_rel',
        'covenant_id',
        'account_id',
        string='Numerator (+)',
        help='Accounts to ADD for the numerator.\n'
             'Examples:\n'
             '- Debt/Equity: Liability accounts\n'
             '- Current Ratio: Current asset accounts\n'
             '- Interest Coverage: Revenue accounts',
    )
    numerator_subtract_account_ids = fields.Many2many(
        'account.account',
        'covenant_numerator_subtract_account_rel',
        'covenant_id',
        'account_id',
        string='Numerator (-)',
        help='Accounts to SUBTRACT for the numerator.\n'
             'Examples:\n'
             '- Interest Coverage: Operating expense accounts (to get EBIT)\n'
             '- Leverage: Depreciation accounts (to get EBITDA)',
    )
    # Denominator = (add accounts) - (subtract accounts)
    denominator_add_account_ids = fields.Many2many(
        'account.account',
        'covenant_denominator_add_account_rel',
        'covenant_id',
        'account_id',
        string='Denominator (+)',
        help='Accounts to ADD for the denominator.\n'
             'Examples:\n'
             '- Debt/Equity: Equity accounts\n'
             '- Current Ratio: Current liability accounts\n'
             '- Interest Coverage: Interest expense accounts',
    )
    denominator_subtract_account_ids = fields.Many2many(
        'account.account',
        'covenant_denominator_subtract_account_rel',
        'covenant_id',
        'account_id',
        string='Denominator (-)',
        help='Accounts to SUBTRACT for the denominator (rarely used).',
    )
    numerator_value = fields.Float(
        string='Numerator',
        readonly=True,
        help='Calculated value: SUM(+) - SUM(-)',
    )
    denominator_value = fields.Float(
        string='Denominator',
        readonly=True,
        help='Calculated value: SUM(+) - SUM(-)',
    )

    # Custom Python formula option
    use_custom_formula = fields.Boolean(
        string='Use Custom Formula',
        default=False,
        help='Enable to use a custom Python formula instead of standard account configuration.',
    )
    custom_formula = fields.Text(
        string='Python Formula',
        help='''Python expression that returns the covenant value.

Available variables:
- balance(account_codes): Returns the sum of balances for the given account codes
  Example: balance('12%') returns total balance of accounts starting with 12
- abs(x): Absolute value
- round(x, n): Round to n decimals
- min(a, b), max(a, b): Minimum/maximum

Examples:
# Debt/Equity Ratio
abs(balance('2%')) / abs(balance('3%'))

# Current Ratio
abs(balance('21%') + balance('22%')) / abs(balance('41%') + balance('42%'))

# Interest Coverage (EBIT / Interest Expense)
(abs(balance('7%')) - abs(balance('6%'))) / abs(balance('661%'))

# DSCR (Cash Flow / Debt Service)
(abs(balance('7%')) - abs(balance('6%')) + abs(balance('68%'))) / (abs(balance('164%')) + abs(balance('661%')))
'''
    )

    @api.depends('current_value', 'threshold_value', 'comparison')
    def _compute_is_compliant(self):
        for covenant in self:
            if covenant.comparison == '>=':
                covenant.is_compliant = covenant.current_value >= covenant.threshold_value
            elif covenant.comparison == '<=':
                covenant.is_compliant = covenant.current_value <= covenant.threshold_value
            elif covenant.comparison == '>':
                covenant.is_compliant = covenant.current_value > covenant.threshold_value
            elif covenant.comparison == '<':
                covenant.is_compliant = covenant.current_value < covenant.threshold_value
            elif covenant.comparison == '=':
                covenant.is_compliant = covenant.current_value == covenant.threshold_value
            else:
                covenant.is_compliant = True

    def write(self, vals):
        """Send alert when covenant becomes non-compliant."""
        result = super().write(vals)
        if 'current_value' in vals:
            for covenant in self:
                if not covenant.is_compliant:
                    covenant._send_violation_alert()
        return result

    def _send_violation_alert(self):
        """Send notification when covenant is violated."""
        self.ensure_one()
        # Post message on the credit line
        self.credit_line_id.message_post(
            body=_(
                '<strong>⚠️ Covenant Violation Alert</strong><br/>'
                '<b>%(name)s</b> is non-compliant:<br/>'
                'Current value: <b>%(current)s</b><br/>'
                'Required: %(comparison)s <b>%(threshold)s</b>',
                name=self.name,
                current=self.current_value,
                comparison=self.comparison,
                threshold=self.threshold_value,
            ),
            subject=_('Covenant Violation: %s', self.name),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
        # Also create an activity for follow-up
        self.credit_line_id.activity_schedule(
            'mail.mail_activity_data_warning',
            summary=_('Covenant Violation: %s', self.name),
            note=_(
                'The covenant "%(name)s" is not compliant.\n'
                'Current: %(current)s, Required: %(comparison)s %(threshold)s',
                name=self.name,
                current=self.current_value,
                comparison=self.comparison,
                threshold=self.threshold_value,
            ),
        )

    def _get_account_balance(self, accounts, use_absolute=True):
        """Get the total balance of the given accounts.

        Args:
            accounts: recordset of account.account
            use_absolute: if True, return absolute value (default for ratios)
        """
        if not accounts:
            return 0.0

        domain = [
            ('account_id', 'in', accounts.ids),
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        lines = self.env['account.move.line'].search(domain)
        total = sum(lines.mapped('balance'))
        return abs(total) if use_absolute else total

    def _get_balance_by_code(self, account_code_pattern):
        """Get the total balance for accounts matching the code pattern.

        Args:
            account_code_pattern: string pattern with optional '%' wildcard
                                 e.g., '12%' matches '120000', '121000', etc.
        """
        self.ensure_one()
        if not account_code_pattern:
            return 0.0

        # Convert pattern with % wildcard to SQL LIKE
        if '%' in account_code_pattern:
            domain = [
                ('code', '=like', account_code_pattern),
                ('company_id', '=', self.company_id.id),
            ]
        else:
            domain = [
                ('code', '=', account_code_pattern),
                ('company_id', '=', self.company_id.id),
            ]

        accounts = self.env['account.account'].search(domain)
        if not accounts:
            return 0.0

        move_domain = [
            ('account_id', 'in', accounts.ids),
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        lines = self.env['account.move.line'].search(move_domain)
        return sum(lines.mapped('balance'))

    def _evaluate_custom_formula(self):
        """Safely evaluate the custom Python formula.

        Returns the calculated value from the formula.
        """
        self.ensure_one()
        if not self.custom_formula:
            raise ValidationError(
                _('No custom formula defined for "%(name)s".', name=self.name)
            )

        # Create a balance function that can be used in the formula
        def balance(code_pattern):
            return self._get_balance_by_code(code_pattern)

        # Safe evaluation context
        eval_context = {
            'balance': balance,
            'abs': abs,
            'round': round,
            'min': min,
            'max': max,
            'sum': sum,
        }

        try:
            result = safe_eval(self.custom_formula.strip(), eval_context, mode='eval', nocopy=True)
            return float(result) if result is not None else 0.0
        except ZeroDivisionError:
            return 0.0
        except Exception as e:
            raise ValidationError(
                _('Error evaluating formula for "%(name)s":\n%(error)s',
                  name=self.name, error=str(e))
            )

    def action_calculate_value(self):
        """Calculate current value from configured accounts or custom formula.

        Standard mode:
        Numerator = SUM(numerator_add_accounts) - SUM(numerator_subtract_accounts)
        Denominator = SUM(denominator_add_accounts) - SUM(denominator_subtract_accounts)
        Value = Numerator / Denominator

        Custom formula mode:
        Evaluates the Python expression in custom_formula field.
        """
        today = fields.Date.today()
        for covenant in self:
            if covenant.use_custom_formula:
                # Use custom Python formula
                covenant.current_value = round(covenant._evaluate_custom_formula(), 4)
                covenant.numerator_value = 0.0
                covenant.denominator_value = 0.0
            else:
                # Standard account-based calculation
                if not covenant.numerator_add_account_ids and not covenant.denominator_add_account_ids:
                    raise ValidationError(
                        _('Please configure at least numerator (+) and denominator (+) accounts for "%(name)s".',
                          name=covenant.name)
                    )

                # Calculate numerator: add - subtract
                num_add = covenant._get_account_balance(covenant.numerator_add_account_ids)
                num_sub = covenant._get_account_balance(covenant.numerator_subtract_account_ids)
                numerator = num_add - num_sub

                # Calculate denominator: add - subtract
                den_add = covenant._get_account_balance(covenant.denominator_add_account_ids)
                den_sub = covenant._get_account_balance(covenant.denominator_subtract_account_ids)
                denominator = den_add - den_sub

                covenant.numerator_value = numerator
                covenant.denominator_value = denominator

                if denominator != 0:
                    covenant.current_value = round(numerator / denominator, 4)
                else:
                    covenant.current_value = 0.0

            covenant.check_date = today

        return True
