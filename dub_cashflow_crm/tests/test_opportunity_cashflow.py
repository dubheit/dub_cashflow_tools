from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOpportunityCashflow(TransactionCase):
    """A quotation takes over the forecast of its opportunity.

    Typical case: an automation moves the opportunity to the next stage when
    the quotation is created, so the opportunity is written in the same
    transaction; its forecast must not come back next to the quotation's.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env['res.partner'].create({'name': 'Cashflow CRM customer'})

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

    def test_quotation_takes_over_opportunity_forecast(self):
        lead = self._opportunity()
        self.assertTrue(self._lead_entries(lead))
        self._quotation(lead)
        self.assertFalse(self._lead_entries(lead))

    def test_opportunity_written_with_quotation_stays_out(self):
        lead = self._opportunity()
        self._quotation(lead)
        lead.write({'description': 'moved on by an automation'})
        self.assertFalse(self._lead_entries(lead))

    def test_cancelled_quotation_gives_forecast_back(self):
        lead = self._opportunity()
        quotation = self._quotation(lead)
        quotation._action_cancel()
        self.assertTrue(self._lead_entries(lead))
