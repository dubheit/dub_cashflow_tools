{
    'name': 'DUB Cashflow - Sale',
    'version': '18.0.1.0.1',
    'category': 'Accounting',
    'summary': 'Cashflow generation from Sale Orders',
    'description': """
        Automatically generate cashflow entries from sale orders.
        Supports payment terms with multiple installments.
    """,
    'author': 'Digitalbox',
    'website': 'https://www.digitalbox.it',
    'license': 'LGPL-3',
    'depends': [
        'dub_cashflow',
        'sale',
    ],
    'data': [
        'data/demo.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
