from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestCashflowCategory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Category = cls.env['cashflow.category']
        cls.company = cls.env.company

    def test_01_create_and_hierarchy(self):
        """Categories can be created with a parent/child hierarchy."""
        parent = self.Category.create({'name': 'Operating', 'code': 'op'})
        child = self.Category.create({
            'name': 'Suppliers',
            'code': 'op_suppliers',
            'parent_id': parent.id,
        })
        self.assertEqual(child.parent_id, parent)
        self.assertIn(child, parent.child_ids)
        self.assertEqual(child.complete_name, 'Operating / Suppliers')

    def test_02_recursion_guard(self):
        """A category cannot become its own ancestor (Odoo _parent_store)."""
        a = self.Category.create({'name': 'A', 'code': 'a'})
        b = self.Category.create({'name': 'B', 'code': 'b', 'parent_id': a.id})
        with self.assertRaises(UserError):
            a.parent_id = b
            self.env.flush_all()

    def test_03_code_unique_per_company(self):
        """The code is unique per company."""
        self.Category.create({'name': 'First', 'code': 'dup'})
        with self.assertRaises(Exception):
            self.Category.create({'name': 'Second', 'code': 'dup'})
            self.env.flush_all()

    def test_04_resolve_code_found(self):
        """_resolve_code returns the matching category."""
        cat = self.Category.create({'name': 'Taxes', 'code': 'taxes_test'})
        resolved = self.Category._resolve_code('taxes_test', self.company)
        self.assertEqual(resolved, cat)

    def test_05_resolve_code_missing(self):
        """_resolve_code returns empty recordset for an unknown code."""
        resolved = self.Category._resolve_code('does_not_exist', self.company)
        self.assertFalse(resolved)

    def test_06_resolve_code_company_shared(self):
        """A company-shared category (no company) is resolved as fallback."""
        shared = self.Category.create({
            'name': 'Shared',
            'code': 'shared_test',
            'company_id': False,
        })
        resolved = self.Category._resolve_code('shared_test', self.company)
        self.assertEqual(resolved, shared)

    def test_07_classifier_assigns_category(self):
        """A cashflow.config with a category_code classifier assigns the category."""
        cat = self.Category.create({'name': 'Collections', 'code': 'collections_test'})
        config = self.env['cashflow.config'].create({
            'name': 'Category Test Config',
            'model_id': self.env.ref('base.model_res_partner').id,
        })
        self.env['cashflow.config.line'].create({
            'config_id': config.id,
            'cashflow_field': 'category_code',
            'source_type': 'fixed_value',
            'fixed_value': 'collections_test',
        })
        partner = self.env['res.partner'].create({'name': 'Category Partner'})
        entry_vals, _item_vals = config._prepare_cashflow_vals(partner)
        self.assertEqual(entry_vals.get('category_id'), cat.id)

    def test_08_classifier_missing_code_leaves_empty(self):
        """An unknown category code leaves category_id unset, no exception."""
        config = self.env['cashflow.config'].create({
            'name': 'Category Missing Config',
            'model_id': self.env.ref('base.model_res_partner').id,
        })
        self.env['cashflow.config.line'].create({
            'config_id': config.id,
            'cashflow_field': 'category_code',
            'source_type': 'fixed_value',
            'fixed_value': 'nope_unknown',
        })
        partner = self.env['res.partner'].create({'name': 'Category Partner 2'})
        entry_vals, _item_vals = config._prepare_cashflow_vals(partner)
        self.assertFalse(entry_vals.get('category_id'))
