from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPurchaseCashflowChain(TransactionCase):
    """A purchase order forecasts what is still to bill, on its payment bank."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.vendor = cls.env['res.partner'].create({'name': 'Cashflow chain vendor'})
        cls.product = cls.env['product.product'].create({
            'name': 'Chain purchase service',
            'type': 'service',
            'purchase_method': 'purchase',
            'supplier_taxes_id': [Command.clear()],
        })

    def _order(self, qty=10):
        return self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'order_line': [Command.create({
                'product_id': self.product.id, 'product_qty': qty, 'price_unit': 100.0,
                'taxes_id': [Command.clear()],
            })],
        })

    def _entries(self, order):
        self.env.cr.flush()
        return self.env['cashflow.entry'].search([
            ('model', '=', 'purchase.order'), ('res_id', '=', order.id),
        ])

    def _bill(self, order, qty):
        order.action_create_invoice()
        bill = order.invoice_ids
        bill.invoice_line_ids.quantity = qty
        return bill

    def test_rfq_entry_is_draft(self):
        order = self._order()
        entries = self._entries(order)
        self.assertTrue(entries)
        self.assertEqual(set(entries.mapped('state')), {'draft'})
        self.assertEqual(sum(entries.mapped('total_out')), 1000.0)

    def test_partially_billed_order_keeps_remainder(self):
        order = self._order()
        order.button_confirm()
        bill = self._bill(order, 4)
        bill.invoice_date = bill.date = '2026-01-10'
        bill.action_post()
        self.assertEqual(sum(self._entries(order).mapped('total_out')), 600.0)
        bill_entries = self.env['cashflow.entry'].search([
            ('model', '=', 'account.move.line'),
            ('res_id', 'in', bill.line_ids.ids),
        ])
        self.assertEqual(sum(bill_entries.mapped('total_out')), 400.0)

    def test_draft_bill_keeps_order_remainder(self):
        order = self._order()
        order.button_confirm()
        bill = self._bill(order, 4)
        self.assertEqual(sum(self._entries(order).mapped('total_out')), 1000.0)
        bill.invoice_date = bill.date = '2026-01-10'
        bill.action_post()
        self.assertEqual(sum(self._entries(order).mapped('total_out')), 600.0)

    def test_journal_from_order_payment_mode(self):
        if 'payment_mode_id' not in self.env['purchase.order']._fields:
            self.skipTest('payment_mode_id is not available')
        journal = self.env['account.journal'].create({
            'name': 'Chain purchase bank', 'type': 'bank', 'code': 'CHPB',
        })
        method = self.env['account.payment.method.line'].search([
            ('payment_type', '=', 'outbound'),
        ], limit=1).payment_method_id
        mode = self.env['account.payment.mode'].create({
            'name': 'Chain purchase mode',
            'payment_method_id': method.id,
            'bank_account_link': 'fixed',
            'fixed_journal_id': journal.id,
        })
        order = self._order()
        order.payment_mode_id = mode
        self.assertEqual(set(self._entries(order).mapped('journal_id')), {journal})

    def test_full_draft_bill_keeps_order_remainder(self):
        order = self._order()
        order.button_confirm()
        bill = self._bill(order, 10)
        self.assertEqual(sum(self._entries(order).mapped('total_out')), 1000.0)
        bill.invoice_date = bill.date = '2026-01-10'
        bill.action_post()
        self.assertFalse(self._entries(order))
