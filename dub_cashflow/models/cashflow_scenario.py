from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CashflowScenario(models.Model):
    _name = 'cashflow.scenario'
    _description = 'Cashflow Scenario'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color Index')
    is_default = fields.Boolean(
        string='Base Scenario',
        help='The base scenario, shown by default in the cashflow analysis. '
             'Only one scenario can be the base one.',
    )
    description = fields.Char()
    config_ids = fields.Many2many(
        'cashflow.config',
        'cashflow_config_scenario_rel',
        'scenario_id',
        'config_id',
        string='Configurations',
        help='Cashflow configurations that contribute to this scenario.',
    )
    config_count = fields.Integer(
        string='Configurations Count',
        compute='_compute_config_count',
    )

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'A scenario with this name already exists.'),
    ]

    @api.depends('config_ids')
    def _compute_config_count(self):
        for scenario in self:
            scenario.config_count = len(scenario.config_ids)

    @api.constrains('is_default', 'active')
    def _check_single_default(self):
        if self.filtered(lambda s: s.is_default and s.active):
            others = self.search([
                ('is_default', '=', True),
                ('active', '=', True),
                ('id', 'not in', self.ids),
            ])
            if others:
                raise ValidationError(
                    "Only one active scenario can be the base scenario. "
                    "Scenario '%s' is already the base one." % others[0].name
                )

    def action_open_configs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Configurations',
            'res_model': 'cashflow.config',
            'view_mode': 'list,form',
            'domain': [('scenario_ids', 'in', self.id)],
            'context': {'default_scenario_ids': [(4, self.id)]},
        }
