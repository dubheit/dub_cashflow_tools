{
    'name': 'DUB Cashflow - CRM',
    'version': '18.0.1.2.0',
    'category': 'Accounting',
    'summary': 'Cashflow forecasting from CRM opportunities',
    'description': """
        Generate cashflow entries from CRM opportunities.

        Features:
        - Automatic cashflow entry creation when opportunities are created/updated
        - Uses expected revenue * probability for amount calculation
        - Uses expected closing date for cashflow date
        - Forecast kept until a sale order from the opportunity is confirmed
    """,
    'author': 'Dubhe Srls',
    'website': 'https://www.dubhe.it',
    'license': 'OPL-1',
    'depends': [
        'dub_cashflow',
        'crm',
        'sale_crm',
    ],
    'data': [
        'data/cashflow_config_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
