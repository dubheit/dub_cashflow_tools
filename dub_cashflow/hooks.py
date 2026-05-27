"""Installation hooks for module migration."""
import logging

_logger = logging.getLogger(__name__)

OLD_MODULE = 'db_cashflow'
NEW_MODULE = 'dub_cashflow'


def pre_init_hook(env):
    """Migrate from old module if it exists."""
    cr = env.cr

    # Check if old module exists and is installed
    cr.execute(
        "SELECT id, state FROM ir_module_module WHERE name = %s",
        (OLD_MODULE,)
    )
    old_module = cr.fetchone()

    if not old_module or old_module[1] != 'installed':
        _logger.info(f"No installed {OLD_MODULE} found, skipping migration")
        return

    _logger.info(f"Migrating {OLD_MODULE} -> {NEW_MODULE}")

    # Update module references in ir_model_data
    cr.execute(
        "UPDATE ir_model_data SET module = %s WHERE module = %s",
        (NEW_MODULE, OLD_MODULE)
    )
    _logger.info(f"Updated ir_model_data: {cr.rowcount} rows")

    # Delete old module entry
    cr.execute(
        "DELETE FROM ir_module_module WHERE name = %s",
        (OLD_MODULE,)
    )
    _logger.info("Deleted old module entry")

    _logger.info(f"Migration {OLD_MODULE} -> {NEW_MODULE} completed")


def post_init_hook(env):
    """Attach the base scenario to pre-existing configurations.

    The default on ``cashflow.config.scenario_ids`` only applies to newly
    created records, so configurations already present before this upgrade
    would otherwise have no scenario and disappear from the base-scenario
    filter of the analysis. Backfill them with the base scenario.
    """
    base = env.ref('dub_cashflow.cashflow_scenario_base', raise_if_not_found=False)
    if not base:
        return
    configs = env['cashflow.config'].with_context(active_test=False).search([
        ('scenario_ids', '=', False),
    ])
    if configs:
        configs.write({'scenario_ids': [(4, base.id)]})
        _logger.info("Backfilled base scenario on %s configuration(s)", len(configs))
