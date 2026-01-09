from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api


class CashflowRecurring(models.Model):
    _name = 'cashflow.recurring'
    _description = 'Recurring Cashflow Template'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    type = fields.Selection([
        ('in', 'Cash In'),
        ('out', 'Cash Out'),
    ], required=True, default='out')
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Bank',
        domain=[('type', '=', 'bank')],
    )
    description = fields.Char()

    # Recurrence settings
    recurrence_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], required=True, default='monthly')
    day_of_month = fields.Integer(
        default=1,
        help='Day of the month for the recurring entry (1-28)',
    )
    advance_days = fields.Integer(
        default=30,
        help='Generate forecast entries this many days in advance',
    )

    # Matching settings
    matching_enabled = fields.Boolean(
        string='Enable Matching',
        default=True,
        help='When enabled, recurring entries will be matched and replaced by actual invoices',
    )
    matching_mode = fields.Selection([
        ('auto', 'Automatic'),
        ('manual', 'Manual'),
    ], string='Matching Mode', default='auto',
        help='Automatic: recurring entry is deleted when match found\n'
             'Manual: creates a match record for user to review and confirm',
    )
    matching_tolerance_days = fields.Integer(
        string='Date Tolerance (days)',
        default=5,
        help='Tolerance in days for matching dates',
    )
    matching_tolerance_amount = fields.Float(
        string='Amount Tolerance (%)',
        default=10.0,
        help='Tolerance percentage for matching amounts',
    )

    # Tracking
    last_generated_date = fields.Date(
        string='Last Generated',
        readonly=True,
    )
    next_generation_date = fields.Date(
        string='Next Generation',
        compute='_compute_next_generation_date',
        store=True,
    )
    entry_count = fields.Integer(
        compute='_compute_entry_count',
        string='Entries',
    )

    @api.depends('last_generated_date', 'recurrence_type', 'day_of_month')
    def _compute_next_generation_date(self):
        today = fields.Date.today()
        for rec in self:
            if not rec.last_generated_date:
                # Never generated, start from current month
                next_date = today.replace(day=min(rec.day_of_month or 1, 28))
                if next_date < today:
                    next_date = next_date + relativedelta(months=1)
            else:
                # Calculate next date based on recurrence type
                if rec.recurrence_type == 'monthly':
                    next_date = rec.last_generated_date + relativedelta(months=1)
                elif rec.recurrence_type == 'quarterly':
                    next_date = rec.last_generated_date + relativedelta(months=3)
                else:  # yearly
                    next_date = rec.last_generated_date + relativedelta(years=1)
            rec.next_generation_date = next_date

    def _compute_entry_count(self):
        for rec in self:
            rec.entry_count = self.env['cashflow.entry'].search_count([
                ('recurring_id', '=', rec.id),
            ])

    def action_view_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cashflow Entries',
            'res_model': 'cashflow.entry',
            'view_mode': 'list,form',
            'domain': [('recurring_id', '=', self.id)],
            'context': {'default_recurring_id': self.id},
        }

    def action_generate_entries(self):
        """Manual generation of entries."""
        # Reset last_generated_date if no entries exist
        for rec in self:
            if not self.env['cashflow.entry'].search_count([('recurring_id', '=', rec.id)]):
                rec.last_generated_date = False
        self.generate_entries()

    def generate_entries(self):
        """Generate forecast entries for upcoming dates."""
        today = fields.Date.today()
        CashflowEntry = self.env['cashflow.entry']
        CashflowItem = self.env['cashflow.item']

        for rec in self.filtered('active'):
            # Calculate target date
            target_date = today + relativedelta(days=rec.advance_days)

            # Generate entries up to target date
            current_date = rec.next_generation_date or today.replace(
                day=min(rec.day_of_month or 1, 28)
            )

            while current_date and current_date <= target_date:
                # Check if entry already exists for this date
                existing = CashflowEntry.search([
                    ('recurring_id', '=', rec.id),
                    ('date', '=', current_date),
                ], limit=1)

                if not existing:
                    # Create entry
                    entry_vals = {
                        'name': f"{rec.name} - {current_date.strftime('%B %Y')}",
                        'date': current_date,
                        'state': 'draft',
                        'entry_type': 'forecast',
                        'source_type': 'recurring',
                        'recurring_id': rec.id,
                        'journal_id': rec.journal_id.id if rec.journal_id else False,
                    }
                    entry = CashflowEntry.create(entry_vals)

                    # Create item
                    item_vals = {
                        'entry_id': entry.id,
                        'date': current_date,
                        'amount': rec.amount,
                        'currency_id': rec.currency_id.id,
                        'type': rec.type,
                        'partner_id': rec.partner_id.id if rec.partner_id else False,
                        'description': rec.description or rec.name,
                    }
                    CashflowItem.create(item_vals)

                # Update last generated date
                rec.last_generated_date = current_date

                # Calculate next date
                if rec.recurrence_type == 'monthly':
                    current_date = current_date + relativedelta(months=1)
                elif rec.recurrence_type == 'quarterly':
                    current_date = current_date + relativedelta(months=3)
                else:  # yearly
                    current_date = current_date + relativedelta(years=1)

    @api.model
    def cron_generate_recurring(self):
        """Cron method to generate recurring entries."""
        templates = self.search([('active', '=', True)])
        templates.generate_entries()

    @api.model
    def find_matching_recurring_entry(self, partner_id, amount, target_date):
        """Find a recurring entry that matches the given criteria.

        Returns the matching cashflow.entry or False.
        """
        if not partner_id:
            return False

        # Find recurring templates for this partner with matching enabled
        templates = self.search([
            ('partner_id', '=', partner_id),
            ('matching_enabled', '=', True),
            ('active', '=', True),
        ])

        for template in templates:
            # Calculate date range
            tolerance_days = template.matching_tolerance_days or 5
            date_from = target_date - relativedelta(days=tolerance_days)
            date_to = target_date + relativedelta(days=tolerance_days)

            # Calculate amount range
            tolerance_pct = (template.matching_tolerance_amount or 10.0) / 100.0
            amount_min = amount * (1 - tolerance_pct)
            amount_max = amount * (1 + tolerance_pct)

            # Search for matching entry
            entries = self.env['cashflow.entry'].search([
                ('recurring_id', '=', template.id),
                ('source_type', '=', 'recurring'),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ])

            for entry in entries:
                # Check amount
                entry_amount = sum(entry.item_ids.mapped('amount'))
                if amount_min <= entry_amount <= amount_max:
                    return entry

        return False
