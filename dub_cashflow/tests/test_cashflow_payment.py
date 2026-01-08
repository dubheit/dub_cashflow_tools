from odoo.tests.common import TransactionCase, tagged
from odoo import fields


@tagged('post_install', '-at_install')
class TestCashflowPayment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Get or create required records
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner Cashflow',
        })

        # Get a receivable account
        cls.account_receivable = cls.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)

        # Get an income account
        cls.account_income = cls.env['account.account'].search([
            ('account_type', '=', 'income'),
        ], limit=1)

        # Get a bank journal
        cls.bank_journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.env.company.id),
        ], limit=1)

        # Get the cashflow configs
        cls.invoice_config = cls.env['cashflow.config'].search([
            ('model_name', '=', 'account.move.line'),
        ], limit=1)
        cls.payment_config = cls.env['cashflow.config'].search([
            ('model_name', '=', 'account.payment'),
        ], limit=1)

    def _create_invoice(self, amount=100.0):
        """Helper to create and post an invoice."""
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Test Product',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.account_income.id,
            })],
        })
        invoice.action_post()
        return invoice

    def _get_invoice_cashflow_entry(self, invoice):
        """Get cashflow entry for invoice's receivable line."""
        receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )
        return self.env['cashflow.entry'].search([
            ('model', '=', 'account.move.line'),
            ('res_id', 'in', receivable_line.ids),
        ])

    def _get_payment_cashflow_entry(self, payment):
        """Get cashflow entry for payment."""
        return self.env['cashflow.entry'].search([
            ('model', '=', 'account.payment'),
            ('res_id', '=', payment.id),
        ])

    def _register_payment(self, invoice):
        """Register a payment for the invoice."""
        payment_register = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'journal_id': self.bank_journal.id,
        })
        action = payment_register.action_create_payments()

        # Get the created payment
        if action and action.get('res_id'):
            return self.env['account.payment'].browse(action['res_id'])
        # If action returns a domain, search for the payment
        return self.env['account.payment'].search([
            ('partner_id', '=', self.partner.id),
        ], order='id desc', limit=1)

    def test_01_invoice_creates_cashflow(self):
        """Test that posting an invoice creates a cashflow entry."""
        invoice = self._create_invoice(100.0)

        # Check cashflow entry was created
        cashflow_entry = self._get_invoice_cashflow_entry(invoice)
        self.assertTrue(cashflow_entry, "Cashflow entry should be created for posted invoice")
        self.assertEqual(cashflow_entry.state, 'confirmed', "Invoice cashflow should be confirmed")
        self.assertEqual(cashflow_entry.entry_type, 'forecast', "Invoice cashflow should be forecast")

        # Check cashflow item
        self.assertEqual(len(cashflow_entry.item_ids), 1, "Should have one cashflow item")
        self.assertEqual(cashflow_entry.item_ids.amount, 100.0, "Amount should match invoice")
        self.assertEqual(cashflow_entry.item_ids.type, 'in', "Type should be 'in' for customer invoice")

    def test_02_payment_deletes_invoice_cashflow(self):
        """Test that registering a payment deletes the invoice cashflow entry."""
        # Create and post invoice
        invoice = self._create_invoice(200.0)

        # Verify invoice cashflow exists
        invoice_cashflow = self._get_invoice_cashflow_entry(invoice)
        self.assertTrue(invoice_cashflow, "Invoice cashflow should exist before payment")

        # Register payment
        payment = self._register_payment(invoice)
        self.assertTrue(payment, "Payment should be created")

        # Check invoice cashflow was deleted
        invoice_cashflow = self._get_invoice_cashflow_entry(invoice)
        self.assertFalse(invoice_cashflow, "Invoice cashflow should be deleted after payment registration")

    def test_03_payment_creates_cashflow(self):
        """Test that registering a payment creates a payment cashflow entry."""
        # Create and post invoice
        invoice = self._create_invoice(300.0)

        # Register payment
        payment = self._register_payment(invoice)
        self.assertTrue(payment, "Payment should be created")

        # Check payment cashflow was created
        payment_cashflow = self._get_payment_cashflow_entry(payment)
        self.assertTrue(payment_cashflow, "Payment cashflow should be created")

        # Check cashflow item
        self.assertEqual(len(payment_cashflow.item_ids), 1, "Should have one cashflow item")
        self.assertEqual(payment_cashflow.item_ids.amount, 300.0, "Amount should match payment")
        self.assertEqual(payment_cashflow.item_ids.type, 'in', "Type should be 'in' for inbound payment")

    def test_04_full_payment_flow(self):
        """Test the complete flow: invoice → payment → only payment cashflow remains."""
        # Create and post invoice
        invoice = self._create_invoice(500.0)

        # Count cashflow entries before payment
        invoice_cashflow_before = self._get_invoice_cashflow_entry(invoice)
        self.assertEqual(len(invoice_cashflow_before), 1, "Should have 1 invoice cashflow entry")

        # Register payment
        payment = self._register_payment(invoice)

        # Count cashflow entries after payment
        invoice_cashflow_after = self._get_invoice_cashflow_entry(invoice)
        payment_cashflow = self._get_payment_cashflow_entry(payment)

        self.assertEqual(len(invoice_cashflow_after), 0, "Invoice cashflow should be deleted")
        self.assertEqual(len(payment_cashflow), 1, "Payment cashflow should exist")

        # Verify only payment cashflow for this transaction
        all_entries = self.env['cashflow.entry'].search([
            '|',
            '&', ('model', '=', 'account.move.line'), ('res_id', 'in', invoice.line_ids.ids),
            '&', ('model', '=', 'account.payment'), ('res_id', '=', payment.id),
        ])
        self.assertEqual(len(all_entries), 1, "Should have exactly 1 cashflow entry (payment only)")
        self.assertEqual(all_entries.model, 'account.payment', "Remaining entry should be for payment")

    def test_05_pay_button_simulation(self):
        """Test simulating the Pay button from invoice form - only payment cashflow should remain."""
        # Create and post invoice
        invoice = self._create_invoice(750.0)

        # Verify invoice cashflow exists
        invoice_cashflow = self._get_invoice_cashflow_entry(invoice)
        self.assertEqual(len(invoice_cashflow), 1, "Invoice cashflow should exist before payment")
        invoice_cashflow_id = invoice_cashflow.id

        # Simulate clicking "Pay" button on invoice
        # This opens the account.payment.register wizard with the invoice context
        ctx = {
            'active_model': 'account.move',
            'active_ids': invoice.ids,
            'active_id': invoice.id,
        }

        # Create the payment register wizard (like clicking Pay button)
        PaymentRegister = self.env['account.payment.register'].with_context(**ctx)
        wizard = PaymentRegister.create({
            'journal_id': self.bank_journal.id,
            'payment_date': fields.Date.today(),
        })

        # Execute the payment (like clicking "Create Payment" in the wizard)
        action = wizard.action_create_payments()

        # Get the created payment
        if action and isinstance(action, dict) and action.get('res_id'):
            payment = self.env['account.payment'].browse(action['res_id'])
        else:
            payment = self.env['account.payment'].search([
                ('partner_id', '=', self.partner.id),
            ], order='id desc', limit=1)

        self.assertTrue(payment, "Payment should be created")

        # Verify invoice cashflow was deleted
        invoice_cashflow_after = self._get_invoice_cashflow_entry(invoice)
        self.assertEqual(len(invoice_cashflow_after), 0,
            f"Invoice cashflow (id={invoice_cashflow_id}) should be deleted after Pay button")

        # Verify payment cashflow exists
        payment_cashflow = self._get_payment_cashflow_entry(payment)
        self.assertEqual(len(payment_cashflow), 1, "Payment cashflow should exist")

        # Final verification: only 1 cashflow entry related to this invoice/payment
        all_related_entries = self.env['cashflow.entry'].search([
            '|',
            '&', ('model', '=', 'account.move.line'), ('res_id', 'in', invoice.line_ids.ids),
            '&', ('model', '=', 'account.payment'), ('res_id', '=', payment.id),
        ])
        self.assertEqual(len(all_related_entries), 1,
            "Should have exactly 1 cashflow entry after Pay button (payment only)")
        self.assertEqual(all_related_entries.model, 'account.payment',
            "The only remaining entry should be for payment, not invoice")

    def test_06_payment_without_context(self):
        """Test that invoice cashflow is deleted via reconcile even without context.

        This simulates what might happen in production if the context is lost.
        The reconcile hook should still delete the invoice cashflow.
        """
        import logging
        _logger = logging.getLogger(__name__)

        # Create and post invoice
        invoice = self._create_invoice(850.0)

        # Verify invoice cashflow exists
        invoice_cashflow = self._get_invoice_cashflow_entry(invoice)
        self.assertEqual(len(invoice_cashflow), 1, "Invoice cashflow should exist before payment")
        invoice_cashflow_id = invoice_cashflow.id
        _logger.info("TEST: Invoice cashflow created with id=%s", invoice_cashflow_id)

        # Get the receivable line for later verification
        receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )

        # Create payment WITHOUT context (simulating lost context scenario)
        # This creates a direct payment without the wizard context
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 850.0,
            'journal_id': self.bank_journal.id,
            'date': fields.Date.today(),
        })
        _logger.info("TEST: Payment created with id=%s, state=%s", payment.id, payment.state)

        # At this point, invoice cashflow might still exist because context was not available
        invoice_cashflow_after_create = self._get_invoice_cashflow_entry(invoice)
        _logger.info("TEST: Invoice cashflow after payment create: %s", invoice_cashflow_after_create.ids)

        # Now post the payment - this should trigger reconciliation
        payment.action_post()
        _logger.info("TEST: Payment posted, state=%s", payment.state)

        # Manually reconcile the payment with the invoice
        # Get the payment's move lines
        payment_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )
        _logger.info("TEST: Payment receivable line: %s", payment_line.ids)

        # Reconcile if not already reconciled
        if receivable_line and payment_line and not receivable_line.reconciled:
            (receivable_line + payment_line).reconcile()
            _logger.info("TEST: Reconciliation performed")

        # After reconciliation, invoice cashflow should be deleted by reconcile hook
        invoice_cashflow_after = self._get_invoice_cashflow_entry(invoice)
        _logger.info("TEST: Invoice cashflow after reconcile: %s", invoice_cashflow_after.ids)

        self.assertEqual(len(invoice_cashflow_after), 0,
            f"Invoice cashflow (id={invoice_cashflow_id}) should be deleted after reconciliation")

        # Payment cashflow should exist
        payment_cashflow = self._get_payment_cashflow_entry(payment)
        self.assertEqual(len(payment_cashflow), 1, "Payment cashflow should exist (test_06)")

    def test_07_wizard_creates_payment_and_reconciles(self):
        """Test that wizard properly creates payment and reconciles, deleting invoice cashflow.

        This test uses the wizard but checks what happens at each step.
        """
        import logging
        _logger = logging.getLogger(__name__)

        # Create and post invoice
        invoice = self._create_invoice(950.0)

        # Verify invoice cashflow exists
        invoice_cashflow = self._get_invoice_cashflow_entry(invoice)
        self.assertEqual(len(invoice_cashflow), 1, "Invoice cashflow should exist before payment")
        _logger.info("TEST: Invoice cashflow exists: %s", invoice_cashflow.ids)

        # Create wizard with context (like Pay button)
        ctx = {
            'active_model': 'account.move',
            'active_ids': invoice.ids,
            'active_id': invoice.id,
        }

        # Log the context being used
        _logger.info("TEST: Creating wizard with context: %s", ctx)

        wizard = self.env['account.payment.register'].with_context(**ctx).create({
            'journal_id': self.bank_journal.id,
            'payment_date': fields.Date.today(),
        })
        _logger.info("TEST: Wizard created, env context active_model=%s, active_ids=%s",
                     wizard.env.context.get('active_model'),
                     wizard.env.context.get('active_ids'))

        # Execute payment creation
        action = wizard.action_create_payments()
        _logger.info("TEST: action_create_payments returned: %s", action)

        # Find the payment
        if action and isinstance(action, dict) and action.get('res_id'):
            payment = self.env['account.payment'].browse(action['res_id'])
        else:
            payment = self.env['account.payment'].search([
                ('partner_id', '=', self.partner.id),
            ], order='id desc', limit=1)

        _logger.info("TEST: Payment found: id=%s, state=%s", payment.id if payment else None, payment.state if payment else None)

        # Check payment state
        self.assertTrue(payment, "Payment should be created")

        # Check if invoice is paid
        invoice.invalidate_recordset(['payment_state'])
        _logger.info("TEST: Invoice payment_state=%s", invoice.payment_state)

        # Check invoice cashflow
        invoice_cashflow_after = self._get_invoice_cashflow_entry(invoice)
        _logger.info("TEST: Invoice cashflow after payment: %s", invoice_cashflow_after.ids)

        self.assertEqual(len(invoice_cashflow_after), 0,
            "Invoice cashflow should be deleted after payment via wizard")

        # Payment cashflow should exist
        payment_cashflow = self._get_payment_cashflow_entry(payment)
        self.assertEqual(len(payment_cashflow), 1, "Payment cashflow should exist (test_07)")

    def test_08_payment_in_process_then_reconcile(self):
        """Test the flow where payment stays in_process and is later reconciled.

        This simulates a more realistic production flow where:
        1. Payment is created (in_process state)
        2. Reconciliation happens later
        3. Invoice cashflow should be deleted by reconcile hook
        """
        import logging
        _logger = logging.getLogger(__name__)

        # Create and post invoice
        invoice = self._create_invoice(1100.0)

        # Verify invoice cashflow exists
        invoice_cashflow = self._get_invoice_cashflow_entry(invoice)
        self.assertEqual(len(invoice_cashflow), 1, "Invoice cashflow should exist before payment")
        _logger.info("TEST08: Invoice cashflow created: %s", invoice_cashflow.ids)

        # Get the receivable line
        invoice_receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )
        _logger.info("TEST08: Invoice receivable line: %s", invoice_receivable_line.ids)

        # Create payment directly (not via wizard, to simulate no context)
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 1100.0,
            'journal_id': self.bank_journal.id,
            'date': fields.Date.today(),
        })
        _logger.info("TEST08: Payment created: id=%s, state=%s", payment.id, payment.state)

        # Invoice cashflow should still exist (no context, no reconciliation yet)
        invoice_cashflow_after_create = self._get_invoice_cashflow_entry(invoice)
        _logger.info("TEST08: Invoice cashflow after payment create: %s", invoice_cashflow_after_create.ids)
        self.assertEqual(len(invoice_cashflow_after_create), 1,
            "Invoice cashflow should still exist (payment not reconciled yet)")

        # Post the payment (goes to in_process)
        payment.action_post()
        _logger.info("TEST08: Payment after action_post: state=%s", payment.state)

        # Get the payment's receivable line
        payment_receivable_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )
        _logger.info("TEST08: Payment receivable line: %s", payment_receivable_line.ids)

        # Invoice cashflow might still exist at this point
        invoice_cashflow_after_post = self._get_invoice_cashflow_entry(invoice)
        _logger.info("TEST08: Invoice cashflow after payment post: %s", invoice_cashflow_after_post.ids)

        # Now reconcile (this creates partial_reconcile)
        _logger.info("TEST08: About to reconcile...")
        if invoice_receivable_line and payment_receivable_line and not invoice_receivable_line.reconciled:
            lines_to_reconcile = invoice_receivable_line + payment_receivable_line
            _logger.info("TEST08: Lines to reconcile: %s", lines_to_reconcile.ids)
            lines_to_reconcile.reconcile()
            _logger.info("TEST08: Reconciliation complete")

        # Check invoice state
        invoice.invalidate_recordset(['payment_state'])
        _logger.info("TEST08: Invoice payment_state after reconcile: %s", invoice.payment_state)

        # NOW invoice cashflow should be deleted by reconcile hook
        invoice_cashflow_final = self._get_invoice_cashflow_entry(invoice)
        _logger.info("TEST08: Invoice cashflow after reconcile: %s", invoice_cashflow_final.ids)

        self.assertEqual(len(invoice_cashflow_final), 0,
            "Invoice cashflow should be deleted after reconciliation via partial_reconcile hook")

        # Payment cashflow should exist
        payment_cashflow = self._get_payment_cashflow_entry(payment)
        _logger.info("TEST08: Payment cashflow: %s", payment_cashflow.ids)
        self.assertEqual(len(payment_cashflow), 1, "Payment cashflow should exist (test_08)")
