from lxml import etree

from odoo.tests.common import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

FILTERS = (
    'filter_origin_document_confirmed',
    'filter_origin_document_draft',
    'filter_origin_manual',
)


@tagged('post_install', '-at_install')
class TestCashflowOriginFilters(TransactionCase):
    """Entries and items filtered by origin: confirmed document, draft
    document, manual (no source document, or a recurring cashflow)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        currency = cls.env.company.currency_id

        def entry(name, model, state):
            return cls.env['cashflow.entry'].create({
                'name': name,
                'model': model,
                'state': state,
                'item_ids': [(0, 0, {
                    'date': '2026-12-31',
                    'amount': 100.0,
                    'currency_id': currency.id,
                    'type': 'in',
                })],
            })

        cls.document_confirmed = entry('Ordine confermato', 'sale.order', 'confirmed')
        cls.document_draft = entry('Preventivo', 'sale.order', 'draft')
        cls.manual = entry('Movimento manuale', False, 'draft')
        cls.recurring = entry('Stipendi', 'cashflow.recurring', 'draft')
        cls.entries = cls.document_confirmed | cls.document_draft | cls.manual | cls.recurring

    def _filter_domains(self, view_xmlid):
        arch = etree.fromstring(self.env.ref(view_xmlid).get_combined_arch())
        return {
            name: safe_eval(arch.xpath(f"//filter[@name='{name}']")[0].get('domain'))
            for name in FILTERS
        }

    def _check(self, model, view_xmlid, records_of):
        domains = self._filter_domains(view_xmlid)
        expected = {
            'filter_origin_document_confirmed': self.document_confirmed,
            'filter_origin_document_draft': self.document_draft,
            'filter_origin_manual': self.manual | self.recurring,
        }
        scope = records_of(self.entries)
        for name, entries in expected.items():
            found = self.env[model].search([('id', 'in', scope.ids)] + domains[name])
            self.assertEqual(found, records_of(entries), name)

    def test_entry_filters(self):
        self._check('cashflow.entry', 'dub_cashflow.view_cashflow_entry_search', lambda e: e)

    def test_item_filters(self):
        self._check(
            'cashflow.item', 'dub_cashflow.view_cashflow_item_search_analysis',
            lambda e: e.item_ids)

    def test_entry_group_by_state(self):
        arch = etree.fromstring(
            self.env.ref('dub_cashflow.view_cashflow_entry_search').get_combined_arch())
        group_by = arch.xpath("//filter[@name='group_state']")
        self.assertEqual(safe_eval(group_by[0].get('context')), {'group_by': 'state'})
