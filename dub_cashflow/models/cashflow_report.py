from odoo import models, fields, tools


class CashflowReport(models.Model):
    _name = 'cashflow.report'
    _description = 'Cashflow Report'
    _auto = False
    _order = 'date'

    date = fields.Date(string='Date', readonly=True)
    month = fields.Char(string='Month', readonly=True)
    cash_in = fields.Float(string='Cash In', readonly=True)
    cash_out = fields.Float(string='Cash Out', readonly=True)
    net = fields.Float(string='Net', readonly=True)
    running_balance = fields.Float(string='Running Balance', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    journal_id = fields.Many2one('account.journal', string='Bank', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    entry_type = fields.Selection([
        ('forecast', 'Forecast'),
        ('actual', 'Actual'),
    ], string='Entry Type', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH monthly_data AS (
                    SELECT
                        DATE_TRUNC('month', ci.date)::date AS date,
                        TO_CHAR(ci.date, 'YYYY-MM') AS month,
                        COALESCE(SUM(ci.amount_in), 0) AS cash_in,
                        COALESCE(SUM(ci.amount_out), 0) AS cash_out,
                        COALESCE(SUM(ci.amount_signed), 0) AS net,
                        ci.currency_id,
                        ci.journal_id,
                        ci.entry_type,
                        ci.state
                    FROM cashflow_item ci
                    GROUP BY
                        DATE_TRUNC('month', ci.date),
                        TO_CHAR(ci.date, 'YYYY-MM'),
                        ci.currency_id,
                        ci.journal_id,
                        ci.entry_type,
                        ci.state
                )
                SELECT
                    ROW_NUMBER() OVER (ORDER BY md.date, md.currency_id, md.journal_id) AS id,
                    md.date,
                    md.month,
                    md.cash_in,
                    md.cash_out,
                    md.net,
                    SUM(md.net) OVER (
                        PARTITION BY md.currency_id
                        ORDER BY md.date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS running_balance,
                    md.currency_id,
                    md.journal_id,
                    NULL::integer AS partner_id,
                    md.entry_type,
                    md.state
                FROM monthly_data md
            )
        """ % self._table)
