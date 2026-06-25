from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TreasuryAvailabilityWizard(models.TransientModel):
    _name = 'treasury.availability.wizard'
    _description = 'Credit Line Availability Wizard'

    date_from = fields.Date(
        required=True,
        default=fields.Date.context_today,
    )
    date_to = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self) + relativedelta(months=3),
    )
    granularity = fields.Selection(
        selection=[
            ('day', 'Daily'),
            ('week', 'Weekly'),
            ('month', 'Monthly'),
        ],
        required=True,
        default='day',
    )
    credit_line_ids = fields.Many2many(
        'treasury.credit.line',
        string='Credit Lines',
        help='Leave empty to include all active credit lines.',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many(
        'treasury.availability.report',
        'wizard_id',
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_to < wizard.date_from:
                raise UserError(_('End date must be on or after the start date.'))

    def _generate_dates(self):
        """Return the list of projection dates honouring the granularity."""
        self.ensure_one()
        dates = []
        current = self.date_from
        step = {
            'day': relativedelta(days=1),
            'week': relativedelta(weeks=1),
            'month': relativedelta(months=1),
        }[self.granularity]
        while current <= self.date_to:
            dates.append(current)
            current += step
        if dates and dates[-1] != self.date_to:
            dates.append(self.date_to)
        return dates

    def action_compute(self):
        self.ensure_one()
        self.line_ids.unlink()

        credit_lines = self.credit_line_ids or self.env['treasury.credit.line'].search([
            ('state', '=', 'active'),
            ('company_id', '=', self.company_id.id),
        ])
        if not credit_lines:
            raise UserError(_('No active credit lines to project.'))

        dates = self._generate_dates()
        Report = self.env['treasury.availability.report']
        rows = []
        for line in credit_lines:
            availability = line.get_available_at_dates(dates)
            for target_date, (used, available) in availability.items():
                utilization = (used / line.limit_amount * 100) if line.limit_amount else 0.0
                rows.append({
                    'wizard_id': self.id,
                    'date': target_date,
                    'credit_line_id': line.id,
                    'company_id': line.company_id.id,
                    'currency_id': line.currency_id.id,
                    'limit_amount': line.limit_amount,
                    'used_at_date': used,
                    'available_at_date': available,
                    'utilization_rate_at_date': utilization,
                })
        Report.create(rows)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Credit Line Availability'),
            'res_model': 'treasury.availability.report',
            'view_mode': 'pivot,list',
            'domain': [('wizard_id', '=', self.id)],
            'context': {
                'search_default_group_bank': 1,
                'pivot_measures': ['available_at_date', 'used_at_date', 'limit_amount'],
            },
            'target': 'current',
        }
