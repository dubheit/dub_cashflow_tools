from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTreasuryAccount(TransactionCase):
    """Test cases for Treasury Account model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.TreasuryAccount = cls.env['treasury.account']
        cls.company = cls.env.company

        # Get or create a bank journal
        cls.bank_journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        if not cls.bank_journal:
            cls.bank_journal = cls.env['account.journal'].create({
                'name': 'Test Bank',
                'type': 'bank',
                'code': 'TBNK',
                'company_id': cls.company.id,
            })

    def test_create_bank_account(self):
        """Test creating a bank treasury account."""
        account = self.TreasuryAccount.create({
            'name': 'Test Bank Account',
            'code': 'TBANK',
            'account_type': 'bank',
            'journal_id': self.bank_journal.id,
        })

        self.assertEqual(account.name, 'Test Bank Account')
        self.assertEqual(account.account_type, 'bank')
        self.assertEqual(account.company_id, self.company)
        self.assertTrue(account.active)

    def test_create_cash_account(self):
        """Test creating a cash treasury account."""
        account = self.TreasuryAccount.create({
            'name': 'Test Cash Account',
            'code': 'TCASH',
            'account_type': 'cash',
        })

        self.assertEqual(account.account_type, 'cash')

    def test_create_internal_account(self):
        """Test creating an internal treasury account."""
        account = self.TreasuryAccount.create({
            'name': 'Test Internal Account',
            'code': 'TINT',
            'account_type': 'internal',
        })

        self.assertEqual(account.account_type, 'internal')

    def test_archive_account(self):
        """Test archiving a treasury account."""
        account = self.TreasuryAccount.create({
            'name': 'Test Account to Archive',
            'code': 'TARCH',
            'account_type': 'bank',
        })

        self.assertTrue(account.active)
        account.active = False
        self.assertFalse(account.active)

    def test_account_with_iban(self):
        """Test treasury account IBAN read from its bank account.

        ``iban`` is a related field on ``bank_account_id.acc_number``, so it is
        populated through the linked res.partner.bank, not written directly.
        """
        bank_account = self.env['res.partner.bank'].create({
            'acc_number': 'IT60X0542811101000000123456',
            'partner_id': self.company.partner_id.id,
        })
        account = self.TreasuryAccount.create({
            'name': 'Test Account with IBAN',
            'code': 'TIBAN',
            'account_type': 'bank',
            'bank_account_id': bank_account.id,
        })

        self.assertEqual(account.iban, 'IT60X0542811101000000123456')

    def test_company_relation(self):
        """Test that company_id is correctly set from journal."""
        account = self.TreasuryAccount.create({
            'name': 'Test Company Relation',
            'code': 'TREL',
            'account_type': 'bank',
            'journal_id': self.bank_journal.id,
        })

        self.assertEqual(account.company_id, self.bank_journal.company_id)
