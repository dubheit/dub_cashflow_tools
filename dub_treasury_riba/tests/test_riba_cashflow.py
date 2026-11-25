from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRibaCashflow(TransactionCase):
    """A presented effetto replaces the invoice installment in the forecast."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.journal = cls.env["account.journal"].create({
            "name": "Test Bank",
            "code": "TBK",
            "type": "bank",
            "company_id": company.id,
        })
        treasury_account = cls.env["treasury.account"].create({
            "name": "Test Bank",
            "code": "TBK-A",
            "account_type": "bank",
            "journal_id": cls.journal.id,
        })
        cls.credit_line = cls.env["treasury.credit.line"].create({
            "name": "SBF",
            "account_id": treasury_account.id,
            "credit_type": "sbf",
            "limit_amount": 450000.0,
        })
        acceptance_account = cls.env["account.account"].create({
            "name": "Test Acceptance",
            "code": "TACC01",
            "account_type": "asset_current",
            "reconcile": True,
        })
        partner_bank = cls.env["res.partner.bank"].create({
            "acc_number": "IT60X0542811101000000123456",
            "partner_id": company.partner_id.id,
        })
        cls.riba_config = cls.env["riba.configuration"].create({
            "name": "Test SBF",
            "type": "sbf",
            "bank_id": partner_bank.id,
            "acceptance_journal_id": cls.journal.id,
            "acceptance_account_id": acceptance_account.id,
            "credit_line_id": cls.credit_line.id,
        })
        cls.due = fields.Date.today() + timedelta(days=60)
        income = cls.env["account.account"].search([
            ("account_type", "=", "income"),
            ("company_ids", "in", company.id),
        ], limit=1)
        invoice = cls.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": cls.partner.id,
            "invoice_date": fields.Date.today(),
            "invoice_date_due": cls.due,
            "invoice_line_ids": [(0, 0, {
                "name": "Test Product",
                "quantity": 1,
                "price_unit": 1000.0,
                "account_id": income.id,
                "tax_ids": [(5, 0, 0)],
            })],
        })
        invoice.action_post()
        cls.receivable = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable")
        cls.slip = cls.env["riba.slip"].create({
            "name": "SLIP/TEST/1",
            "config_id": cls.riba_config.id,
        })
        cls.slip_line = cls.env["riba.slip.line"].create({
            "slip_id": cls.slip.id,
            "partner_id": cls.partner.id,
            "due_date": cls.due,
            "sequence": 1,
        })
        cls.env["riba.slip.move.line"].create({
            "riba_line_id": cls.slip_line.id,
            "move_line_id": cls.receivable.id,
            "amount": 1000.0,
        })
        cls.env.cr.flush()

    def _entries(self, model, record):
        self.env.cr.flush()
        return self.env["cashflow.entry"].search([
            ("model", "=", model), ("res_id", "=", record.id)])

    def _set_state(self, state):
        self.slip_line.write({"state": state})

    def test_presented_effetto_replaces_invoice_entry(self):
        self.assertTrue(self._entries("account.move.line", self.receivable))
        self._set_state("confirmed")
        self.assertFalse(self._entries("account.move.line", self.receivable))
        entry = self._entries("riba.slip.line", self.slip_line)
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry.journal_id, self.journal)
        self.assertEqual(entry.item_ids.date, self.due)
        self.assertEqual(entry.item_ids.type, "in")
        self.assertEqual(entry.item_ids.amount, 1000.0)

    def test_credited_effetto_stays_and_counts(self):
        self._set_state("confirmed")
        self._set_state("credited")
        self.assertEqual(len(self._entries("riba.slip.line", self.slip_line)), 1)
        self.assertFalse(self._entries("account.move.line", self.receivable))
        self.assertEqual(self.credit_line._get_riba_usage(), 1000.0)

    def test_past_due_returns_to_invoice(self):
        self._set_state("confirmed")
        self._set_state("past_due")
        self.assertFalse(self._entries("riba.slip.line", self.slip_line))
        entry = self._entries("account.move.line", self.receivable)
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry.item_ids.amount, 1000.0)
