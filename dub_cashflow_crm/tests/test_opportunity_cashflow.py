from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOpportunityCashflow(TransactionCase):
    """The opportunity forecasts until an order is confirmed.

    A quotation does not take the forecast over: the opportunity keeps it
    until a linked order is confirmed, and gets it back when that order is
    cancelled.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env['res.partner'].create({'name': 'Cashflow CRM customer'})
        cls.product = cls.env['product.product'].create({
            'name': 'Cashflow CRM service', 'type': 'service', 'list_price': 100.0,
        })

    def _opportunity(self):
        lead = self.env['crm.lead'].create({
            'name': 'Cashflow opportunity',
            'type': 'opportunity',
            'partner_id': self.partner.id,
            'expected_revenue': 1000.0,
            'probability': 50.0,
        })
        self.env.cr.flush()
        return lead

    def _lead_entries(self, lead):
        self.env.cr.flush()
        return self.env['cashflow.entry'].search([
            ('model', '=', 'crm.lead'), ('res_id', '=', lead.id),
        ])

    def _quotation(self, lead):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'opportunity_id': lead.id,
            'client_order_ref': 'CF-TEST',
        })

    def test_opportunity_written_with_quotation_stays(self):
        lead = self._opportunity()
        self._quotation(lead)
        lead.write({'description': 'moved on by an automation'})
        self.assertTrue(self._lead_entries(lead))

    def test_cancelled_confirmed_order_gives_forecast_back(self):
        lead = self._opportunity()
        quotation = self._quotation(lead)
        quotation.order_line = [Command.create({
            'product_id': self.product.id, 'product_uom_qty': 1, 'price_unit': 100.0,
        })]
        quotation.action_confirm()
        self.assertFalse(self._lead_entries(lead))
        quotation._action_cancel()
        self.assertTrue(self._lead_entries(lead))

    def test_opportunity_kept_with_quotation_dropped_when_confirmed(self):
        lead = self._opportunity()
        lead.date_deadline = '2030-01-31'
        entries = self._lead_entries(lead)
        self.assertEqual(sum(entries.mapped('total_in')), 500.0)
        quotation = self._quotation(lead)
        self.assertEqual(sum(self._lead_entries(lead).mapped('total_in')), 500.0)
        quotation.order_line = [Command.create({
            'product_id': self.product.id, 'product_uom_qty': 1, 'price_unit': 100.0,
        })]
        quotation.action_confirm()
        self.assertFalse(self._lead_entries(lead))
