"""Pre-migration script for module rename."""
import logging

_logger = logging.getLogger(__name__)

OLD_MODULE = 'db_cashflow_sale'
NEW_MODULE = 'dub_cashflow_sale'


def migrate(cr, version):
    """Pre-migration: rename old module to new module in database."""
    if not version:
        return

    _logger.info(f"Pre-migrating {OLD_MODULE} -> {NEW_MODULE}")

    # Update module references in ir_model_data
    cr.execute(f"UPDATE ir_model_data SET module = '{NEW_MODULE}' WHERE module = '{OLD_MODULE}'")

    # Update module name in ir_module_module
    cr.execute(f"UPDATE ir_module_module SET name = '{NEW_MODULE}' WHERE name = '{OLD_MODULE}'")

    _logger.info(f"Pre-migration {OLD_MODULE} -> {NEW_MODULE} completed")
