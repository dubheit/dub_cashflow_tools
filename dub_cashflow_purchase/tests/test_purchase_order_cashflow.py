from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPurchaseOrderCashflow(TransactionCase):
    """A vendor bill takes over the forecast of its purchase order (see the
    sale order counterpart in dub_cashflow_sale)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.vendor = cls.env['res.partner'].create({'name': 'Cashflow PO vendor'})
        cls.product = cls.env['product.product'].create({
            'name': 'Cashflow PO service',
            'type': 'service',
            'purchase_method': 'purchase',
            'supplier_taxes_id': [Command.clear()],
        })

    def _confirmed_order(self):
        order = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'order_line': [Command.create({
                'product_id': self.product.id, 'product_qty': 2, 'price_unit': 100.0,
                'taxes_id': [Command.clear()],
            })],
        })
        order.button_confirm()
        self.env.cr.flush()
        return order

    def _order_entries(self, order):
        self.env.cr.flush()
        return self.env['cashflow.entry'].search([
            ('model', '=', 'purchase.order'), ('res_id', '=', order.id),
        ])

    def _bill(self, order):
        order.action_create_invoice()
        return order.invoice_ids

    def test_bill_takes_over_order_forecast(self):
        order = self._confirmed_order()
        self.assertTrue(self._order_entries(order))
        self._bill(order)
        self.assertFalse(self._order_entries(order))

    def test_partially_billed_order_stays_out_after_a_write(self):
        order = self._confirmed_order()
        bill = self._bill(order)
        bill.invoice_line_ids.quantity = 1
        self.assertEqual(order.invoice_status, 'to invoice')
        order.write({'notes': 'touched after billing'})
        self.assertFalse(self._order_entries(order))

    def test_bill_creation_keeps_orm_cache(self):
        order = self._confirmed_order()
        in_memory = self.env['res.partner'].new({'name': 'Kept in memory'})
        self._bill(order)
        self.assertEqual(in_memory.name, 'Kept in memory')
