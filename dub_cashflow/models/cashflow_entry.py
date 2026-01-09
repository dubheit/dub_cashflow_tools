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
    source_type = fields.Selection(
        selection=[
            ('auto', 'Automatic'),
            ('manual', 'Manual'),
            ('recurring', 'Recurring'),
        ],
        string='Source Type',
        default='auto',
        help='How this entry was created:\n'
             '- Automatic: Generated from invoices, payments, etc.\n'
             '- Manual: Created manually by user\n'
             '- Recurring: Generated from recurring template',
    )
    recurring_id = fields.Many2one(
        'cashflow.recurring',
        string='Recurring Template',
        ondelete='set null',
        index=True,
    )
    match_id = fields.Many2one(
        'cashflow.entry.match',
        string='Pending Match',
        ondelete='set null',
        index=True,
    )
    has_pending_match = fields.Boolean(
        compute='_compute_has_pending_match',
        string='Has Pending Match',
        store=True,
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

    @api.depends('match_id', 'match_id.state')
    def _compute_has_pending_match(self):
        for entry in self:
            entry.has_pending_match = entry.match_id and entry.match_id.state == 'pending'

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
