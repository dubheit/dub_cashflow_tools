from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestTreasuryCreditLine(TransactionCase):
    """Test cases for Treasury Credit Line model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.TreasuryAccount = cls.env['treasury.account']
        cls.CreditLine = cls.env['treasury.credit.line']
        cls.company = cls.env.company

        # Create a treasury account for credit lines
        cls.treasury_account = cls.TreasuryAccount.create({
            'name': 'Test Bank for Credit Lines',
            'code': 'TCL',
            'account_type': 'bank',
        })

    def test_create_overdraft(self):
        """Test creating an overdraft credit line."""
        credit_line = self.CreditLine.create({
            'name': 'Test Overdraft',
            'account_id': self.treasury_account.id,
            'credit_type': 'overdraft',
            'limit_amount': 50000.00,
            'interest_rate': 8.50,
        })

        self.assertEqual(credit_line.name, 'Test Overdraft')
        self.assertEqual(credit_line.credit_type, 'overdraft')
        self.assertEqual(credit_line.limit_amount, 50000.00)
        self.assertEqual(credit_line.state, 'draft')
        self.assertEqual(credit_line.available_amount, 50000.00)
        self.assertEqual(credit_line.utilization_rate, 0.0)

    def test_create_advance_facility(self):
        """Test creating an invoice advance facility."""
        credit_line = self.CreditLine.create({
            'name': 'Test Advance',
            'account_id': self.treasury_account.id,
            'credit_type': 'advance',
            'limit_amount': 100000.00,
            'interest_rate': 6.50,
            'spread': 1.50,
        })

        self.assertEqual(credit_line.credit_type, 'advance')
        self.assertEqual(credit_line.spread, 1.50)

    def test_activate_credit_line(self):
        """Test activating a credit line."""
        credit_line = self.CreditLine.create({
            'name': 'Test Activation',
            'account_id': self.treasury_account.id,
            'credit_type': 'overdraft',
            'limit_amount': 30000.00,
        })

        self.assertEqual(credit_line.state, 'draft')
        credit_line.action_activate()
        self.assertEqual(credit_line.state, 'active')

    def test_close_credit_line(self):
        """Test closing a credit line with zero usage."""
        credit_line = self.CreditLine.create({
            'name': 'Test Close',
            'account_id': self.treasury_account.id,
            'credit_type': 'overdraft',
            'limit_amount': 30000.00,
            'state': 'active',
        })

        credit_line.action_close()
        self.assertEqual(credit_line.state, 'closed')

    def test_cannot_close_with_usage(self):
        """Test that credit line with usage cannot be closed."""
        credit_line = self.CreditLine.create({
            'name': 'Test Cannot Close',
            'account_id': self.treasury_account.id,
            'credit_type': 'advance',
            'limit_amount': 30000.00,
            'manual_used_amount': 10000.00,
            'auto_compute_usage': False,
            'state': 'active',
        })

        with self.assertRaises(ValidationError):
            credit_line.action_close()

    def test_utilization_calculation(self):
        """Test utilization rate calculation."""
        credit_line = self.CreditLine.create({
            'name': 'Test Utilization',
            'account_id': self.treasury_account.id,
            'credit_type': 'advance',
            'limit_amount': 100000.00,
            'manual_used_amount': 25000.00,
            'auto_compute_usage': False,
        })

        self.assertEqual(credit_line.used_amount, 25000.00)
        self.assertEqual(credit_line.available_amount, 75000.00)
        self.assertEqual(credit_line.utilization_rate, 25.0)

    def test_usage_cannot_exceed_limit(self):
        """Test that used amount cannot exceed limit."""
        with self.assertRaises(ValidationError):
            self.CreditLine.create({
                'name': 'Test Exceed Limit',
                'account_id': self.treasury_account.id,
                'credit_type': 'advance',
                'limit_amount': 50000.00,
                'manual_used_amount': 60000.00,
                'auto_compute_usage': False,
            })

    def test_date_validation(self):
        """Test that start date must be before expiry date."""
        with self.assertRaises(ValidationError):
            self.CreditLine.create({
                'name': 'Test Date Validation',
                'account_id': self.treasury_account.id,
                'credit_type': 'overdraft',
                'limit_amount': 50000.00,
                'start_date': '2024-12-31',
                'expiry_date': '2024-01-01',
            })

    def test_expire_credit_line(self):
        """Test marking credit line as expired."""
        credit_line = self.CreditLine.create({
            'name': 'Test Expire',
            'account_id': self.treasury_account.id,
            'credit_type': 'overdraft',
            'limit_amount': 30000.00,
            'state': 'active',
        })

        credit_line.action_expire()
        self.assertEqual(credit_line.state, 'expired')

    def test_covenant_compliance(self):
        """Test covenant compliance calculation."""
        credit_line = self.CreditLine.create({
            'name': 'Test Covenant',
            'account_id': self.treasury_account.id,
            'credit_type': 'advance',
            'limit_amount': 100000.00,
        })

        covenant = self.env['treasury.covenant'].create({
            'name': 'Debt/Equity',
            'credit_line_id': credit_line.id,
            'covenant_type': 'debt_equity',
            'comparison': '<=',
            'threshold_value': 2.0,
            'current_value': 1.5,
        })

        self.assertTrue(covenant.is_compliant)

        covenant.current_value = 2.5
        self.assertFalse(covenant.is_compliant)

    def test_rate_label(self):
        """rate_label combines the reference rate and the spread."""
        credit_line = self.CreditLine.create({
            'name': 'Test Rate Label',
            'account_id': self.treasury_account.id,
            'credit_type': 'sbf',
            'limit_amount': 450000.00,
            'reference_rate': 'euribor_3m',
            'spread': 0.35,
        })
        self.assertEqual(credit_line.rate_label, 'Euribor 3M + 0.35%')

        credit_line.reference_rate = False
        credit_line.interest_rate = 2.4
        self.assertEqual(credit_line.rate_label, '2.4%')

    def test_manual_vs_auto_usage(self):
        """Test switching between manual and auto usage computation."""
        credit_line = self.CreditLine.create({
            'name': 'Test Manual Auto',
            'account_id': self.treasury_account.id,
            'credit_type': 'advance',
            'limit_amount': 100000.00,
            'manual_used_amount': 30000.00,
            'auto_compute_usage': False,
        })

        self.assertEqual(credit_line.used_amount, 30000.00)

        # With auto_compute enabled, an advance facility recomputes the usage
        # from its linked invoices. With none linked, the usage is 0.
        credit_line.auto_compute_usage = True
        self.assertEqual(credit_line.used_amount, 0.0)
