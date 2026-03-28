from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta


@tagged('post_install', '-at_install')
class TestTreasuryFinancialInstrument(TransactionCase):
    """Test cases for Treasury Financial Instrument model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Instrument = cls.env['treasury.financial.instrument']
        cls.Installment = cls.env['treasury.installment']
        cls.company = cls.env.company

        # Create a partner for instruments
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Bank Partner',
            'company_type': 'company',
        })

    def test_create_loan(self):
        """Test creating a bank loan instrument."""
        instrument = self.Instrument.create({
            'name': 'Test Loan',
            'instrument_type': 'loan',
            'flow_direction': 'inbound',
            'partner_id': self.partner.id,
            'principal_amount': 100000.00,
            'interest_rate': 4.50,
            'rate_type': 'fixed',
            'amortization_type': 'french',
            'installment_frequency': 'monthly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=5),
            'first_installment_date': date.today() + relativedelta(months=1),
        })

        self.assertEqual(instrument.name, 'Test Loan')
        self.assertEqual(instrument.instrument_type, 'loan')
        self.assertEqual(instrument.flow_direction, 'inbound')
        self.assertEqual(instrument.principal_amount, 100000.00)
        self.assertEqual(instrument.state, 'draft')

    def test_create_mortgage(self):
        """Test creating a mortgage instrument."""
        instrument = self.Instrument.create({
            'name': 'Test Mortgage',
            'instrument_type': 'mortgage',
            'flow_direction': 'inbound',
            'partner_id': self.partner.id,
            'principal_amount': 500000.00,
            'interest_rate': 3.20,
            'rate_type': 'variable',
            'reference_rate': 'euribor_3m',
            'spread': 1.50,
            'amortization_type': 'french',
            'installment_frequency': 'monthly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=15),
            'first_installment_date': date.today() + relativedelta(months=1),
            'guarantee_type': 'mortgage',
        })

        self.assertEqual(instrument.instrument_type, 'mortgage')
        self.assertEqual(instrument.rate_type, 'variable')
        self.assertEqual(instrument.guarantee_type, 'mortgage')

    def test_create_leasing(self):
        """Test creating a leasing instrument."""
        instrument = self.Instrument.create({
            'name': 'Test Leasing',
            'instrument_type': 'leasing',
            'flow_direction': 'inbound',
            'partner_id': self.partner.id,
            'principal_amount': 80000.00,
            'interest_rate': 5.80,
            'rate_type': 'fixed',
            'amortization_type': 'french',
            'installment_frequency': 'monthly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=5),
            'first_installment_date': date.today() + relativedelta(months=1),
        })

        self.assertEqual(instrument.instrument_type, 'leasing')

    def test_create_partner_loan_outbound(self):
        """Test creating an outbound partner loan (given to partner)."""
        instrument = self.Instrument.create({
            'name': 'Test Partner Loan Out',
            'instrument_type': 'partner_loan',
            'flow_direction': 'outbound',
            'partner_id': self.partner.id,
            'principal_amount': 30000.00,
            'interest_rate': 3.00,
            'rate_type': 'fixed',
            'amortization_type': 'bullet',
            'installment_frequency': 'quarterly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=2),
            'first_installment_date': date.today() + relativedelta(months=3),
        })

        self.assertEqual(instrument.flow_direction, 'outbound')
        self.assertEqual(instrument.amortization_type, 'bullet')

    def test_activate_instrument(self):
        """Test activating a financial instrument."""
        instrument = self.Instrument.create({
            'name': 'Test Activation',
            'instrument_type': 'loan',
            'flow_direction': 'inbound',
            'principal_amount': 50000.00,
            'interest_rate': 4.00,
            'rate_type': 'fixed',
            'amortization_type': 'french',
            'installment_frequency': 'monthly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=3),
            'first_installment_date': date.today() + relativedelta(months=1),
        })

        self.assertEqual(instrument.state, 'draft')
        instrument.action_activate()
        self.assertEqual(instrument.state, 'active')

    def test_generate_french_amortization(self):
        """Test French amortization schedule generation."""
        instrument = self.Instrument.create({
            'name': 'Test French Amortization',
            'instrument_type': 'loan',
            'flow_direction': 'inbound',
            'principal_amount': 12000.00,
            'interest_rate': 12.00,  # 1% per month for easy calculation
            'rate_type': 'fixed',
            'amortization_type': 'french',
            'installment_frequency': 'monthly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=1),
            'first_installment_date': date.today() + relativedelta(months=1),
        })

        instrument.action_generate_installments()

        self.assertEqual(len(instrument.installment_ids), 12)
        self.assertTrue(all(i.state == 'draft' for i in instrument.installment_ids))

        # French amortization: constant total payment
        payments = instrument.installment_ids.mapped('total_amount')
        # Allow small rounding differences
        self.assertTrue(max(payments) - min(payments) < 1)

    def test_generate_italian_amortization(self):
        """Test Italian amortization schedule generation."""
        instrument = self.Instrument.create({
            'name': 'Test Italian Amortization',
            'instrument_type': 'loan',
            'flow_direction': 'inbound',
            'principal_amount': 12000.00,
            'interest_rate': 12.00,
            'rate_type': 'fixed',
            'amortization_type': 'italian',
            'installment_frequency': 'monthly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=1),
            'first_installment_date': date.today() + relativedelta(months=1),
        })

        instrument.action_generate_installments()

        self.assertEqual(len(instrument.installment_ids), 12)

        # Italian amortization: constant principal
        principals = instrument.installment_ids.mapped('principal_amount')
        # Each principal payment should be 1000 (12000/12)
        self.assertTrue(all(abs(p - 1000) < 1 for p in principals))

    def test_generate_bullet_amortization(self):
        """Test bullet amortization (interest only, principal at end)."""
        instrument = self.Instrument.create({
            'name': 'Test Bullet',
            'instrument_type': 'loan',
            'flow_direction': 'inbound',
            'principal_amount': 100000.00,
            'interest_rate': 4.00,
            'rate_type': 'fixed',
            'amortization_type': 'bullet',
            'installment_frequency': 'quarterly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=2),
            'first_installment_date': date.today() + relativedelta(months=3),
        })

        instrument.action_generate_installments()

        self.assertEqual(len(instrument.installment_ids), 8)  # 2 years * 4 quarters

        # All but last installment should have zero principal
        all_but_last = instrument.installment_ids.sorted('due_date')[:-1]
        last = instrument.installment_ids.sorted('due_date')[-1]

        self.assertTrue(all(i.principal_amount == 0 for i in all_but_last))
        self.assertEqual(last.principal_amount, 100000.00)

    def test_quarterly_frequency(self):
        """Test quarterly payment frequency."""
        instrument = self.Instrument.create({
            'name': 'Test Quarterly',
            'instrument_type': 'loan',
            'flow_direction': 'inbound',
            'principal_amount': 40000.00,
            'interest_rate': 4.00,
            'rate_type': 'fixed',
            'amortization_type': 'french',
            'installment_frequency': 'quarterly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=2),
            'first_installment_date': date.today() + relativedelta(months=3),
        })

        instrument.action_generate_installments()

        self.assertEqual(len(instrument.installment_ids), 8)  # 2 years * 4 quarters

    def test_semiannual_frequency(self):
        """Test semi-annual payment frequency."""
        instrument = self.Instrument.create({
            'name': 'Test Semi-Annual',
            'instrument_type': 'loan',
            'flow_direction': 'inbound',
            'principal_amount': 60000.00,
            'interest_rate': 4.00,
            'rate_type': 'fixed',
            'amortization_type': 'french',
            'installment_frequency': 'semi_annual',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=3),
            'first_installment_date': date.today() + relativedelta(months=6),
        })

        instrument.action_generate_installments()

        self.assertEqual(len(instrument.installment_ids), 6)  # 3 years * 2 semesters

    def test_residual_calculation(self):
        """Test residual amount calculation after payments."""
        instrument = self.Instrument.create({
            'name': 'Test Residual',
            'instrument_type': 'loan',
            'flow_direction': 'inbound',
            'principal_amount': 12000.00,
            'interest_rate': 12.00,
            'rate_type': 'fixed',
            'amortization_type': 'italian',
            'installment_frequency': 'monthly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=1),
            'first_installment_date': date.today() + relativedelta(months=1),
        })

        instrument.action_generate_installments()

        installments = instrument.installment_ids.sorted('due_date')

        # First installment residual should be 12000 - 1000 = 11000
        self.assertAlmostEqual(installments[0].residual_amount, 11000.00, places=2)

        # Last installment residual should be 0
        self.assertAlmostEqual(installments[-1].residual_amount, 0.00, places=2)

    def test_date_validation(self):
        """Test that start date must be before end date."""
        with self.assertRaises(ValidationError):
            self.Instrument.create({
                'name': 'Test Date Validation',
                'instrument_type': 'loan',
                'flow_direction': 'inbound',
                'principal_amount': 50000.00,
                'interest_rate': 4.00,
                'rate_type': 'fixed',
                'amortization_type': 'french',
                'installment_frequency': 'monthly',
                'start_date': '2024-12-31',
                'end_date': '2024-01-01',
                'first_installment_date': '2024-02-01',
            })

    def test_close_instrument(self):
        """Test closing a paid instrument."""
        instrument = self.Instrument.create({
            'name': 'Test Close',
            'instrument_type': 'loan',
            'flow_direction': 'inbound',
            'principal_amount': 10000.00,
            'interest_rate': 4.00,
            'rate_type': 'fixed',
            'amortization_type': 'french',
            'installment_frequency': 'monthly',
            'start_date': date.today() - relativedelta(years=1),
            'end_date': date.today(),
            'first_installment_date': date.today() - relativedelta(months=11),
            'state': 'active',
        })

        instrument.action_generate_installments()

        # Mark all installments as paid
        for installment in instrument.installment_ids:
            installment.write({
                'state': 'paid',
                'payment_date': installment.due_date,
            })

        instrument.action_close()
        self.assertEqual(instrument.state, 'closed')

    def test_installment_workflow(self):
        """Test installment state transitions."""
        instrument = self.Instrument.create({
            'name': 'Test Installment Workflow',
            'instrument_type': 'loan',
            'flow_direction': 'inbound',
            'principal_amount': 3000.00,
            'interest_rate': 12.00,
            'rate_type': 'fixed',
            'amortization_type': 'french',
            'installment_frequency': 'monthly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(months=3),
            'first_installment_date': date.today() + relativedelta(months=1),
        })

        instrument.action_generate_installments()

        installment = instrument.installment_ids[0]
        self.assertEqual(installment.state, 'draft')

        # Mark as paid
        installment.action_mark_paid()
        self.assertEqual(installment.state, 'paid')
        self.assertEqual(installment.payment_date, date.today())


@tagged('post_install', '-at_install')
class TestTreasuryInvoiceLink(TransactionCase):
    """Test cases for linking invoices to treasury instruments."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Instrument = cls.env['treasury.financial.instrument']
        cls.CreditLine = cls.env['treasury.credit.line']
        cls.TreasuryAccount = cls.env['treasury.account']
        cls.AccountMove = cls.env['account.move']
        cls.company = cls.env.company

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Vendor',
            'company_type': 'company',
        })

        cls.treasury_account = cls.TreasuryAccount.create({
            'name': 'Test Bank',
            'code': 'TBANK01',
            'account_type': 'bank',
        })

    def test_link_invoice_to_instrument(self):
        """Test linking a vendor invoice to a financial instrument."""
        instrument = self.Instrument.create({
            'name': 'Test Loan for Invoice',
            'instrument_type': 'loan',
            'flow_direction': 'inbound',
            'principal_amount': 50000.00,
            'interest_rate': 4.00,
            'rate_type': 'fixed',
            'amortization_type': 'french',
            'installment_frequency': 'monthly',
            'start_date': date.today(),
            'end_date': date.today() + relativedelta(years=2),
            'first_installment_date': date.today() + relativedelta(months=1),
        })

        invoice = self.AccountMove.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': date.today(),
            'treasury_instrument_ids': [(4, instrument.id)],
        })

        self.assertIn(instrument, invoice.treasury_instrument_ids)
        self.assertIn(invoice, instrument.vendor_bill_ids)

    def test_link_invoice_to_credit_line(self):
        """Test linking a vendor invoice to a credit line."""
        credit_line = self.CreditLine.create({
            'name': 'Test Credit Line for Invoice',
            'account_id': self.treasury_account.id,
            'credit_type': 'advance',
            'limit_amount': 100000.00,
        })

        invoice = self.AccountMove.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': date.today(),
            'credit_line_ids': [(4, credit_line.id)],
        })

        self.assertIn(credit_line, invoice.credit_line_ids)
        self.assertIn(invoice, credit_line.linked_invoice_ids)

    def test_linked_invoice_count(self):
        """Test linked invoice count calculation."""
        credit_line = self.CreditLine.create({
            'name': 'Test Invoice Count',
            'account_id': self.treasury_account.id,
            'credit_type': 'overdraft',
            'limit_amount': 50000.00,
        })

        self.assertEqual(credit_line.linked_invoice_count, 0)

        invoice1 = self.AccountMove.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': date.today(),
            'credit_line_ids': [(4, credit_line.id)],
        })

        self.assertEqual(credit_line.linked_invoice_count, 1)

        invoice2 = self.AccountMove.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': date.today(),
            'credit_line_ids': [(4, credit_line.id)],
        })

        self.assertEqual(credit_line.linked_invoice_count, 2)

    def test_link_customer_invoice_to_credit_line(self):
        """Test linking a customer invoice to a credit line (advance/SBF/factoring)."""
        credit_line = self.CreditLine.create({
            'name': 'Test Advance Credit Line',
            'account_id': self.treasury_account.id,
            'credit_type': 'advance',
            'limit_amount': 200000.00,
        })

        customer_invoice = self.AccountMove.create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': date.today(),
            'credit_line_ids': [(4, credit_line.id)],
        })

        self.assertIn(credit_line, customer_invoice.credit_line_ids)
        self.assertIn(customer_invoice, credit_line.linked_invoice_ids)
        self.assertEqual(credit_line.linked_invoice_count, 1)
