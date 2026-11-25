"""Purchase orders forecast their unbilled remainder, in company currency, on
the payment mode bank.

The configuration records are noupdate, so the new values of the data file
are written here on existing databases.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

MODULE = 'dub_cashflow_purchase'

VALUES = {
    'cashflow_config_purchase_order': {
        'filter_domain': "[('state', '!=', 'cancel'), '|', ('invoice_status', '!=', 'invoiced'), ('order_line.invoice_lines.parent_state', '=', 'draft')]",
    },
    'cashflow_config_line_po_amount': {
        'python_code': "record._cashflow_forecast_amount()",
    },
    'cashflow_config_line_po_currency': {
        'python_code': "record.company_id.currency_id.id",
    },
    'cashflow_config_line_po_journal': {
        'python_code': "fixed_bank_journal(record)",
    },
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, values in VALUES.items():
        record = env.ref('%s.%s' % (MODULE, xmlid), raise_if_not_found=False)
        if not record:
            _logger.info("Skipping %s: record not found", xmlid)
            continue
        record.write(values)
        _logger.info("Updated cashflow configuration %s", xmlid)
