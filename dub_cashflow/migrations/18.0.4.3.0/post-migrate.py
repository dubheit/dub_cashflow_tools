"""Align the invoice and payment configurations with the document chain.

The configuration records are noupdate, so the new values of data/demo.xml
are written here on existing databases.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

MODULE = 'dub_cashflow'

VALUES = {
    'cashflow_config_move_line': {
        'filter_domain': "[('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']), ('move_id.move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')), ('move_id.state', 'in', ('draft', 'posted')), ('reconciled', '=', False)]",
    },
    'cashflow_config_line_amount': {
        'python_code': "abs(record.amount_residual)",
    },
    'cashflow_config_line_type': {
        'python_code': "'in' if record.amount_residual > 0 else 'out'",
    },
    'cashflow_config_line_currency': {
        'python_code': "record.company_currency_id.id",
    },
    'cashflow_config_line_journal': {
        'python_code': "fixed_bank_journal(record)",
    },
    'cashflow_config_payment': {
        'filter_domain': "[('state', 'in', ('in_process', 'paid')), ('is_matched', '=', False)]",
    },
    'cashflow_config_payment_state': {
        'python_code': "{'draft': 'draft', 'in_process': 'confirmed', 'paid': 'confirmed'}.get(record.state, 'cancelled')",
    },
    'cashflow_config_payment_journal': {
        'python_code': "record.journal_id.id",
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
