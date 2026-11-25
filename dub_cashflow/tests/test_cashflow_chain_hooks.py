from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCashflowChainHooks(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.config = cls.env.ref("dub_cashflow.cashflow_config_move_line")
        cls.partner = cls.env["res.partner"].create({"name": "Chain Hooks Partner"})
        cls.income = cls.env["account.account"].search([
            ("account_type", "=", "income"),
            ("company_ids", "in", cls.env.company.id),
        ], limit=1)
        cls.bank_journal = cls.env["account.journal"].create({
            "name": "Chain Hooks Bank",
            "code": "CHB1",
            "type": "bank",
        })

    def _mode(self, link):
        if "payment_mode_id" not in self.env["account.move"]._fields:
            self.skipTest("payment_mode_id not available (OCA account_payment_mode)")
        vals = {
            "name": "Chain mode %s" % link,
            "bank_account_link": link,
            "payment_method_id": self.env.ref(
                "account.account_payment_method_manual_in").id,
            "company_id": self.env.company.id,
        }
        if link == "fixed":
            vals["fixed_journal_id"] = self.bank_journal.id
        return self.env["account.payment.mode"].create(vals)

    def _invoice(self, amount=1000.0, mode=None):
        vals = {
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [(0, 0, {
                "name": "Item",
                "quantity": 1,
                "price_unit": amount,
                "account_id": self.income.id,
                "tax_ids": [(6, 0, [])],
            })],
        }
        if mode:
            vals["payment_mode_id"] = mode.id
        invoice = self.env["account.move"].create(vals)
        invoice.action_post()
        return invoice

    def _receivable(self, invoice):
        return invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable")

    def _entries(self, line):
        self.env.cr.flush()
        return self.env["cashflow.entry"].sudo().search([
            ("model", "=", "account.move.line"),
            ("res_id", "=", line.id),
            ("config_id", "=", self.config.id),
        ])

    def test_fixed_bank_journal_fixed_mode(self):
        mode = self._mode("fixed")
        line = self._receivable(self._invoice(mode=mode))
        self.assertEqual(self.config._fixed_bank_journal(line), self.bank_journal.id)
        self.assertEqual(self.config._payment_mode_of(line), mode)

    def test_fixed_bank_journal_variable_mode_is_false(self):
        mode = self._mode("variable")
        line = self._receivable(self._invoice(mode=mode))
        self.assertFalse(self.config._fixed_bank_journal(line))
        line = self._receivable(self._invoice())
        self.assertFalse(self.config._fixed_bank_journal(line))

    def test_superseded_record_loses_entry(self):
        line = self._receivable(self._invoice())
        self.assertTrue(self._entries(line))
        with patch.object(type(self.config), "_is_superseded", lambda self, rec: True):
            self.config.generate_cashflow(line)
        self.assertEqual(len(self._entries(line)), 0)

    def test_regenerate_recreates_missing_entries(self):
        line = self._receivable(self._invoice(1000.0))
        entries = self._entries(line)
        self.assertTrue(entries)
        entries.unlink()
        self.assertFalse(self._entries(line))
        self.assertTrue(self.config.action_regenerate())
        entry = self._entries(line)
        self.assertEqual(len(entry), 1)
        self.assertEqual(sum(entry.item_ids.mapped("amount")), 1000.0)

    def test_regenerate_drops_stale_entries(self):
        invoice = self._invoice(500.0)
        line = self._receivable(invoice)
        invoice.button_draft()
        invoice.button_cancel()
        self.assertEqual(invoice.state, "cancel")
        self._entries(line).unlink()
        stale = self.env["cashflow.entry"].create({
            "name": "stale",
            "model": "account.move.line",
            "res_id": line.id,
            "config_id": self.config.id,
            "date": fields.Date.today(),
        })
        self.config.action_regenerate()
        self.assertFalse(stale.exists())
