from odoo import models, fields, api


class CashflowEntry(models.Model):
    _name = 'cashflow.entry'
    _description = 'Cashflow Entry'
    _order = 'date desc, id desc'

    name = fields.Char(required=True)
    date = fields.Date(required=True, default=fields.Date.today)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
    )
    entry_type = fields.Selection(
        selection=[
            ('forecast', 'Forecast'),
            ('actual', 'Actual'),
        ],
        string='Entry Type',
        default='forecast',
        required=True,
        help='Forecast: expected cashflow (invoices, planned payments)\n'
             'Actual: real cashflow (bank transactions, confirmed payments)',
    )
    reference = fields.Char()
    category_id = fields.Many2one(
        'cashflow.category',
        string='Category',
        index=True,
        ondelete='set null',
        help='Cashflow category used to group flows by nature for pivots and '
             'dashboards.',
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Bank',
        domain="[('type', '=', 'bank')]",
        help='Bank journal for this cashflow entry',
    )
    model = fields.Char(string='Source Model Name', index=True)
    model_id = fields.Many2one(
        'ir.model',
        string='Source Model',
        compute='_compute_model_id',
        store=True,
        index=True,
    )
    model_label = fields.Char(
        string='Source',
        related='model_id.name',
        store=True,
    )
    res_id = fields.Integer(string='Source Record ID', index=True)
    config_id = fields.Many2one(
        'cashflow.config',
        string='Configuration',
        ondelete='cascade',
        index=True,
    )
    recurring_id = fields.Many2one(
        'cashflow.recurring',
        string='Recurring Source',
        ondelete='cascade',
        index=True,
        help='Recurring cashflow definition that generated this entry.',
    )
    scenario_ids = fields.Many2many(
        'cashflow.scenario',
        'cashflow_entry_scenario_rel',
        'entry_id',
        'scenario_id',
        string='Scenarios',
        compute='_compute_scenario_ids',
        store=True,
        help='Scenarios this entry belongs to, inherited from its '
             'configuration or recurring source.',
    )
    item_ids = fields.One2many('cashflow.item', 'entry_id', string='Cashflow Items')
    total_in = fields.Monetary(
        compute='_compute_totals',
        currency_field='currency_id',
        string='Total In',
    )
    total_out = fields.Monetary(
        compute='_compute_totals',
        currency_field='currency_id',
        string='Total Out',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    @api.depends('config_id.scenario_ids', 'recurring_id.scenario_ids')
    def _compute_scenario_ids(self):
        for entry in self:
            entry.scenario_ids = entry.config_id.scenario_ids | entry.recurring_id.scenario_ids

    @api.depends('model')
    def _compute_model_id(self):
        IrModel = self.env['ir.model']
        for entry in self:
            if entry.model:
                entry.model_id = IrModel.sudo().search([('model', '=', entry.model)], limit=1)
            else:
                entry.model_id = False

    @api.depends('item_ids.amount', 'item_ids.type')
    def _compute_totals(self):
        for entry in self:
            entry.total_in = sum(
                item.amount for item in entry.item_ids if item.type == 'in'
            )
            entry.total_out = sum(
                item.amount for item in entry.item_ids if item.type == 'out'
            )

    def action_open_source_record(self):
        """Open the source record linked to this cashflow entry."""
        self.ensure_one()
        if not self.model or not self.res_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }
