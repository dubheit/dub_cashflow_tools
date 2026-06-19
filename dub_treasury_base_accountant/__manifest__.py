{
    "name": "DUB Treasury Base - Accounting",
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "Glue module: move the Treasury menu under Accounting when Odoo Accounting is installed",
    "description": """
Treasury Management - Accounting bridge
=======================================

Glue module automatically installed when both ``dub_treasury_base`` and the
Odoo Accounting app (``accountant``) are installed.

It moves the Treasury menu from Invoicing (``account.menu_finance``) to the
dedicated Accounting menu (``accountant.menu_accounting``), so the menu always
shows up under the correct top-level entry regardless of the Odoo edition.
    """,
    "author": "Dubhe Srls",
    "website": "https://www.dubhe.it",
    "license": "OPL-1",
    "depends": [
        "dub_treasury_base",
        "accountant",
    ],
    "data": [
        "views/treasury_menu_accountant.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
}
