from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaleCashflowChain(TransactionCase):
    """A sale order forecasts what is still to invoice, on its payment bank."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        partner_vals = {'name': 'Cashflow chain customer'}
        Partner = cls.env['res.partner']
        if 'administrative_category_id' in Partner._fields:
            partner_vals['administrative_category_id'] = cls.env[
                'res.partner.administrative.category'
            ].search([('block_sale_order', '=', False)], limit=1).id
        cls.partner = Partner.create(partner_vals)
        Product = cls.env['product.product']
        cls.service = Product.create({
            'name': 'Chain service', 'type': 'service',
            'invoice_policy': 'order', 'list_price': 100.0,
            'taxes_id': [Command.clear()],
        })
        cls.goods = Product.create({
            'name': 'Chain goods', 'type': 'consu', 'is_storable': True,
            'invoice_policy': 'delivery', 'list_price': 100.0,
            'taxes_id': [Command.clear()],
        })

    def _order(self, product, qty=10):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'product_id': product.id, 'product_uom_qty': qty, 'price_unit': 100.0,
            })],
        })

    def _entries(self, order):
        self.env.cr.flush()
        return self.env['cashflow.entry'].search([
            ('model', '=', 'sale.order'), ('res_id', '=', order.id),
        ])

    def test_quotation_entry_is_draft(self):
        order = self._order(self.service)
        entries = self._entries(order)
        self.assertTrue(entries)
        self.assertEqual(set(entries.mapped('state')), {'draft'})
        self.assertEqual(sum(entries.mapped('total_in')), 1000.0)

    def test_partially_invoiced_order_keeps_remainder(self):
        order = self._order(self.service)
        order.action_confirm()
        invoice = order._create_invoices()
        invoice.invoice_line_ids.quantity = 4
        invoice.action_post()
        self.assertEqual(sum(self._entries(order).mapped('total_in')), 600.0)
        invoice_entries = self.env['cashflow.entry'].search([
            ('model', '=', 'account.move.line'),
            ('res_id', 'in', invoice.line_ids.ids),
        ])
        self.assertEqual(sum(invoice_entries.mapped('total_in')), 400.0)

    def test_undelivered_order_keeps_full_amount(self):
        order = self._order(self.goods)
        order.action_confirm()
        entries = self._entries(order)
        self.assertEqual(set(entries.mapped('state')), {'confirmed'})
        self.assertEqual(sum(entries.mapped('total_in')), 1000.0)

    def test_journal_from_order_payment_mode(self):
        if 'payment_mode_id' not in self.env['sale.order']._fields:
            self.skipTest('payment_mode_id is not available')
        journal = self.env['account.journal'].create({
            'name': 'Chain bank', 'type': 'bank', 'code': 'CHNB',
        })
        method = self.env['account.payment.method.line'].search([
            ('payment_type', '=', 'inbound'),
        ], limit=1).payment_method_id
        mode = self.env['account.payment.mode'].create({
            'name': 'Chain mode',
            'payment_method_id': method.id,
            'bank_account_link': 'fixed',
            'fixed_journal_id': journal.id,
        })
        order = self._order(self.service)
        order.payment_mode_id = mode
        self.assertEqual(set(self._entries(order).mapped('journal_id')), {journal})

    def test_full_draft_invoice_keeps_order_remainder(self):
        order = self._order(self.service)
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(sum(self._entries(order).mapped('total_in')), 1000.0)
        invoice.action_post()
        self.assertFalse(self._entries(order))
