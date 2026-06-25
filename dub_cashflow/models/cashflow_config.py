import logging
from datetime import date, time, timedelta
from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval, datetime as safe_datetime

_logger = logging.getLogger(__name__)


class CashflowConfig(models.Model):
    _name = 'cashflow.config'
    _description = 'Cashflow Configuration'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    scenario_ids = fields.Many2many(
        'cashflow.scenario',
        'cashflow_config_scenario_rel',
        'config_id',
        'scenario_id',
        string='Scenarios',
        default=lambda self: self._default_scenario_ids(),
        help='Scenarios this configuration contributes to. A configuration '
             'can belong to several scenarios (e.g. both Base and Pessimistic).',
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain=[('transient', '=', False)],
    )
    model_name = fields.Char(string='Model Name', related='model_id.model', store=True, readonly=True)
    filter_domain = fields.Char(
        string='Filter Domain',
        default='[]',
        help='Domain to filter which records should generate cashflow entries',
    )
    line_ids = fields.One2many(
        'cashflow.config.line',
        'config_id',
        string='Field Mappings',
    )

    # Trigger configuration
    trigger_on_create = fields.Boolean(
        string='Trigger on Create',
        default=True,
        help='Generate cashflow when a record is created',
    )
    trigger_on_write = fields.Boolean(
        string='Trigger on Write',
        default=True,
        help='Update cashflow when a record is modified',
    )
    trigger_on_unlink = fields.Boolean(
        string='Trigger on Unlink',
        default=True,
        help='Delete cashflow when a record is deleted',
    )
    trigger_on_copy = fields.Boolean(
        string='Trigger on Copy',
        default=False,
        help='Generate cashflow when a record is duplicated',
    )

    # Entry name template
    name_code = fields.Text(
        string='Entry Name Code',
        default="record.display_name",
        help="""Python expression to generate the entry name.
Available variables: record, env, config
Examples:
  - record.display_name (default)
  - record.move_id.name or record.name
  - f"Invoice {record.move_id.name}"
""",
    )

    # Custom action code
    action_code = fields.Text(
        string='Custom Action Code',
        help="""Optional Python code to execute instead of default behavior.
Available variables:
  - record: the source record being processed
  - records: all records being processed (recordset)
  - operation: the operation type ('create', 'write', 'unlink', 'copy', 'post', 'draft', 'cancel')
  - config: this configuration record
  - env: the Odoo environment
  - generate_cashflow(): call to execute default generate behavior
  - delete_cashflow(): call to execute default delete behavior

Example:
  if operation == 'unlink':
      delete_cashflow()
  elif operation in ('create', 'write', 'post'):
      generate_cashflow()
""",
    )

    # Payment terms support
    use_payment_terms = fields.Boolean(
        string='Use Payment Terms',
        default=False,
        help='Generate multiple cashflow items based on payment terms installments',
    )
    payment_term_field = fields.Char(
        string='Payment Term Field',
        default='payment_term_id',
        help='Field name containing the payment term (e.g., payment_term_id)',
    )
    amount_field = fields.Char(
        string='Amount Field',
        default='amount_total',
        help='Field name containing the total amount to split (e.g., amount_total, amount_residual)',
    )
    date_field = fields.Char(
        string='Date Field',
        default='date',
        help='Field name containing the base date for payment term calculation (e.g., date, date_order, invoice_date)',
    )

    @api.model
    def _default_scenario_ids(self):
        """Default a new configuration to the base scenario, if it exists."""
        base = self.env.ref('dub_cashflow.cashflow_scenario_base', raise_if_not_found=False)
        return [(4, base.id)] if base else False

    @api.model
    def get_configs_for_model(self, model_name):
        """Get all active configurations for a given model."""
        return self.search([
            ('model_name', '=', model_name),
            ('active', '=', True),
        ])

    def _evaluate_domain(self, record):
        """Check if record matches the filter domain."""
        self.ensure_one()
        if not self.filter_domain or self.filter_domain == '[]':
            return True
        domain = safe_eval(self.filter_domain)
        return record.filtered_domain(domain)

    # Fields that belong to cashflow.entry (not cashflow.item)
    ENTRY_FIELDS = {'state', 'entry_type', 'journal_id'}

    def _get_eval_context(self, record):
        """Get evaluation context for Python expressions."""
        return {
            'record': record,
            'env': self.env,
            'datetime': safe_datetime,
            'date': date,
            'time': time,
            'timedelta': timedelta,
            'abs': abs,
            'max': max,
            'min': min,
            'sum': sum,
            'len': len,
            'True': True,
            'False': False,
        }

    def _prepare_cashflow_vals(self, record):
        """Prepare cashflow entry and item values from a source record using field mappings."""
        self.ensure_one()
        entry_vals = {}
        item_vals = {}
        eval_context = self._get_eval_context(record)

        for line in self.line_ids:
            try:
                value = line._evaluate(record, eval_context)
                if value is None:
                    continue
                if line.cashflow_field == 'category_code':
                    # Special target: resolve the evaluated code to a category.
                    entry_vals['category_id'] = self._resolve_category(record, value)
                elif line.cashflow_field in self.ENTRY_FIELDS:
                    entry_vals[line.cashflow_field] = value
                else:
                    item_vals[line.cashflow_field] = value
            except Exception as e:
                _logger.warning(
                    "Error evaluating field %s for record %s: %s",
                    line.cashflow_field, record, e
                )

        return entry_vals, item_vals

    def _resolve_category(self, record, code):
        """Resolve a classifier code to a cashflow.category id.

        Returns False (and logs a warning) when the code does not match any
        category, so a misconfigured classifier never raises nor creates
        categories on the fly (R1.5).
        """
        self.ensure_one()
        company = self.env.company
        if 'company_id' in record._fields and record.company_id:
            company = record.company_id[:1]
        category = self.env['cashflow.category']._resolve_code(str(code), company)
        if not category:
            _logger.warning(
                "CASHFLOW: category code %r (config %s, record %s) does not match "
                "any cashflow.category; leaving category empty.",
                code, self.name, record,
            )
            return False
        return category.id

    def generate_cashflow(self, records):
        """Generate cashflow entries for the given records."""
        self.ensure_one()
        CashflowEntry = self.env['cashflow.entry']
        CashflowItem = self.env['cashflow.item']

        for record in records:
            if not self._evaluate_domain(record):
                # If record doesn't match domain anymore, delete existing entries
                _logger.info("CASHFLOW: Record %s does not match domain, deleting cashflow", record.id)
                self.delete_cashflow(record)
                continue

            # Prepare values
            entry_vals, item_vals = self._prepare_cashflow_vals(record)

            # Find or create cashflow entry for this record
            entry = CashflowEntry.search([
                ('model', '=', self.model_name),
                ('res_id', '=', record.id),
                ('config_id', '=', self.id),
            ], limit=1)

            # Generate entry name
            eval_context = self._get_eval_context(record)
            eval_context['config'] = self
            try:
                entry_name = safe_eval(self.name_code or 'record.display_name', eval_context)
            except Exception as e:
                _logger.warning("Error evaluating name_code for %s: %s", record, e)
                entry_name = record.display_name

            # Base entry values
            base_entry_vals = {
                'name': entry_name,
                'reference': getattr(record, 'name', '') or str(record.id),
            }
            base_entry_vals.update(entry_vals)

            if not entry:
                base_entry_vals.update({
                    'model': self.model_name,
                    'res_id': record.id,
                    'config_id': self.id,
                    'date': fields.Date.today(),
                })
                entry = CashflowEntry.create(base_entry_vals)
            else:
                entry.write(base_entry_vals)

            # Remove existing items and recreate
            entry.item_ids.unlink()

            # Create cashflow items
            if item_vals:
                # Check if amount is 0 or very small (fully paid invoice)
                amount = item_vals.get('amount', 0)
                if amount is not None and abs(float(amount)) < 0.01:
                    # Delete entry for zero-amount items (e.g., fully paid invoices)
                    _logger.info("CASHFLOW: Deleting entry for record %s with zero amount", record.id)
                    entry.unlink()
                    continue

                if self.use_payment_terms:
                    # Generate multiple items based on payment terms
                    items_data = self._compute_payment_term_items(record, item_vals)
                    for item_data in items_data:
                        item_data['entry_id'] = entry.id
                        CashflowItem.create(item_data)
                else:
                    # Single item
                    item_vals['entry_id'] = entry.id
                    CashflowItem.create(item_vals)

        return True

    def _compute_payment_term_items(self, record, base_item_vals):
        """Compute multiple cashflow items based on payment terms.

        Returns a list of item_vals dictionaries, one per installment.
        """
        self.ensure_one()
        items = []

        # Get payment term
        payment_term = None
        if self.payment_term_field:
            try:
                payment_term = record
                for field_part in self.payment_term_field.split('.'):
                    payment_term = getattr(payment_term, field_part, None)
                    if payment_term is None:
                        break
            except Exception:
                payment_term = None

        # Get total amount
        total_amount = base_item_vals.get('amount', 0)
        if not total_amount and self.amount_field:
            try:
                total_amount = record
                for field_part in self.amount_field.split('.'):
                    total_amount = getattr(total_amount, field_part, 0)
            except Exception:
                total_amount = 0
        total_amount = abs(float(total_amount or 0))

        # Get base date
        base_date = base_item_vals.get('date') or fields.Date.today()
        if self.date_field:
            try:
                base_date = record
                for field_part in self.date_field.split('.'):
                    base_date = getattr(base_date, field_part, None)
                if not base_date:
                    base_date = fields.Date.today()
            except Exception:
                base_date = fields.Date.today()

        if payment_term and hasattr(payment_term, 'line_ids') and payment_term.line_ids:
            # Use payment term to compute installments
            # Odoo's payment term compute method
            try:
                result = payment_term._compute_terms(
                    date_ref=base_date,
                    currency=self.env.company.currency_id,
                    company=self.env.company,
                    tax_amount=0,
                    tax_amount_currency=0,
                    untaxed_amount=total_amount,
                    untaxed_amount_currency=total_amount,
                    sign=1,
                )
                # Result is a dict with 'line_ids' containing the payment lines
                term_lines = result.get('line_ids', []) if isinstance(result, dict) else result
                for term_line in term_lines:
                    item_data = dict(base_item_vals)
                    item_data['date'] = term_line.get('date')
                    item_data['amount'] = abs(term_line.get('foreign_amount', 0) or term_line.get('company_amount', 0))
                    if item_data['amount'] > 0:
                        items.append(item_data)
            except Exception as e:
                _logger.warning("Error computing payment terms for %s: %s", record, e)
                # Fallback to single item
                items.append(base_item_vals)
        else:
            # No payment term, single item
            items.append(base_item_vals)

        return items

    def delete_cashflow(self, records):
        """Delete cashflow entries for the given records."""
        self.ensure_one()
        _logger.info("CASHFLOW: delete_cashflow() for model=%s, res_ids=%s, config_id=%s", self.model_name, records.ids, self.id)
        entries = self.env['cashflow.entry'].search([
            ('model', '=', self.model_name),
            ('res_id', 'in', records.ids),
            ('config_id', '=', self.id),
        ])
        _logger.info("CASHFLOW: Found %s entries to delete: %s", len(entries), entries.ids)
        entries.unlink()
        return True

    def _should_trigger(self, operation):
        """Check if this configuration should trigger for the given operation."""
        self.ensure_one()
        trigger_map = {
            'create': self.trigger_on_create,
            'write': self.trigger_on_write,
            'unlink': self.trigger_on_unlink,
            'copy': self.trigger_on_copy,
            # State change operations always trigger if write is enabled
            'post': self.trigger_on_write,
            'confirm': self.trigger_on_write,  # For sale.order confirmation
            'draft': self.trigger_on_write,
            'cancel': self.trigger_on_write,
        }
        return trigger_map.get(operation, True)

    def _execute_action(self, records, operation):
        """Execute the configured action for the given records and operation."""
        self.ensure_one()
        _logger.info("CASHFLOW: _execute_action() config=%s, operation=%s, records=%s", self.name, operation, records.ids)

        if self.action_code:
            _logger.info("CASHFLOW: Executing action_code for config %s", self.name)
            # Execute custom action code
            def generate_cashflow():
                self.generate_cashflow(records)

            def delete_cashflow():
                self.delete_cashflow(records)

            eval_context = {
                'records': records,
                'record': records[0] if len(records) == 1 else records,
                'operation': operation,
                'config': self,
                'env': self.env,
                'generate_cashflow': generate_cashflow,
                'delete_cashflow': delete_cashflow,
                'datetime': safe_datetime,
                'date': date,
                'time': time,
                'timedelta': timedelta,
                'abs': abs,
                'True': True,
                'False': False,
                '_logger': _logger,  # Pre-configured logger for action_code logging
            }
            try:
                safe_eval(self.action_code, eval_context, mode='exec', nocopy=True)
                _logger.info("CASHFLOW: action_code executed successfully for config %s", self.name)
            except Exception as e:
                _logger.error(
                    "Error executing action code for config %s on %s: %s",
                    self.name, records, e
                )
        else:
            # Default behavior
            if operation == 'unlink':
                self.delete_cashflow(records)
            else:
                self.generate_cashflow(records)

    @api.model
    def process_records(self, records, operation='write'):
        """Process records based on cashflow configurations.

        This method should be called from model overrides.
        """
        if not records:
            return

        model_name = records._name
        configs = self.get_configs_for_model(model_name)

        for config in configs:
            try:
                if not config._should_trigger(operation):
                    continue
                config._execute_action(records, operation)
            except Exception as e:
                _logger.error(
                    "Error processing cashflow for %s on %s: %s",
                    operation, records, e
                )
