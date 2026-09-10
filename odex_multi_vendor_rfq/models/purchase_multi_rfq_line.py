# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PurchaseMultiRFQLine(models.Model):
    _name = 'purchase.multi.rfq.line'
    _description = 'Multi Vendor RFQ Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    rfq_id = fields.Many2one(
        'purchase.multi.rfq',
        string='Multi RFQ',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain=[('purchase_ok', '=', True)],
        change_default=True,
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        store=False,
    )
    description = fields.Text(string='Description')
    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
        digits='Product Unit of Measure',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        required=True,
    )
    uom_category_id = fields.Many2one(
        related='uom_id.category_id',
        string='UoM Category',
    )
    expected_date = fields.Date(string='Expected Date')
    company_id = fields.Many2one(
        related='rfq_id.company_id',
        store=True,
    )
    currency_id = fields.Many2one(
        related='rfq_id.currency_id',
        store=True,
    )

    # ── Award tracking (permanent — set once awarded, never cleared) ────────────
    awarded_vendor_id = fields.Many2one(
        'res.partner', string='Awarded Vendor', readonly=True, copy=False,
    )
    awarded_price = fields.Float(string='Awarded Price', readonly=True, copy=False)
    awarded_po_id = fields.Many2one(
        'purchase.order', string='Purchase Order', readonly=True, copy=False,
    )

    # ── Live recommendation (from the single shared supplier-recommendation
    # method on purchase.multi.rfq — never computed independently here) ────────
    recommended_vendor_id = fields.Many2one(
        'res.partner', string='Recommended Supplier',
        compute='_compute_recommendation', store=False,
    )
    lowest_price = fields.Float(
        string='Lowest Price', compute='_compute_recommendation', store=False,
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
    vehicle_make_id = fields.Many2one("fleet.vehicle.model.brand", string="Brand")

    @api.depends(
        'rfq_id.line_ids', 'rfq_id.vendor_ids',
        'rfq_id.generated_rfq_ids.order_line.price_unit',
        'rfq_id.generated_rfq_ids.order_line.product_id',
        'rfq_id.generated_rfq_ids.is_award_po',
    )
    def _compute_recommendation(self):
        # Group by parent RFQ so the (potentially large) matrix is computed
        # once per RFQ, not once per line.
        rfqs = self.mapped('rfq_id')
        recommendations_by_rfq = {
            rfq.id: rfq.get_recommended_suppliers() for rfq in rfqs
        }
        for line in self:
            info = recommendations_by_rfq.get(line.rfq_id.id, {}).get(line.id, {})
            line.lowest_price = info.get('lowest') or 0.0
            line.recommended_vendor_id = info.get('vendor') or False

    # ── Onchange ──────────────────────────────────────────────────────────────
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
        self.description = self.product_id.description_pickingin \
            or self.product_id.name
        self.uom_id = self.product_id.uom_po_id or self.product_id.uom_id
        self.part_no = self.product_id.barcode
        self.parts_type = self.product_id.parts_type
        self.vehicle_make_id = self.product_id.vehicle_make_id.id

    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        if self.uom_id and self.product_id:
            if self.uom_id.category_id != self.product_id.uom_id.category_id:
                self.uom_id = self.product_id.uom_id
                return {
                    'warning': {
                        'title': _('Incompatible UoM'),
                        'message': _(
                            'The selected UoM belongs to a different category '
                            'than the product UoM. It has been reset.'
                        ),
                    }
                }

    @api.onchange('part_no')
    def _onchange_part_no(self):
        if self.part_no:
            product_id = self.env['product.product'].search([('barcode', '=', self.part_no)], limit=1)
            if product_id:
                self.product_id = product_id.id

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _prepare_purchase_order_line_vals(self):
        self.ensure_one()
        return {
            'product_id': self.product_id.id,
            'part_no': self.part_no,
            'parts_type': self.parts_type,
            'vehicle_make_id': self.vehicle_make_id.id,
            'name': self.description or self.product_id.name,
            'product_qty': self.quantity,
            'product_uom': self.uom_id.id,
            'date_planned': self.expected_date
            or fields.Date.context_today(self),
            'price_unit': 0.0,
            'multi_rfq_line_id': self.id,
        }
