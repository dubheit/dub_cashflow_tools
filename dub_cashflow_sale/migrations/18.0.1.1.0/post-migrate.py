from odoo import SUPERUSER_ID, api

OLD_DOMAIN = "[('state', 'not in', ['cancel']), ('invoice_status', '!=', 'invoiced')]"
NEW_DOMAIN = "[('state', 'not in', ['cancel']), ('invoice_status', '!=', 'invoiced'), ('invoice_ids', 'not any', [('state', '!=', 'cancel')])]"


def migrate(cr, version):
    """The config filter now drops an order with an invoice: the hook only asks
    for a recomputation instead of deleting the entries itself. The record is
    noupdate, so the filter is updated here, and only when still the default.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    config = env.ref("dub_cashflow_sale.cashflow_config_sale_order", raise_if_not_found=False)
    if config and config.filter_domain == OLD_DOMAIN:
        config.filter_domain = NEW_DOMAIN
