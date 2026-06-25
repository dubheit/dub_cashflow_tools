from datetime import date

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestTreasuryRateTier(TransactionCase):
    """Tiered interest rates (R6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CreditLine = cls.env['treasury.credit.line']
        cls.treasury_account = cls.env['treasury.account'].create({
            'name': 'Bank Tier',
            'code': 'TIER-A',
            'account_type': 'bank',
        })
        cls.line = cls.CreditLine.create({
            'name': 'Tiered Overdraft',
            'account_id': cls.treasury_account.id,
            'credit_type': 'overdraft',
            'limit_amount': 200000.0,
            'interest_rate': 0.60,
        })

    def test_01_no_tier_returns_flat_rate(self):
        """Without tiers the flat interest rate is returned (backward compat)."""
        self.assertEqual(self.line.get_applicable_rate(50000.0), 0.60)

    def test_02_tier_selection_by_threshold(self):
        """The tier matching the utilization threshold is applied."""
        self.env['treasury.credit.line.rate.tier'].create([
            {
                'credit_line_id': self.line.id,
                'min_amount': 0.0,
                'max_amount': 100000.0,
                'interest_rate': 0.60,
            },
            {
                'credit_line_id': self.line.id,
                'min_amount': 100000.01,
                'max_amount': 0.0,
                'interest_rate': 0.50,
            },
        ])
        self.assertEqual(self.line.get_applicable_rate(50000.0), 0.60)
        self.assertEqual(self.line.get_applicable_rate(150000.0), 0.50)

    def test_03_tier_validity_dates(self):
        """Date-bounded tiers only apply within their validity window."""
        self.env['treasury.credit.line.rate.tier'].create({
            'credit_line_id': self.line.id,
            'min_amount': 0.0,
            'max_amount': 0.0,
            'interest_rate': 0.40,
            'valid_from': date(2026, 1, 1),
            'valid_to': date(2026, 6, 30),
        })
        self.assertEqual(self.line.get_applicable_rate(10000.0, date(2026, 3, 1)), 0.40)
        # Outside the window → fall back to the flat rate.
        self.assertEqual(self.line.get_applicable_rate(10000.0, date(2026, 9, 1)), 0.60)

    def test_04_invalid_amounts_rejected(self):
        """max_amount below min_amount is rejected."""
        with self.assertRaises(ValidationError):
            self.env['treasury.credit.line.rate.tier'].create({
                'credit_line_id': self.line.id,
                'min_amount': 100000.0,
                'max_amount': 50000.0,
                'interest_rate': 0.50,
            })
