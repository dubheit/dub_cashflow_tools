from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTreasuryAvailability(TransactionCase):
    """Projected availability at date (R4)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.CreditLine = cls.env['treasury.credit.line']
        cls.bank_journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        cls.treasury_account = cls.env['treasury.account'].create({
            'name': 'Bank A',
            'code': 'AVAIL-A',
            'account_type': 'bank',
            'journal_id': cls.bank_journal.id,
        })

    def _make_item(self, day, amount, flow_type):
        """Create a standalone cashflow entry+item on the bank journal."""
        entry = self.env['cashflow.entry'].create({
            'name': 'Proj %s' % day,
            'date': day,
            'state': 'confirmed',
            'entry_type': 'forecast',
            'journal_id': self.bank_journal.id,
        })
        self.env['cashflow.item'].create({
            'entry_id': entry.id,
            'date': day,
            'amount': amount,
            'type': flow_type,
            'currency_id': self.company.currency_id.id,
        })
        return entry

    def test_01_overdraft_projection(self):
        """Overdraft usage follows the projected (negative) bank balance."""
        line = self.CreditLine.create({
            'name': 'Overdraft A',
            'account_id': self.treasury_account.id,
            'credit_type': 'overdraft',
            'limit_amount': 50000.0,
        })
        # Big outflow on Feb 10 → balance goes negative from that date.
        self._make_item(date(2026, 2, 10), 20000.0, 'out')
        self._make_item(date(2026, 2, 20), 5000.0, 'in')

        used_jan, avail_jan = line.get_available_at_date(date(2026, 1, 31))
        self.assertEqual(used_jan, 0.0, "No flow yet → no usage")
        self.assertEqual(avail_jan, 50000.0)

        used_feb15, avail_feb15 = line.get_available_at_date(date(2026, 2, 15))
        self.assertEqual(used_feb15, 20000.0, "Outflow drawn the overdraft")
        self.assertEqual(avail_feb15, 30000.0)

        used_feb25, _ = line.get_available_at_date(date(2026, 2, 25))
        self.assertEqual(used_feb25, 15000.0, "Inflow reduced the usage")

    def test_02_snapshot_not_broken(self):
        """The snapshot available_amount keeps its 'today' meaning."""
        line = self.CreditLine.create({
            'name': 'Overdraft B',
            'account_id': self.treasury_account.id,
            'credit_type': 'overdraft',
            'limit_amount': 10000.0,
            'manual_used_amount': 4000.0,
            'auto_compute_usage': False,
        })
        self.assertEqual(line.available_amount, 6000.0)

    def test_03_batch_matches_single(self):
        """get_available_at_dates matches per-date get_available_at_date."""
        line = self.CreditLine.create({
            'name': 'Overdraft C',
            'account_id': self.treasury_account.id,
            'credit_type': 'overdraft',
            'limit_amount': 50000.0,
        })
        self._make_item(date(2026, 3, 5), 12000.0, 'out')
        dates = [date(2026, 3, 1), date(2026, 3, 10), date(2026, 3, 20)]
        batch = line.get_available_at_dates(dates)
        for d in dates:
            self.assertEqual(batch[d], line.get_available_at_date(d))

    def test_04_wizard_builds_report(self):
        """The wizard materialises one report row per (line, date)."""
        line = self.CreditLine.create({
            'name': 'Overdraft D',
            'account_id': self.treasury_account.id,
            'credit_type': 'overdraft',
            'limit_amount': 50000.0,
            'state': 'active',
        })
        wizard = self.env['treasury.availability.wizard'].create({
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 5),
            'granularity': 'day',
            'credit_line_ids': [(6, 0, line.ids)],
        })
        action = wizard.action_compute()
        self.assertEqual(action['res_model'], 'treasury.availability.report')
        self.assertEqual(len(wizard.line_ids), 5, "5 days → 5 rows")
        self.assertTrue(all(r.limit_amount == 50000.0 for r in wizard.line_ids))
