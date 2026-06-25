from odoo import models, fields, api


class CashflowCategory(models.Model):
    _name = 'cashflow.category'
    _description = 'Cashflow Category'
    _parent_store = True
    _parent_name = 'parent_id'
    _order = 'sequence, complete_name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        help='Technical code used for import/export and to reference this '
             'category from cashflow configuration classifiers.',
    )
    complete_name = fields.Char(
        string='Complete Name',
        compute='_compute_complete_name',
        recursive=True,
        store=True,
    )
    parent_id = fields.Many2one(
        'cashflow.category',
        string='Parent Category',
        ondelete='cascade',
        index=True,
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        'cashflow.category',
        'parent_id',
        string='Sub-categories',
    )
    color = fields.Integer(string='Color')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
        help='Leave empty to share the category across all companies.',
    )

    _sql_constraints = [
        (
            'code_company_uniq',
            'unique(code, company_id)',
            'The category code must be unique per company.',
        ),
    ]

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = '%s / %s' % (
                    category.parent_id.complete_name,
                    category.name,
                )
            else:
                category.complete_name = category.name

    # Recursion is prevented by Odoo's _parent_store machinery, which raises a
    # UserError on cycles during flush.

    @api.model
    def _resolve_code(self, code, company):
        """Return the category matching the given code for the company.

        Falls back to a company-shared category (company_id not set) when no
        company-specific match exists. Returns an empty recordset if nothing
        matches, so callers can log a warning and leave category_id unset.
        """
        if not code:
            return self.browse()
        company_ids = [company.id, False] if company else [False]
        return self.search(
            [('code', '=', code), ('company_id', 'in', company_ids)],
            order='company_id desc',
            limit=1,
        )
