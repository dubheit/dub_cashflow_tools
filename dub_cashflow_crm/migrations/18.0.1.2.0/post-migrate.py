"""The opportunity forecasts until an order is confirmed, on the customer payment terms.

The configuration records are noupdate, so the new values of the data file
are written here on existing databases.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

MODULE = 'dub_cashflow_crm'

VALUES = {
    'cashflow_config_crm_opportunity': {
        'filter_domain': "[('type', '=', 'opportunity'), ('probability', '>', 0), ('order_ids', 'not any', [('state', '=', 'sale')])]",
        'use_payment_terms': True,
        'payment_term_field': 'partner_id.property_payment_term_id',
        'date_field': 'date_deadline',
    },
    'cashflow_config_line_crm_journal': {
        'python_code': "fixed_bank_journal(record.partner_id.commercial_partner_id)",
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
