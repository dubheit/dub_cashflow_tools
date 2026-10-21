from odoo import Command, fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCashflowDeferred(TransactionCase):
    """Cashflow is recomputed at the end of the transaction, not inside the
    write that triggers it.

    Recomputing a cashflow deletes its items, and every ``unlink()`` clears the
    whole ORM cache. Done inside a write, that wiped the in-memory records of
    whatever operation was running: validating a batch payment in the bank
    reconciliation widget lost the batch line and failed with "The entry is not
    balanced".
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env['res.partner'].create({'name': 'Cashflow deferred partner'})
        cls.account_income = cls.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_ids', 'in', cls.env.company.id),
        ], limit=1)

    def _post_invoice(self, amount=100.0):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [Command.create({
                'name': 'Deferred cashflow',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.account_income.id,
                'tax_ids': [Command.clear()],
            })],
        })
        invoice.action_post()
        return invoice

    def _receivable_entry(self, invoice):
        receivable = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable')
        return self.env['cashflow.entry'].search([
            ('model', '=', 'account.move.line'),
            ('res_id', 'in', receivable.ids),
        ])

    def test_in_memory_record_survives_cashflow_hook(self):
        """A write that triggers the cashflow leaves the ORM cache alone."""
        invoice = self._post_invoice()
        self.env.cr.flush()
        in_memory = self.env['res.partner'].new({'name': 'Kept in memory'})

        invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
        ).write({'name': 'touched'})

        self.assertEqual(in_memory.name, 'Kept in memory')

    def test_cashflow_is_up_to_date_after_flush(self):
        """Deferring does not lose the update: it lands when the cursor flushes."""
        invoice = self._post_invoice(250.0)
        self.env.cr.flush()
        entry = self._receivable_entry(invoice)
        self.assertEqual(entry.item_ids.amount, 250.0)

    def test_batch_payment_validates_in_bank_reconciliation(self):
        """A batch of payments without journal entry validates in the widget."""
        if 'bank.rec.widget' not in self.env or 'account.batch.payment' not in self.env:
            self.skipTest("needs account_accountant_batch_payment")
        bank = self.env['account.journal'].search([
            ('type', '=', 'bank'), ('company_id', '=', self.env.company.id),
        ], limit=1)
        method_line = bank.outbound_payment_method_line_ids[:1]
        # No outstanding account: the payments get their entry only when the
        # widget validates them, which is where the cashflow hook kicked in.
        method_line.payment_account_id = False
        expense = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', self.env.company.id),
        ], limit=1)
        bills = self.env['account.move']
        for name, amount in (('Vendor A', 1219.63), ('Vendor B', 1688.72)):
            bill = self.env['account.move'].create({
                'move_type': 'in_invoice',
                'partner_id': self.env['res.partner'].create({'name': name}).id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': [Command.create({
                    'name': 'Batch', 'quantity': 1, 'price_unit': amount,
                    'account_id': expense.id, 'tax_ids': [Command.clear()],
                })],
            })
            bill.action_post()
            bills |= bill
        payments = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=bills.ids,
        ).create({
            'journal_id': bank.id,
            'payment_method_line_id': method_line.id,
            'group_payment': False,
        })._create_payments()
        self.assertFalse(payments.move_id)
        batch = self.env['account.batch.payment'].create({
            'journal_id': bank.id,
            'batch_type': 'outbound',
            'payment_method_id': method_line.payment_method_id.id,
            'payment_ids': [Command.set(payments.ids)],
        })
        st_line = self.env['account.bank.statement.line'].create({
            'journal_id': bank.id,
            'date': fields.Date.today(),
            'payment_ref': 'Batch',
            'amount': -sum(payments.mapped('amount')),
        })
        wizard = self.env['bank.rec.widget'].with_context(
            default_st_line_id=st_line.id).new({})
        wizard._action_add_new_batched_amls(batch)

        wizard._action_validate()

        self.assertTrue(st_line.is_reconciled)
