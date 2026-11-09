from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaleOrderCashflow(TransactionCase):
    """An invoice takes over the forecast of its sale order.

    The order config decides, through its filter, when the order stops
    counting; the invoice hook only asks for a recomputation. Deleting the
    entries from the hook cleared the whole ORM cache in the middle of the
    invoice creation, and a later write on the order in the same transaction
    brought its forecast back.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        partner_vals = {'name': 'Cashflow SO customer'}
        Partner = cls.env['res.partner']
        if 'administrative_category_id' in Partner._fields:
            # Installed customizations may block orders of customers without
            # an administrative category: give it one that does not block.
            partner_vals['administrative_category_id'] = cls.env[
                'res.partner.administrative.category'
            ].search([('block_sale_order', '=', False)], limit=1).id
        cls.partner = Partner.create(partner_vals)
        cls.product = cls.env['product.product'].create({
            'name': 'Cashflow SO service',
            'type': 'service',
            'invoice_policy': 'order',
            'list_price': 100.0,
            'taxes_id': [Command.clear()],
        })

    def _confirmed_order(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'client_order_ref': 'CF-TEST',
            'order_line': [Command.create({
                'product_id': self.product.id, 'product_uom_qty': 2, 'price_unit': 100.0,
            })],
        })
        order.action_confirm()
        self.env.cr.flush()
        return order

    def _order_entries(self, order):
        self.env.cr.flush()
        return self.env['cashflow.entry'].search([
            ('model', '=', 'sale.order'), ('res_id', '=', order.id),
        ])

    def test_invoice_takes_over_order_forecast(self):
        order = self._confirmed_order()
        self.assertTrue(self._order_entries(order))
        order._create_invoices()
        self.assertFalse(self._order_entries(order))

    def test_partially_invoiced_order_stays_out_after_a_write(self):
        """A write on the order in the same transaction keeps it out."""
        order = self._confirmed_order()
        invoice = order._create_invoices()
        invoice.invoice_line_ids.quantity = 1
        self.assertEqual(order.invoice_status, 'to invoice')
        order.write({'note': 'touched after invoicing'})
        self.assertFalse(self._order_entries(order))

    def test_invoice_creation_keeps_orm_cache(self):
        order = self._confirmed_order()
        in_memory = self.env['res.partner'].new({'name': 'Kept in memory'})
        order._create_invoices()
        self.assertEqual(in_memory.name, 'Kept in memory')
