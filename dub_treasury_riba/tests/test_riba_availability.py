from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRibaAvailability(TransactionCase):
    """Projected availability is wired to the Ri.Ba. portfolio (R4 + RiBa)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CreditLine = cls.env["treasury.credit.line"]
        cls.account = cls.env["treasury.account"].create({
            "name": "SBF Bank",
            "code": "SBF-A",
            "account_type": "bank",
        })
        cls.line = cls.CreditLine.create({
            "name": "SBF line",
            "account_id": cls.account.id,
            "credit_type": "sbf",
            "limit_amount": 500000.0,
        })

    def test_01_projection_hook_present(self):
        """The RiBa override is in the MRO for projected usage."""
        self.assertTrue(
            hasattr(self.line, "_projected_riba_usage_at_date"),
            "RiBa projection helper should be available on the credit line",
        )

    def test_02_no_effects_full_availability(self):
        """With no presented effects, the SBF line is fully available at date."""
        used, available = self.line.get_available_at_date(date(2026, 7, 15))
        self.assertEqual(used, 0.0)
        self.assertEqual(available, 500000.0)

    def test_03_riba_usage_zero_without_config(self):
        """The projected portfolio is 0 when no riba.configuration points here."""
        self.assertEqual(
            self.line._projected_riba_usage_at_date(date(2026, 7, 15)), 0.0
        )
