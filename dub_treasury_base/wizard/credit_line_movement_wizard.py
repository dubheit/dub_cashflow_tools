from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CreditLineMovementWizard(models.TransientModel):
    _name = 'credit.line.movement.wizard'
    _description = 'Credit Line Movement Wizard'

    credit_line_id = fields.Many2one(
        'treasury.credit.line',
        string='Credit Line',
        required=True,
        default=lambda self: self.env.context.get('active_id'),
    )
    company_id = fields.Many2one(
        related='credit_line_id.company_id',
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='credit_line_id.currency_id',
        readonly=True,
    )
    available_amount = fields.Monetary(
        related='credit_line_id.available_amount',
        readonly=True,
    )
    used_amount = fields.Monetary(
        related='credit_line_id.used_amount',
        readonly=True,
    )

    movement_type = fields.Selection(
        selection=[
            ('utilization', 'Utilization (Drawing)'),
            ('repayment', 'Repayment'),
            ('interest', 'Interest Charge'),
        ],
        string='Movement Type',
        required=True,
        default='utilization',
    )
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        required=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
    )
    memo = fields.Char(
        string='Memo',
        help='Description for the journal entry',
    )
    post_entry = fields.Boolean(
        string='Post Entry',
        default=False,
        help='Automatically post the journal entry after creation',
    )

    @api.constrains('amount')
    def _check_amount(self):
        for wizard in self:
            if wizard.amount <= 0:
                raise ValidationError(_('Amount must be positive.'))

    @api.onchange('movement_type')
    def _onchange_movement_type(self):
        if self.movement_type == 'utilization':
            self.amount = min(self.available_amount, 0) or 0
        elif self.movement_type == 'repayment':
            self.amount = self.used_amount or 0

    def action_confirm(self):
        """Create the journal entry for the movement."""
        self.ensure_one()
        credit_line = self.credit_line_id

        # Validate
        if self.movement_type == 'utilization':
            if self.amount > credit_line.available_amount:
                raise ValidationError(
                    _('Amount (%(amount)s) exceeds available credit (%(available)s).',
                      amount=self.amount,
                      available=credit_line.available_amount)
                )
        elif self.movement_type == 'repayment':
            if self.amount > credit_line.used_amount:
                raise ValidationError(
                    _('Amount (%(amount)s) exceeds used amount (%(used)s).',
                      amount=self.amount,
                      used=credit_line.used_amount)
                )

        # Prepare move values
        if self.movement_type == 'utilization':
            move_vals = credit_line._prepare_utilization_move_vals(
                self.amount, self.memo
            )
        elif self.movement_type == 'repayment':
            move_vals = credit_line._prepare_repayment_move_vals(
                self.amount, self.memo
            )
        else:  # interest
            move_vals = credit_line._prepare_interest_move_vals(
                self.amount, self.memo
            )

        # Override date if specified
        move_vals['date'] = self.date

        # Create the move
        move = self.env['account.move'].create(move_vals)

        # Post if requested
        if self.post_entry:
            move.action_post()

        # Update manual used amount for credit lines with manual tracking
        if not credit_line.auto_compute_usage:
            if self.movement_type == 'utilization':
                credit_line.manual_used_amount += self.amount
            elif self.movement_type == 'repayment':
                credit_line.manual_used_amount -= self.amount

        # Return action to view the created entry
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }
