# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.addons import decimal_precision as dp


class JobCostSheet(models.Model):
    _inherit = "job.cost.sheet"

    cost_type = fields.Selection(
        [('spare_parts', 'Spare Parts'),
         ('discount', 'Discount'),
         ('service', 'Service'),
         ('consumables', 'Consumables'),
         ('labour', 'Labour'),
         ('sublet', 'Sublet'),
         ('tyre', 'Tyre'),
         ('scrap', 'Scrap'),
         ('paint', 'Paint'),
         ],
        string='Type',
        default='spare_parts',
    )
    parts_type = fields.Selection(
        [('original', 'Original'),
         ('duplicate', 'Thijari(Duplicate)'),
         ('used', 'Used'),
         ],
        string='Parts Type',
        default='original',
    )
    part_no = fields.Char(string="Part No.")
    coupon_service_no = fields.Integer(
        string='Coupon Service No.',
        readonly=True
    )
    invoice_checkbox = fields.Boolean(default=True)

    # 1. Custom Price: Defaults to product unit price and remains manually editable
    custom_price = fields.Float(
        string='Custom Price',
        compute='_compute_custom_price',
        store=True,
        readonly=False,
        help='Base price before markup. Defaults to standard unit price but can be manually edited.',
    )

    # 2. Markup percentage fetched from customer contact
    price_factor = fields.Float(
        string='Markup (%)',
        compute='_compute_markup_prices',
        store=True,
        readonly=False,
        help='Markup percentage retrieved from customer contact',
    )
    vendor_id = fields.Many2one('res.partner', string="Vendor")

    # Field to track if this line has already been converted to a PO
    is_po_created = fields.Boolean(
        string='PO Created', 
        default=False, 
        copy=False, 
        readonly=True
    )

    # 3. Readonly computed field for price after markup (applies to hidden price_unit)
    # price_after_markup = fields.Float(
    #     string='Sale Price',
    #     compute='_compute_markup_prices',
    #     store=True,
    #     readonly=True,
    #     help='Final sale price after applying percentage markup.',
    # )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        rtn = super(JobCostSheet, self)._onchange_product_id()
        if self.product_id:
            self.invoice_line_tax_ids = self.product_id.taxes_id._filter_taxes_by_company(self.task_id.company_id)
            self.cost_type = self.product_id.cost_type
            self.parts_type = self.product_id.parts_type
            self.part_no = self.product_id.barcode
        return rtn

    @api.onchange('part_no')
    def _onchange_part_no(self):
        if self.part_no:
            product_id = self.env['product.product'].search([('barcode', '=', self.part_no)], limit=1)
            if product_id:
                self.product_id = product_id.id

    @api.depends('product_id')
    def _compute_custom_price(self):
        """Sets custom_price default to whatever standard unit price the product takes."""
        for line in self:
            if line.product_id:
                # Fetch standard computed list price / pricelist value
                line.custom_price = line.product_id.lst_price

    @api.depends('custom_price', 'cost_type', 'task_id.partner_id')
    def _compute_markup_prices(self):
        for line in self:
            partner = line.task_id.partner_id
            raw_markup = 0.0

            if partner:
                if line.cost_type == 'spare_parts':
                    raw_markup = partner.markup_spare_parts
                elif line.cost_type == 'labour':
                    raw_markup = partner.markup_labor
                elif line.cost_type == 'sublet':
                    raw_markup = partner.markup_sublet

            # --- PERCENTAGE CONVERSION LOGIC ---
            # If the value entered on res.partner is a whole number (e.g. 10 for 10%),
            # convert it to decimal ratio (0.10) for widget="percentage" and math.
            if raw_markup > 1.0:
                markup_ratio = raw_markup / 100.0
            else:
                markup_ratio = raw_markup

            # Assign ratio to price_factor (0.10 renders as 10% in UI)
            line.price_factor = markup_ratio

            # Calculate Sale Price: Custom Price + (Custom Price * 10%)
            base = line.custom_price or 0.0
            final_price = base * (1.0 + markup_ratio)

            # line.price_after_markup = final_price
            line.price_unit = final_price