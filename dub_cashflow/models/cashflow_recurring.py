import logging
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CashflowRecurring(models.Model):
    _name = 'cashflow.recurring'
    _description = 'Recurring Cashflow'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Bank',
        required=True,
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
    )
    partner_id = fields.Many2one('res.partner', string='Partner')
    category_id = fields.Many2one(
        'cashflow.category',
        string='Category',
        ondelete='set null',
    )
    flow_type = fields.Selection(
        selection=[('in', 'Cash In'), ('out', 'Cash Out')],
        string='Flow Type',
        required=True,
        default='out',
    )
    amount = fields.Monetary(required=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    recurrence_type = fields.Selection(
        selection=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly'),
        ],
        string='Recurrence',
        required=True,
        default='monthly',
    )
    recurrence_day = fields.Integer(
        string='Day of Month',
        default=1,
        help='Day of the month for monthly/quarterly/yearly recurrences (1-31). '
             'Clamped to the last day of shorter months.',
    )
    recurrence_month = fields.Integer(
        string='Month',
        default=1,
        help='Month (1-12) for yearly recurrences.',
    )
    recurrence_weekday = fields.Selection(
        selection=[
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
        ],
        string='Weekday',
        default='0',
        help='Weekday for weekly recurrences.',
    )

    date_start = fields.Date(string='Start Date', required=True, default=fields.Date.context_today)
    date_end = fields.Date(string='End Date')
    horizon_months = fields.Integer(
        string='Horizon (months)',
        default=12,
        help='How many months ahead the cron generates forecast entries.',
    )
    scenario_ids = fields.Many2many(
        'cashflow.scenario',
        'cashflow_recurring_scenario_rel',
        'recurring_id',
        'scenario_id',
        string='Scenarios',
        default=lambda self: self._default_scenario_ids(),
    )
    description_template = fields.Text(
        string='Description Template',
        help='Template for the generated entry name. Placeholders: '
             '{date}, {amount}, {partner}.',
    )

    entry_ids = fields.One2many(
        'cashflow.entry',
        'recurring_id',
        string='Generated Entries',
    )
    entry_count = fields.Integer(string='Entries', compute='_compute_entry_count')

    @api.model
    def _default_scenario_ids(self):
        base = self.env.ref('dub_cashflow.cashflow_scenario_base', raise_if_not_found=False)
        return [(4, base.id)] if base else False

    @api.depends('entry_ids')
    def _compute_entry_count(self):
        for rec in self:
            rec.entry_count = len(rec.entry_ids)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_end and rec.date_start and rec.date_end < rec.date_start:
                raise ValidationError(_('End date must be on or after the start date.'))

    @api.constrains('recurrence_day')
    def _check_recurrence_day(self):
        for rec in self:
            if rec.recurrence_type in ('monthly', 'quarterly', 'yearly'):
                if not 1 <= rec.recurrence_day <= 31:
                    raise ValidationError(_('Day of month must be between 1 and 31.'))

    @api.constrains('recurrence_month')
    def _check_recurrence_month(self):
        for rec in self:
            if rec.recurrence_type == 'yearly' and not 1 <= rec.recurrence_month <= 12:
                raise ValidationError(_('Month must be between 1 and 12.'))

    @api.constrains('horizon_months')
    def _check_horizon(self):
        for rec in self:
            if rec.horizon_months <= 0:
                raise ValidationError(_('Horizon (months) must be strictly positive.'))

    @staticmethod
    def _clamp_day(year, month, day):
        """Return a valid date, clamping the day to the last day of the month."""
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        return fields.Date.to_date('%04d-%02d-%02d' % (year, month, min(day, last_day)))

    def _compute_next_occurrences(self, date_from, date_to):
        """Return the sorted list of occurrence dates within [date_from, date_to].

        Bounded by date_start / date_end. Pure computation, no side effects.
        """
        self.ensure_one()
        date_from = max(date_from, self.date_start)
        if self.date_end:
            date_to = min(date_to, self.date_end)
        if date_from > date_to:
            return []

        occurrences = []
        if self.recurrence_type == 'daily':
            current = date_from
            while current <= date_to:
                occurrences.append(current)
                current += relativedelta(days=1)
        elif self.recurrence_type == 'weekly':
            weekday = int(self.recurrence_weekday or '0')
            current = date_from
            # advance to the first matching weekday
            current += relativedelta(days=(weekday - current.weekday()) % 7)
            while current <= date_to:
                occurrences.append(current)
                current += relativedelta(weeks=1)
        else:
            step = {'monthly': 1, 'quarterly': 3, 'yearly': 12}[self.recurrence_type]
            # Anchor on the start month so quarterly stays aligned to date_start.
            anchor = self.date_start.replace(day=1)
            if self.recurrence_type == 'yearly':
                anchor = anchor.replace(month=self.recurrence_month)
            current = anchor
            # rewind/advance the anchor close to date_from
            while current < date_from.replace(day=1):
                current += relativedelta(months=step)
            while True:
                occ = self._clamp_day(current.year, current.month, self.recurrence_day)
                if occ > date_to:
                    break
                if occ >= date_from:
                    occurrences.append(occ)
                current += relativedelta(months=step)

        return sorted(occurrences)

    def _entry_name(self, occurrence_date):
        """Build the cashflow.entry name for an occurrence."""
        self.ensure_one()
        if self.description_template:
            return self.description_template.format(
                date=occurrence_date,
                amount=self.amount,
                partner=self.partner_id.display_name or '',
            )
        return self.name

    def _prepare_entry_vals(self, occurrence_date):
        self.ensure_one()
        return {
            'name': self._entry_name(occurrence_date),
            'date': occurrence_date,
            'entry_type': 'forecast',
            'state': 'draft',
            'journal_id': self.journal_id.id,
            'category_id': self.category_id.id or False,
            'currency_id': self.currency_id.id,
            'model': self._name,
            'res_id': self.id,
            'recurring_id': self.id,
        }

    def _prepare_item_vals(self, occurrence_date):
        self.ensure_one()
        return {
            'date': occurrence_date,
            'amount': abs(self.amount),
            'type': self.flow_type,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id or False,
            'description': self._entry_name(occurrence_date),
        }

    def _generate_entries(self):
        """Create/update forecast entries over the horizon. Idempotent.

        Matches existing entries by (recurring_id, date) so re-runs never
        duplicate. Forecast entries that fall outside the current occurrence
        set are removed; entries promoted to 'actual' are left untouched.
        """
        CashflowEntry = self.env['cashflow.entry']
        CashflowItem = self.env['cashflow.item']
        today = fields.Date.context_today(self)

        for rec in self:
            if not rec.active:
                continue
            date_to = today + relativedelta(months=rec.horizon_months)
            occurrences = rec._compute_next_occurrences(today, date_to)
            occurrence_set = set(occurrences)

            existing = CashflowEntry.search([
                ('recurring_id', '=', rec.id),
            ])
            existing_by_date = {entry.date: entry for entry in existing}

            for occ in occurrences:
                entry = existing_by_date.get(occ)
                if entry:
                    if entry.entry_type == 'actual':
                        # Realised occurrence: do not overwrite.
                        continue
                    entry.write(rec._prepare_entry_vals(occ))
                    entry.item_ids.unlink()
                else:
                    entry = CashflowEntry.create(rec._prepare_entry_vals(occ))
                item_vals = rec._prepare_item_vals(occ)
                item_vals['entry_id'] = entry.id
                CashflowItem.create(item_vals)

            # Drop stale forecast entries no longer matching the schedule.
            stale = existing.filtered(
                lambda e: e.date not in occurrence_set and e.entry_type != 'actual'
            )
            stale.unlink()
        return True

    def action_generate_entries(self):
        """Manual on-demand (re)generation."""
        self._generate_entries()
        return True

    def _remove_future_entries(self):
        """Remove not-yet-realised forecast entries (deactivation/unlink policy).

        Forecast entries are deleted; entries promoted to 'actual' are kept as
        historical record.
        """
        entries = self.env['cashflow.entry'].search([
            ('recurring_id', 'in', self.ids),
            ('entry_type', '=', 'forecast'),
        ])
        entries.unlink()

    def write(self, vals):
        res = super().write(vals)
        if 'active' in vals and not vals['active']:
            self._remove_future_entries()
        return res

    def unlink(self):
        self._remove_future_entries()
        return super().unlink()

    def action_view_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generated Entries'),
            'res_model': 'cashflow.entry',
            'view_mode': 'list,form',
            'domain': [('recurring_id', '=', self.id)],
        }

    @api.model
    def _cron_generate_recurring_entries(self):
        """Daily cron: regenerate forecast entries for all active recurrences."""
        recurrences = self.search([('active', '=', True)])
        recurrences._generate_entries()
        return True
