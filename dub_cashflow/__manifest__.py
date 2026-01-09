{
    "name": "DUB Cashflow",
    "version": "19.0.3.0.0",
    "category": "Accounting",
    "summary": "Manage predictive cash flows",
    "description": """
This module allows to manage predictive cash flows.

Features:
- Configure cashflow generation for any model
- Automatic creation/update/deletion of cashflow entries
- Flexible field mapping with Python expressions
- Filter records with domain expressions
- Recurring templates for planned expenses (salaries, subscriptions, etc.)
- Automatic matching of recurring entries with actual invoices
    """,
    "author": "Dubhe Srls",
    "website": "https://www.dubhe.it",
    "depends": [
        "account"
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/cashflow_config_views.xml",
        "views/cashflow_entry_match_views.xml",
        "views/cashflow_entry_views.xml",
        "views/cashflow_report_views.xml",
        "views/cashflow_item_views.xml",
        "views/cashflow_recurring_views.xml",
        "views/res_config_settings_views.xml",
        "data/demo.xml",
        "data/ir_cron.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "OPL-1",
}
