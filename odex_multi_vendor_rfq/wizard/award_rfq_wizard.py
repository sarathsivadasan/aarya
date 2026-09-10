# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from ..models.purchase_multi_rfq import match_po_line_for_rfq_line


class AwardRFQWizard(models.TransientModel):
    _name = 'award.rfq.wizard'
    _description = 'Award RFQ Wizard'

    multi_rfq_id = fields.Many2one(
        'purchase.multi.rfq',
        string='Multi RFQ',
        required=True,
        ondelete='cascade',
    )
    award_mode = fields.Selection(
        selection=[
            ('complete', 'Award Complete RFQ'),
            ('line', 'Award Line Wise'),
        ],
        string='Award Mode',
        required=True,
        default='complete',
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Award to Vendor',
    )
    line_award_ids = fields.One2many(
        'award.rfq.wizard.line',
        'wizard_id',
        string='Line Awards',
    )
    available_vendor_ids = fields.Many2many(
        'res.partner',
        'award_wizard_avail_vendor_rel',
        'wizard_id',
        'partner_id',
        compute='_compute_available_vendors',
        string='Available Vendors',
    )
    win_summary = fields.Char(
        string='Recommendation Basis',
        compute='_compute_win_summary',
    )

    @api.depends('multi_rfq_id')
    def _compute_win_summary(self):
        for rec in self:
            if not rec.multi_rfq_id:
                rec.win_summary = ''
                continue
            matrix = rec.multi_rfq_id._get_price_matrix()
            win_count = matrix['win_count']
            vendor_by_id = matrix['vendor_by_id']
            parts = [
                _('%(vendor)s: %(count)d product(s)') % {
                    'vendor': vendor_by_id[vid].name, 'count': count,
                }
                for vid, count in sorted(win_count.items(), key=lambda kv: -kv[1])
                if count
            ]
            rec.win_summary = ' | '.join(parts)

    @api.depends('multi_rfq_id')
    def _compute_available_vendors(self):
        for rec in self:
            if rec.multi_rfq_id:
                partners = rec.multi_rfq_id.generated_rfq_ids.filtered(
                    lambda r: not r.is_award_po
                ).mapped('partner_id')
                rec.available_vendor_ids = partners
            else:
                rec.available_vendor_ids = self.env['res.partner']

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Populate line awards when mode is 'line'
        if res.get('award_mode') == 'line' and res.get('multi_rfq_id'):
            rfq = self.env['purchase.multi.rfq'].browse(res['multi_rfq_id'])
            lines = self._build_line_awards(rfq)
            if lines:
                res['line_award_ids'] = lines
        return res

    def _build_line_awards(self, rfq):
        # Single source of truth: identical recommendation used by the
        # Quotation Comparison tab. The wizard NEVER computes this itself.
        recommendations = rfq.get_recommended_suppliers()
        lines = []
        for rfq_line in rfq.line_ids:
            info = recommendations.get(rfq_line.id, {})
            vendor = info.get('vendor')
            lines.append((0, 0, {
                'rfq_line_id': rfq_line.id,
                'product_id': rfq_line.product_id.id,
                'quantity': rfq_line.quantity,
                'uom_id': rfq_line.uom_id.id,
                'vendor_id': vendor.id if vendor else False,
            }))
        return lines

    # NOTE: line_award_ids is populated ONLY here, in default_get — never in
    # an onchange. An onchange keyed on multi_rfq_id/award_mode (fields
    # that sit hidden on the form and don't change once the wizard is
    # open) can get replayed by the client during its own re-evaluation
    # cycles, and a `[(5, 0, 0)] + lines` reset would silently wipe out
    # anything the user had already edited. Populating exactly once here
    # avoids that entirely.

    def action_award(self):
        self.ensure_one()
        if self.award_mode == 'complete':
            if not self.vendor_id:
                raise UserError(_('Please select a vendor to award.'))
            self.multi_rfq_id._do_award_complete(self.vendor_id.id)
        else:
            self._do_award_line_wise()
        return {'type': 'ir.actions.act_window_close'}

    def _do_award_line_wise(self):
        rfq = self.multi_rfq_id
        if not self.line_award_ids:
            raise UserError(_('No line awards configured.'))

        # Validate EVERYTHING up front, before any database write. This
        # guarantees we never partially create a Purchase Order and then
        # fail — either every vendor gets their PO, or nothing is touched.
        for award_line in self.line_award_ids:
            if not award_line.product_id:
                raise UserError(
                    _('An award line is missing its product. Please close '
                      'and reopen the wizard.')
                )
            if not award_line.vendor_id:
                raise UserError(
                    _('Please select a vendor for product "%s".')
                    % award_line.product_id.display_name
                )

        # Group award lines by vendor
        vendor_award_lines = {}
        for award_line in self.line_award_ids:
            vendor_award_lines.setdefault(award_line.vendor_id.id, []).append(award_line)

        PurchaseOrder = self.env['purchase.order']
        confirmed_pos = PurchaseOrder
        award_time = fields.Datetime.now()

        for vendor_id, award_lines in vendor_award_lines.items():
            source_po = rfq.generated_rfq_ids.filtered(
                lambda r, v=vendor_id: r.partner_id.id == v
                and not r.is_award_po
                and r.state not in ('cancel',)
            )
            source_po = source_po[0] if source_po else False
            if not source_po:
                # Surface this clearly rather than silently dropping the
                # vendor's award — the user needs to know why a vendor
                # they assigned lines to ended up with no Purchase Order.
                vendor_name = award_lines[0].vendor_id.display_name
                raise UserError(
                    _('Could not find an active quotation from vendor "%s" '
                      'to award. Their RFQ may have been cancelled.')
                    % vendor_name
                )

            # Build a DEDICATED confirmed Purchase Order containing only the
            # awarded lines. The vendor's original quotation (source_po) is
            # never touched — every price they quoted, on every product,
            # remains permanently intact for the comparison and for audit.
            order_line_vals = []
            for award_line in award_lines:
                po_line = match_po_line_for_rfq_line(source_po, award_line.rfq_line_id)
                price_unit = po_line.price_unit if po_line else (award_line.vendor_price or 0.0)
                product = award_line.product_id
                # Standard Odoo purchase description (falls back to the
                # product's display name) — 'name' is mandatory on
                # purchase.order.line and must never be left empty.
                # Standard Odoo purchase description when available on this
                # build; always falls back safely so 'name' (mandatory on
                # purchase.order.line) is never left empty and this can
                # never crash regardless of which product methods exist.
                description = False
                if hasattr(product, 'get_product_multiline_description_purchase'):
                    description = product.get_product_multiline_description_purchase()
                description = description or product.display_name or product.name
                order_line_vals.append((0, 0, {
                    'product_id': product.id,
                    'name': description,
                    'product_qty': award_line.quantity,
                    'product_uom': award_line.uom_id.id,
                    'date_planned': source_po.date_planned or fields.Date.context_today(self),
                    'price_unit': price_unit,
                    'multi_rfq_line_id': award_line.rfq_line_id.id,
                }))

            new_po = PurchaseOrder.create({
                'partner_id': vendor_id,
                'currency_id': source_po.currency_id.id,
                'company_id': source_po.company_id.id,
                'date_order': award_time,
                'payment_term_id': source_po.payment_term_id.id,
                'multi_rfq_id': rfq.id,
                'is_award_po': True,
                'origin': rfq.name,
                'order_line': order_line_vals,
            })
            new_po.button_confirm()
            confirmed_pos |= new_po
            new_po.message_post(
                body=_('Purchase Order created from Line-Wise Award of "%s".') % rfq.name
            )
            new_po.action_send_award_email()

            for award_line in award_lines:
                rfq_line = award_line.rfq_line_id
                if not rfq_line:
                    continue
                awarded_po_line = match_po_line_for_rfq_line(new_po, rfq_line)
                rfq_line.write({
                    'awarded_vendor_id': vendor_id,
                    'awarded_po_id': new_po.id,
                    'awarded_price': awarded_po_line.price_unit if awarded_po_line else 0.0,
                })

        # Vendors that received no awarded lines are simply not awarded.
        # Their original quotation is left completely intact; we only close
        # them out operationally (Cancel is a status change — the comparison
        # never filters by state, so their quoted prices remain visible).
        awarded_vendor_ids = set(vendor_award_lines.keys())
        rfq.generated_rfq_ids.filtered(
            lambda r: not r.is_award_po
            and r.partner_id.id not in awarded_vendor_ids
            and r.state not in ('purchase', 'done', 'cancel')
        ).button_cancel()

        rfq.write({
            'state': 'awarded',
            'award_type': 'line',
            'award_date': award_time,
        })
        rfq.message_post(
            body=_('Line-wise award completed. %d Purchase Order(s) created.')
            % len(confirmed_pos)
        )


