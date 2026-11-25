from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCashflowInvoiceLines(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({'name': 'Cashflow Line Partner'})
        cls.bank_journal = cls._create_bank_journal('Cashflow Test Bank', 'CFTB')

    @classmethod
    def _create_bank_journal(cls, name, code, outstanding_account=True):
        """Bank journal, by default with outstanding accounts (payments get moves)."""
        journal = cls.env['account.journal'].create({
            'name': name,
            'type': 'bank',
            'code': code,
            'company_id': cls.company.id,
        })
        if not outstanding_account:
            return journal
        outstanding = cls.env['account.account'].create({
            'name': 'Outstanding %s' % code,
            'code': 'OUT%s' % code,
            'account_type': 'asset_current',
            'reconcile': True,
        })
        (journal.inbound_payment_method_line_ids
         | journal.outbound_payment_method_line_ids).payment_account_id = outstanding
        return journal

    def _invoice(self, move_type='out_invoice', amount=1000.0, tax=None,
                 currency=None, date=None):
        line = {'name': 'Line', 'quantity': 1, 'price_unit': amount}
        if tax:
            line['tax_ids'] = [(6, 0, tax.ids)]
        vals = {
            'move_type': move_type,
            'partner_id': self.partner.id,
            'invoice_date': date or fields.Date.today(),
            'invoice_line_ids': [(0, 0, line)],
        }
        if currency:
            vals['currency_id'] = currency.id
        move = self.env['account.move'].create(vals)
        move.action_post()
        return move

    def _term_line(self, move):
        return move.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable'))

    def _entries(self, model, ids):
        self.env.cr.flush()
        return self.env['cashflow.entry'].search([
            ('model', '=', model), ('res_id', 'in', ids)])

    def _pay(self, move, amount, journal=None):
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids,
        ).create({
            'journal_id': (journal or self.bank_journal).id,
            'amount': amount,
            'communication': 'unrelated memo',
            'payment_date': fields.Date.today(),
        })
        wizard.action_create_payments()

    def test_partial_payment_uses_residual(self):
        tax = self.env['account.tax'].create({
            'name': 'Tax 22 cashflow', 'amount': 22.0,
            'amount_type': 'percent', 'type_tax_use': 'sale',
        })
        invoice = self._invoice(amount=1000.0, tax=tax)
        self.assertAlmostEqual(invoice.amount_total, 1220.0)
        self._pay(invoice, 220.0)
        entry = self._entries('account.move.line', self._term_line(invoice).ids)
        self.assertEqual(len(entry), 1)
        self.assertAlmostEqual(entry.item_ids.amount, 1000.0)

    def test_reversed_invoice_has_no_entry(self):
        invoice = self._invoice(amount=500.0)
        line = self._term_line(invoice)
        self.assertTrue(self._entries('account.move.line', line.ids))
        reversal = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'journal_id': invoice.journal_id.id})
        action = reversal.refund_moves()
        # The credit note is created in draft; posting it reconciles it with
        # the reversed invoice.
        self.env['account.move'].browse(action['res_id']).action_post()
        self.assertTrue(line.reconciled)
        self.assertFalse(self._entries('account.move.line', line.ids))

    def test_foreign_currency_bill_uses_company_currency(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        self.assertNotEqual(usd, self.company.currency_id)
        self.env['res.currency.rate'].create({
            'currency_id': usd.id,
            'company_id': self.company.id,
            'name': fields.Date.today(),
            'rate': 1.25,
        })
        bill = self._invoice(move_type='in_invoice', amount=1250.0, currency=usd)
        self._pay(bill, 250.0)
        entry = self._entries('account.move.line', self._term_line(bill).ids)
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry.item_ids.currency_id, self.company.currency_id)
        self.assertAlmostEqual(entry.item_ids.amount, 800.0)

    def test_unmatched_payment_is_forecast_on_its_journal(self):
        journal = self._create_bank_journal('Cashflow Other Bank', 'CFOB')
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner.id,
            'amount': 500.0,
            'journal_id': journal.id,
            'date': fields.Date.today(),
        })
        payment.action_post()
        self.assertEqual(payment.state, 'in_process')
        entry = self._entries('account.payment', payment.ids)
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry.state, 'confirmed')
        self.assertEqual(entry.item_ids.type, 'out')
        self.assertEqual(entry.item_ids.journal_id, journal)

    def test_moveless_payment_is_left_to_the_invoice_forecast(self):
        journal = self._create_bank_journal('Cashflow No Outstanding', 'CFNO', outstanding_account=False)
        invoice = self._invoice(amount=700.0)
        self._pay(invoice, 700.0, journal=journal)
        payment = self.env['account.payment'].search([('partner_id', '=', self.partner.id)])
        self.assertEqual(payment.state, 'in_process')
        self.assertFalse(payment.move_id)
        self.assertFalse(self._entries('account.payment', payment.ids))
        entry = self._entries('account.move.line', self._term_line(invoice).ids)
        self.assertEqual(len(entry), 1)
        self.assertAlmostEqual(entry.item_ids.amount, 700.0)

    def test_moveless_unlinked_payment_not_forecast(self):
        journal = self._create_bank_journal('Cashflow No Outstanding 2', 'CFN2', outstanding_account=False)
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner.id,
            'amount': 500.0,
            'journal_id': journal.id,
            'date': fields.Date.today(),
        })
        payment.action_post()
        self.assertEqual(payment.state, 'in_process')
        self.assertFalse(payment.move_id)
        self.assertFalse(payment.invoice_ids)
        self.assertFalse(self._entries('account.payment', payment.ids))

    def test_foreign_currency_payment_uses_company_currency(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        self.assertNotEqual(usd, self.company.currency_id)
        self.env['res.currency.rate'].create({
            'currency_id': usd.id,
            'company_id': self.company.id,
            'name': fields.Date.today(),
            'rate': 1.25,
        })
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner.id,
            'amount': 1250.0,
            'currency_id': usd.id,
            'journal_id': self.bank_journal.id,
            'date': fields.Date.today(),
        })
        payment.action_post()
        entry = self._entries('account.payment', payment.ids)
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry.item_ids.currency_id, self.company.currency_id)
        self.assertAlmostEqual(entry.item_ids.amount, 1000.0)

    def test_payment_entry_leaves_when_matched_with_the_bank(self):
        journal = self._create_bank_journal('Cashflow Matched Bank', 'CFMB')
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner.id,
            'amount': 500.0,
            'journal_id': journal.id,
            'date': fields.Date.today(),
        })
        payment.action_post()
        entry = self._entries('account.payment', payment.ids)
        self.assertEqual(entry.state, 'confirmed')
        statement_line = self.env['account.bank.statement.line'].create({
            'journal_id': journal.id,
            'amount': -500.0,
            'date': fields.Date.today(),
            'payment_ref': 'Bank match',
        })
        _liquidity, suspense, _other = statement_line._seek_for_lines()
        outstanding_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_id == payment.outstanding_account_id)
        suspense.account_id = payment.outstanding_account_id
        (suspense + outstanding_line).reconcile()
        self.assertTrue(payment.is_matched)
        self.assertFalse(self._entries('account.payment', payment.ids))
