"""Backfill the base scenario on configurations existing before 3.0.0.

The default on ``cashflow.config.scenario_ids`` only applies to newly created
records, and ``post_init_hook`` runs on install only. On upgrade we therefore
attach the base scenario here so existing configurations (and their entries)
keep showing up under the base-scenario filter of the analysis.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    base = env.ref('dub_cashflow.cashflow_scenario_base', raise_if_not_found=False)
    if not base:
        return
    configs = env['cashflow.config'].with_context(active_test=False).search([
        ('scenario_ids', '=', False),
    ])
    if configs:
        configs.write({'scenario_ids': [(4, base.id)]})
        _logger.info("Backfilled base scenario on %s configuration(s)", len(configs))
