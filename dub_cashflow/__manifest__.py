{
    "name": "DUB Cashflow",
    "version": "18.0.3.0.0",
    "category": "Accounting",
    "summary": "Manage predictive cash flows",
    "description": """
This module allows to manage predictive cash flows.

Features:
- Configure cashflow generation for any model
- Automatic creation/update/deletion of cashflow entries
- Flexible field mapping with Python expressions
- Filter records with domain expressions
- Scenarios: group configurations to compare alternative forecasts
  (e.g. Base vs Pessimistic) side by side in the analysis pivot
    """,
    "author": "Your Company",
    "website": "https://www.yourcompany.com",
    "depends": [
        "account"
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/cashflow_scenario_data.xml",
        "views/cashflow_scenario_views.xml",
        "views/cashflow_config_views.xml",
        "views/cashflow_entry_views.xml",
        "views/cashflow_report_views.xml",
        "views/cashflow_item_views.xml",
        "data/demo.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "OPL-1",
}
