"""Align the invoice and payment configurations with the document chain.

The configuration records are noupdate, so the new values of data/demo.xml
are written here on existing databases.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

MODULE = 'dub_cashflow'

RECONCILE_ACTION_CODE = '''
# _logger is available from eval_context
# Process each reconcile record (handles both single record and recordset)
for rec in records:
    _logger.info("CASHFLOW RECONCILE: Processing partial_reconcile id=%s, operation=%s", rec.id, operation)

    # Get the debit and credit move lines
    lines = env['account.move.line']
    if rec.debit_move_id:
        lines |= rec.debit_move_id
    if rec.credit_move_id:
        lines |= rec.credit_move_id

    # Filter to invoice receivable/payable lines
    invoice_lines = lines.filtered(
        lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
        and l.move_id.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
    )

    if invoice_lines:
        # Update invoice cashflow (recalculate amount based on linked payments)
        _logger.info("CASHFLOW RECONCILE: Updating cashflow for invoice_lines=%s", invoice_lines.ids)
        env['cashflow.config'].process_records(invoice_lines, 'write')

    # Payments whose journal entry lines were reconciled (e.g. with a bank
    # statement line) are not written to: reprocess them so the forecast of a
    # matched payment drops out.
    payments = lines.move_id.origin_payment_id
    if payments:
        env['cashflow.config'].process_records(payments, 'write')
            '''

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
        'filter_domain': "[('state', 'in', ('in_process', 'paid')), ('is_matched', '=', False), ('move_id', '!=', False)]",
    },
    'cashflow_config_payment_amount': {
        'python_code': "abs(record.amount_company_currency_signed)",
    },
    'cashflow_config_payment_currency': {
        'python_code': "record.company_id.currency_id.id",
    },
    'cashflow_config_reconcile': {
        'action_code': RECONCILE_ACTION_CODE,
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
