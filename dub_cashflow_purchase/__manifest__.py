{
    'name': 'DUB Cashflow - Purchase',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Cashflow generation from Purchase Orders',
    'description': """
        Automatically generate cashflow entries (outflow) from purchase orders.
        Supports payment terms with multiple installments.

        Mirrors dub_cashflow_sale: open purchase orders feed the cash-out side of
        the forecast and are removed once the related vendor bill is created.
    """,
    'author': 'Dubhe Srls',
    'website': 'https://www.dubhe.it',
    'license': 'OPL-1',
    'depends': [
        'dub_cashflow',
        'purchase',
    ],
    'data': [
        'data/cashflow_config_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
