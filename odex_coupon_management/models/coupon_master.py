# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
class Product(models.Model):
    _inherit = 'product.template'

    is_coupon = fields.Boolean()
class CouponMaster(models.Model):
    _name = 'coupon.master'
    _description = 'Coupon Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'id desc'

    name = fields.Char(string='Coupon Name', required=True, tracking=True)
    code = fields.Char(
        string='Code', readonly=True, copy=False,
        default='New', tracking=True,
    )
    coupon_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom'),
    ], string='Coupon Type', required=True, default='monthly', tracking=True)

    duration_days = fields.Integer(
        string='Duration (Days)', default=30, tracking=True)
    amount = fields.Monetary(
        string='Amount', currency_field='currency_id',
        required=True, tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id,
    )
    description = fields.Text(string='Description', tracking=True)
    auto_expiry = fields.Boolean(
        string='Auto Expiry', default=True,
        help='Auto set expiry date based on duration',
    )
    active = fields.Boolean(string='Active', default=True, tracking=True)

    # One2many service lines — mirrors the screenshot table (#, Service, Description, Unit Price, Type)
    allowed_service_line_ids = fields.One2many(
        'coupon.master.service.line', 'coupon_master_id',
        string='Allowed Services',
    )
    # Convenience Many2many for use in customer coupon (read-only mirror)
    allowed_service_ids = fields.Many2many(
        'product.product',
        'coupon_master_service_rel',
        'coupon_id', 'product_id',
        string='Allowed Services (M2M)',
        compute='_compute_allowed_service_ids',
        store=True,
    )
    notes = fields.Html(string='Notes ')
    allowed_services_count = fields.Integer(
        string='Allowed Services Count',
        store=True,
    )

    # ── Computed ──────────────────────────────────────────────────────────

    @api.depends('allowed_service_line_ids.product_id')
    def _compute_allowed_service_ids(self):
        for rec in self:
            rec.allowed_service_ids = rec.allowed_service_line_ids.mapped('product_id')



    # ── Onchange ──────────────────────────────────────────────────────────

    @api.onchange('coupon_type')
    def _onchange_coupon_type(self):
        mapping = {'monthly': 30, 'quarterly': 90, 'yearly': 365}
        if self.coupon_type in mapping:
            self.duration_days = mapping[self.coupon_type]

    # ── CRUD ──────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = (
                    self.env['ir.sequence'].next_by_code('coupon.master') or 'New'
                )
        return super().create(vals_list)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                '[%s] %s' % (rec.code, rec.name)
                if rec.code and rec.code != 'New'
                else rec.name
            )


class CouponMasterServiceLine(models.Model):
    _name = 'coupon.master.service.line'
    _description = 'Coupon Master Service Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='#', default=10)
    coupon_master_id = fields.Many2one(
        'coupon.master', string='Coupon Master', ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product', string='Service', required=True,
        domain=[('type', 'in', ['service', 'consu'])],
    )
    description = fields.Char(
        string='Description',
        compute='_compute_description', store=True, readonly=False,
    )
    unit_price = fields.Float(
        string='Unit Price',
        compute='_compute_unit_price', store=True, readonly=False,
        digits='Product Price',
    )
    product_type = fields.Selection(
        related='product_id.type', string='Type',
    )

    @api.depends('product_id')
    def _compute_description(self):
        for line in self:
            line.description = (
                line.product_id.description_sale or line.product_id.name
                if line.product_id else ''
            )

    @api.depends('product_id')
    def _compute_unit_price(self):
        for line in self:
            line.unit_price = line.product_id.lst_price if line.product_id else 0.0
