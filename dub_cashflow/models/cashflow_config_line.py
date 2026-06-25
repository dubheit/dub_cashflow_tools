import logging
from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class CashflowConfigLine(models.Model):
    _name = 'cashflow.config.line'
    _description = 'Cashflow Configuration Line'
    _order = 'sequence, id'

    config_id = fields.Many2one(
        'cashflow.config',
        string='Configuration',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    cashflow_field = fields.Selection(
        selection=[
            ('date', 'Date'),
            ('amount', 'Amount'),
            ('type', 'Type (in/out)'),
            ('currency_id', 'Currency'),
            ('partner_id', 'Partner'),
            ('description', 'Description'),
            ('state', 'Status'),
            ('entry_type', 'Entry Type (forecast/actual)'),
            ('journal_id', 'Bank'),
            ('category_code', 'Category (by code)'),
        ],
        string='Cashflow Field',
        required=True,
        help="Target cashflow field to fill. 'Category (by code)' is special: "
             "the evaluated value is treated as a cashflow.category code and "
             "resolved to the matching category (a warning is logged and the "
             "category is left empty when no category matches).",
    )
    source_type = fields.Selection(
        selection=[
            ('field', 'Field'),
            ('python_code', 'Python Code'),
            ('fixed_value', 'Fixed Value'),
        ],
        string='Source Type',
        required=True,
        default='field',
    )
    source_field_id = fields.Many2one(
        'ir.model.fields',
        string='Source Field',
        domain="[('model_id', '=', parent.model_id)]",
    )
    python_code = fields.Text(
        string='Python Code',
        help="Python expression to evaluate. Use 'record' to access the source record.\n"
             "Examples:\n"
             "  - record.date_maturity or record.date\n"
             "  - abs(record.balance)\n"
             "  - 'in' if record.balance > 0 else 'out'\n"
             "  - record.partner_id.id",
    )
    fixed_value = fields.Char(string='Fixed Value')

    @api.onchange('source_type')
    def _onchange_source_type(self):
        if self.source_type == 'field':
            self.python_code = False
            self.fixed_value = False
        elif self.source_type == 'python_code':
            self.source_field_id = False
            self.fixed_value = False
        elif self.source_type == 'fixed_value':
            self.source_field_id = False
            self.python_code = False

    def _evaluate(self, record, eval_context=None):
        """Evaluate this line's mapping for the given record."""
        self.ensure_one()

        if self.source_type == 'field':
            if not self.source_field_id:
                return None
            field_name = self.source_field_id.name
            value = record[field_name]
            # Handle relational fields - return id
            if hasattr(value, 'id'):
                return value.id
            return value

        elif self.source_type == 'python_code':
            if not self.python_code:
                return None
            context = eval_context or {}
            context['record'] = record
            return safe_eval(self.python_code, context)

        elif self.source_type == 'fixed_value':
            if not self.fixed_value:
                return None
            # Try to convert to appropriate type
            cashflow_field = self.cashflow_field
            if cashflow_field in ('amount',):
                return float(self.fixed_value)
            elif cashflow_field in ('currency_id', 'partner_id', 'journal_id'):
                return int(self.fixed_value)
            return self.fixed_value

        return None
