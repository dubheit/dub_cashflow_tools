{
    "name": "DUB Treasury Base",
    "version": "18.0.1.1.1",
    "category": "Accounting/Accounting",
    "summary": "Treasury management base: accounts, credit lines, financial instruments",
    "description": """
Treasury Management - Base Module
=================================

This module provides the foundation for treasury management:

* **Treasury Accounts**: Bank accounts, cash, internal accounts
* **Credit Lines**: Overdrafts, advances, factoring facilities
* **Financial Instruments**: Loans, mortgages, leasing, partner loans
* **Installments**: Payment schedules for financial instruments

Integrates with Odoo's native accounting and banking features.
    """,
    "author": "Dubhe Srls",
    "website": "https://www.dubhe.it",
    "license": "OPL-1",
    "depends": [
        "account",
        "dub_cashflow",
    ],
    "data": [
        "security/treasury_security.xml",
        "security/ir.model.access.csv",
        "wizard/credit_line_movement_wizard_views.xml",
        "views/account_move_views.xml",
        "views/treasury_account_views.xml",
        "views/treasury_credit_line_views.xml",
        "views/treasury_financial_instrument_views.xml",
        "views/treasury_menu.xml",
    ],
    "demo": [
        "data/treasury_demo.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