class AwardRFQWizardLine(models.TransientModel):
    _name = 'award.rfq.wizard.line'
    _description = 'Award RFQ Wizard Line'

    wizard_id = fields.Many2one(
        'award.rfq.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    rfq_line_id = fields.Many2one(
        'purchase.multi.rfq.line',
        string='RFQ Line',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=True,
    )
    quantity = fields.Float(string='Quantity', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='UoM', readonly=True)
    vendor_id = fields.Many2one(
        'res.partner',
        string='Award to Vendor',
        required=True,
    )
    vendor_price = fields.Float(
        string='Vendor Unit Price',
        compute='_compute_vendor_price',
    )
    vendor_subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_vendor_price',
    )

    @api.depends('vendor_id', 'rfq_line_id', 'quantity', 'wizard_id.multi_rfq_id')
    def _compute_vendor_price(self):
        for rec in self:
            price = 0.0
            if rec.vendor_id and rec.wizard_id.multi_rfq_id:
                pos = rec.wizard_id.multi_rfq_id.generated_rfq_ids.filtered(
                    lambda r: r.partner_id == rec.vendor_id
                    and not r.is_award_po
                    and r.state not in ('cancel',)
                )
                if pos:
                    po_line = match_po_line_for_rfq_line(pos[0], rec.rfq_line_id)
                    if po_line:
                        price = po_line.price_unit
            rec.vendor_price = price
            rec.vendor_subtotal = price * rec.quantity
