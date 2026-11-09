from odoo import SUPERUSER_ID, api

OLD_DOMAIN = "[('type', '=', 'opportunity'), ('probability', '>', 0)]"
NEW_DOMAIN = "[('type', '=', 'opportunity'), ('probability', '>', 0), ('order_ids', 'not any', [('state', '!=', 'cancel')])]"


def migrate(cr, version):
    """The config filter now drops an opportunity with a live quotation: the hook only asks
    for a recomputation instead of deleting the entries itself. The record is
    noupdate, so the filter is updated here, and only when still the default.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    config = env.ref("dub_cashflow_crm.cashflow_config_crm_opportunity", raise_if_not_found=False)
    if config and config.filter_domain == OLD_DOMAIN:
        config.filter_domain = NEW_DOMAIN
