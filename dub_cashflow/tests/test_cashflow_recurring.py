from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
from odoo import fields


@tagged('post_install', '-at_install')
class TestCashflowRecurring(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Recurring = cls.env['cashflow.recurring']
        cls.bank_journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.env.company.id),
        ], limit=1)

    def _make_recurring(self, **kwargs):
        vals = {
            'name': 'Test Recurring',
            'journal_id': self.bank_journal.id,
            'flow_type': 'out',
            'amount': 1000.0,
            'recurrence_type': 'monthly',
            'recurrence_day': 28,
            'date_start': fields.Date.context_today(self.Recurring),
            'horizon_months': 12,
        }
        vals.update(kwargs)
        return self.Recurring.create(vals)

    def test_01_monthly_horizon_generates_entries(self):
        """Monthly day 28, horizon 12 → 12 forecast entries over the next year."""
        rec = self._make_recurring()
        rec.action_generate_entries()
        entries = rec.entry_ids
        self.assertEqual(len(entries), 12, "Should generate 12 monthly entries")
        self.assertTrue(all(e.entry_type == 'forecast' for e in entries))
        self.assertTrue(all(e.date.day == 28 for e in entries))
        self.assertTrue(all(len(e.item_ids) == 1 for e in entries))
        self.assertTrue(all(e.item_ids.type == 'out' for e in entries))

    def test_02_idempotent_regeneration(self):
        """Changing the amount and regenerating updates entries without duplicates."""
        rec = self._make_recurring()
        rec.action_generate_entries()
        count_before = len(rec.entry_ids)
        rec.amount = 2000.0
        rec.action_generate_entries()
        self.assertEqual(len(rec.entry_ids), count_before, "No duplicate entries")
        self.assertTrue(all(e.item_ids.amount == 2000.0 for e in rec.entry_ids))

    def test_03_deactivation_removes_future_entries(self):
        """Deactivating a recurring removes its forecast entries."""
        rec = self._make_recurring()
        rec.action_generate_entries()
        self.assertTrue(rec.entry_ids)
        rec.active = False
        self.assertFalse(rec.entry_ids, "Forecast entries removed on deactivation")

    def test_04_multi_scenario(self):
        """Entries inherit all scenarios linked to the recurring."""
        scenario = self.env['cashflow.scenario'].create({'name': 'Pessimistic'})
        base = self.env.ref('dub_cashflow.cashflow_scenario_base')
        rec = self._make_recurring()
        rec.scenario_ids = [(6, 0, (base | scenario).ids)]
        rec.action_generate_entries()
        entry = rec.entry_ids[0]
        self.assertIn(scenario, entry.scenario_ids)
        self.assertIn(base, entry.scenario_ids)

    def test_05_date_end_before_start_raises(self):
        """date_end before date_start is rejected."""
        with self.assertRaises(ValidationError):
            self._make_recurring(
                date_start=date(2026, 6, 1),
                date_end=date(2026, 5, 1),
            )

    def test_06_compute_occurrences_weekly(self):
        """Weekly occurrences land on the configured weekday."""
        rec = self._make_recurring(
            recurrence_type='weekly',
            recurrence_weekday='2',  # Wednesday
            date_start=date(2026, 1, 1),
        )
        occ = rec._compute_next_occurrences(date(2026, 1, 1), date(2026, 1, 31))
        self.assertTrue(occ)
        self.assertTrue(all(d.weekday() == 2 for d in occ))

    def test_07_compute_occurrences_respects_date_end(self):
        """Occurrences never exceed date_end."""
        rec = self._make_recurring(
            date_start=date(2026, 1, 28),
            date_end=date(2026, 3, 31),
        )
        occ = rec._compute_next_occurrences(date(2026, 1, 1), date(2027, 1, 1))
        self.assertTrue(occ)
        self.assertTrue(all(d <= date(2026, 3, 31) for d in occ))

    def test_08_day_clamped_to_short_month(self):
        """Day 31 is clamped to the last day of February."""
        rec = self._make_recurring(
            recurrence_day=31,
            date_start=date(2026, 1, 1),
        )
        occ = rec._compute_next_occurrences(date(2026, 2, 1), date(2026, 2, 28))
        self.assertEqual(occ, [date(2026, 2, 28)])
