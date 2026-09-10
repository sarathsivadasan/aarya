# -*- coding: utf-8 -*-
import secrets
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# Colour tokens for the comparison matrix. Applied both as inline styles
# (so the colours always render regardless of asset-bundle caching) and as
# CSS classes (for anyone who wants to theme via CSS instead).
_PRICE_COLOR_LOWEST = '#059669'   # green
_PRICE_COLOR_MID = '#d97706'      # amber
_PRICE_COLOR_HIGHEST = '#dc2626'  # red


def match_po_line_for_rfq_line(po, rfq_line):
    """Find the exact purchase.order.line on `po` that corresponds to
    `rfq_line`. Matches on the precise multi_rfq_line_id link first.
    Falls back to product_id ONLY when that vendor quoted the product on
    exactly one line (legacy quotations created before this field
    existed) — never guesses when the same product appears more than
    once on an RFQ, since that would silently mix up two different
    prices (e.g. two separate "Alternator" lines).

    This is the single shared implementation: the price matrix, the
    award wizard's price preview, and both award flows all call this —
    never re-implemented separately."""
    empty = po.order_line.browse() if po else None
    if not po or not rfq_line:
        return empty
    lines = po.order_line.filtered(lambda l: l.multi_rfq_line_id.id == rfq_line.id)
    if lines:
        return lines[:1]
    candidates = po.order_line.filtered(
        lambda l: l.product_id.id == rfq_line.product_id.id and not l.multi_rfq_line_id
    )
    return candidates[:1] if len(candidates) == 1 else empty


class PurchaseMultiRFQ(models.Model):
    _name = 'purchase.multi.rfq'
    _description = 'Multi Vendor RFQ'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), tracking=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company, tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id, tracking=True,
    )
    rfq_deadline = fields.Datetime(string='RFQ Deadline', tracking=True)
    purchase_user_id = fields.Many2one(
        'res.users', string='Purchase Representative',
        default=lambda self: self.env.user, tracking=True,
    )
    payment_term_id = fields.Many2one(
        'account.payment.term', string='Payment Terms', tracking=True,
    )
    notes = fields.Html(string='Notes')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('sent', 'RFQ Sent'),
            ('received', 'Quotations Received'),
            ('in_quoatation', "In Quotation"),
            # ('comparison', 'In Comparison'),
            ('awarded', 'Awarded'),
            ('cancel', 'Cancelled'),
        ],
        string='Status', default='draft', required=True,
        copy=False, tracking=True, index=True,
    )

    # ── Mulkiya Copy ──────────────────────────────────────────────────────────
    # Stored ONLY here. Every generated Vendor RFQ / Purchase Order exposes it
    # via a `related` field (see purchase_order_inherit.py) so it is always
    # available and always in sync — nothing is duplicated or copied.
    mulkiya_attachment = fields.Binary(
        string='Mulkiya Copy', attachment=True, copy=False,
    )
    mulkiya_filename = fields.Char(string='Mulkiya Filename', copy=False)

    # ── Award tracking (permanent — never cleared by Cancel) ────────────────────
    award_type = fields.Selection(
        selection=[
            ('complete', 'Complete Award'),
            ('line', 'Line Wise Award'),
        ],
        string='Award Type', readonly=True, copy=False, tracking=True,
    )
    award_date = fields.Datetime(
        string='Award Date', readonly=True, copy=False, tracking=True,
    )
    awarded_vendor_ids = fields.Many2many(
        'res.partner',
        'odex_multi_rfq_awarded_vendor_rel',
        'rfq_id', 'partner_id',
        string='Awarded Vendor(s)',
        compute='_compute_awarded_vendor_ids', store=True, readonly=True,
    )
    # Vehicle Details
    vehicle_id = fields.Many2one("fleet.vehicle", string="License Plate")
    vehicle_make_id = fields.Many2one("fleet.vehicle.model.brand", related="vehicle_id.vehicle_make_id",
                                      string="Vehicle Make")
    vehicle_model_id = fields.Many2one("fleet.vehicle.model", related="vehicle_id.model_id", string="Model")
    vehicle_color_id = fields.Many2one("vehicle.color", related="vehicle_id.color_id", string="Color")
    vin = fields.Char(string="Chassis No.", related="vehicle_id.vin_sn")
    engin_no = fields.Char(string="Engin No.", related="vehicle_id.engin_no")
    year = fields.Selection(string="Year", related="vehicle_id.model_year")
    
    @api.constrains('mulkiya_filename')
    def _check_mulkiya_filetype(self):
        allowed = ('.pdf', '.jpg', '.jpeg', '.png')
        for rec in self:
            if rec.mulkiya_filename and not rec.mulkiya_filename.lower().endswith(allowed):
                raise ValidationError(
                    _('Mulkiya Copy must be a PDF, JPG, JPEG, or PNG file.')
                )

    @api.depends('line_ids.awarded_vendor_id')
    def _compute_awarded_vendor_ids(self):
        for rec in self:
            rec.awarded_vendor_ids = rec.line_ids.mapped('awarded_vendor_id')

    # ── Relations ─────────────────────────────────────────────────────────────
    vendor_ids = fields.Many2many(
        'res.partner',
        'odex_multi_rfq_vendor_rel',
        'rfq_id', 'partner_id',
        string='Vendors',
        domain=[('supplier_rank', '>', 0)],
        tracking=True,
    )
    line_ids = fields.One2many(
        'purchase.multi.rfq.line', 'rfq_id',
        string='Product Lines', copy=True,
    )
    generated_rfq_ids = fields.One2many(
        'purchase.order', 'multi_rfq_id',
        string='Generated RFQs',
    )

    # ── Computed ──────────────────────────────────────────────────────────────
    vendor_count = fields.Integer(compute='_compute_vendor_count')
    rfq_count = fields.Integer(compute='_compute_rfq_count')
    quotation_count = fields.Integer(compute='_compute_rfq_count')
    purchase_order_count = fields.Integer(compute='_compute_rfq_count')
    product_count = fields.Integer(compute='_compute_product_count')
    best_vendor_id = fields.Many2one(
        'res.partner', string='Best Vendor',
        compute='_compute_best_vendor', store=False,
    )
    best_total_amount = fields.Monetary(
        string='Best Total', compute='_compute_best_vendor',
        currency_field='currency_id', store=False,
    )
    comparison_html = fields.Html(
        string='Quotation Comparison',
        compute='_compute_comparison_html',
        sanitize=False,
    )

    @api.depends('vendor_ids')
    def _compute_vendor_count(self):
        for rec in self:
            rec.vendor_count = len(rec.vendor_ids)

    @api.depends('line_ids')
    def _compute_product_count(self):
        for rec in self:
            rec.product_count = len(rec.line_ids)

    @api.depends(
        'generated_rfq_ids', 'generated_rfq_ids.state',
        'generated_rfq_ids.order_line.price_unit',
        'generated_rfq_ids.is_award_po',
    )
    def _compute_rfq_count(self):
        for rec in self:
            all_rfqs = rec.generated_rfq_ids
            # Vendor-facing RFQs only — excludes the internal confirmed
            # Purchase Orders created by a line-wise award (those are real
            # Purchase Orders, not "RFQs sent to a vendor").
            vendor_rfqs = all_rfqs.filtered(lambda r: not r.is_award_po)
            rec.rfq_count = len(vendor_rfqs)
            # A quotation counts as "received" the moment the vendor has
            # saved at least one price — no confirmation required, and a
            # later Cancel/Award of the RFQ never removes it from this count.
            rec.quotation_count = len(vendor_rfqs.filtered(
                lambda r: any(line.price_unit for line in r.order_line)
            ))
            rec.purchase_order_count = len(
                all_rfqs.filtered(lambda r: r.state == 'purchase')
            )

    @api.depends('generated_rfq_ids', 'generated_rfq_ids.amount_total',
                 'generated_rfq_ids.is_award_po')
    def _compute_best_vendor(self):
        for rec in self:
            best_vendor = self.env['res.partner']
            best_amount = 0.0
            for po in rec.generated_rfq_ids.filtered(lambda r: not r.is_award_po):
                total = sum(l.price_subtotal for l in po.order_line)
                if not total:
                    continue
                if not best_vendor or total < best_amount:
                    best_vendor = po.partner_id
                    best_amount = total
            rec.best_vendor_id = best_vendor
            rec.best_total_amount = best_amount

    @api.depends(
        'line_ids.product_id', 'line_ids.sequence',
        'vendor_ids',
        'generated_rfq_ids.state', 'generated_rfq_ids.partner_id',
        'generated_rfq_ids.order_line.price_unit',
        'generated_rfq_ids.order_line.product_id',
        'generated_rfq_ids.order_line.multi_rfq_line_id',
        'generated_rfq_ids.amount_total', 'generated_rfq_ids.date_order',
        'generated_rfq_ids.is_award_po',
    )
    def _compute_comparison_html(self):
        for rec in self:
            rec.comparison_html = rec._build_comparison_html()

    # ── SINGLE SOURCE OF TRUTH ───────────────────────────────────────────────
    # Everything that needs to know "who is the recommended/cheapest vendor
    # for this product" — the Quotation Comparison tab, Award Complete, and
    # Award Line Wise — calls _get_price_matrix() / get_recommended_suppliers()
    # below. There is exactly one place this is calculated; nothing else is
    # allowed to compute it independently.
    def _get_price_matrix(self):
        """Build the full Product x Vendor price matrix for this RFQ.

        Reads directly from purchase.order.line — no duplicated storage.
        Includes EVERY generated PO regardless of state (draft/sent/purchase/
        cancel): a vendor's quoted prices must remain visible in the
        comparison forever, even after their RFQ is cancelled (e.g. because
        they lost the award) or the whole Multi Vendor RFQ is cancelled.
        Internal award-confirmation POs (is_award_po=True, created only by
        line-wise awards) are excluded — they are copies of already-quoted
        prices, not a new vendor quotation.
        """
        self.ensure_one()
        all_pos = self.generated_rfq_ids.filtered(lambda po: not po.is_award_po)

        # Stable column order: vendors as picked on the RFQ first, then any
        # PO vendor that isn't in vendor_ids (defensive edge case).
        po_vendor_ids = {po.partner_id.id for po in all_pos}
        ordered_vendors = [v for v in self.vendor_ids if v.id in po_vendor_ids]
        seen_ids = {v.id for v in ordered_vendors}
        for po in all_pos:
            if po.partner_id.id not in seen_ids:
                ordered_vendors.append(po.partner_id)
                seen_ids.add(po.partner_id.id)

        # One PO per vendor — used only as tie-break metadata (quotation
        # total / submission date), never for pricing.
        po_by_vendor = {}
        for po in all_pos:
            po_by_vendor.setdefault(po.partner_id.id, po)
        vendor_by_id = {v.id: v for v in ordered_vendors}

        # Single pass over all order lines of all POs — one query total
        # regardless of product/vendor count (no N+1).
        #
        # Primary match: the exact originating RFQ line (multi_rfq_line_id).
        # This is required because the same product can appear more than
        # once in a Multi Vendor RFQ (e.g. two separate "Alternator" needs)
        # — matching by product_id alone would silently collapse those into
        # one shared price.
        #
        # Fallback: quotations generated before this field existed won't
        # have it set. For those, match by product_id — but ONLY when that
        # vendor quoted that product on exactly one line. If it's ambiguous
        # (quoted on 2+ lines with no line reference), leave it unquoted
        # rather than guess wrong.
        order_vendor_map = {po.id: po.partner_id.id for po in all_pos}
        line_price_map = {}  # (rfq_line_id, vendor_id) -> price_unit
        legacy_prices_by_product = {}  # (product_id, vendor_id) -> [price_unit, ...]
        for po_line in all_pos.order_line:
            vendor_id = order_vendor_map.get(po_line.order_id.id)
            if vendor_id is None or not po_line.product_id:
                continue
            if po_line.multi_rfq_line_id:
                line_price_map[(po_line.multi_rfq_line_id.id, vendor_id)] = po_line.price_unit
            else:
                legacy_prices_by_product.setdefault(
                    (po_line.product_id.id, vendor_id), []
                ).append(po_line.price_unit)

        def _lookup_price(rfq_line, vendor_id):
            price = line_price_map.get((rfq_line.id, vendor_id))
            if price is not None:
                return price
            legacy = legacy_prices_by_product.get((rfq_line.product_id.id, vendor_id))
            if legacy and len(legacy) == 1:
                return legacy[0]
            return None

        # ── Pass 1: prices + tied-lowest vendors per line, and tally how
        # many products each vendor is (tied-)lowest on. ────────────────────
        lines_data = []
        win_count = {v.id: 0 for v in ordered_vendors}
        for rfq_line in self.line_ids:
            product = rfq_line.product_id
            prices = [_lookup_price(rfq_line, v.id) for v in ordered_vendors]
            valid_prices = [p for p in prices if p]
            lowest = min(valid_prices) if valid_prices else None
            highest = max(valid_prices) if valid_prices else None
            tied_vendor_ids = [
                v.id for v, p in zip(ordered_vendors, prices)
                if lowest is not None and p == lowest
            ]
            for vendor_id in tied_vendor_ids:
                win_count[vendor_id] += 1
            lines_data.append({
                'line': rfq_line,
                'product': product,
                'prices': prices,
                'lowest': lowest,
                'highest': highest,
                'tied_vendor_ids': tied_vendor_ids,
            })

        def tie_break_key(vendor_id):
            # 1) lowest overall quotation total, 2) earliest submission
            # date, 3) alphabetical vendor name.
            po = po_by_vendor.get(vendor_id)
            vendor = vendor_by_id.get(vendor_id)
            amount_total = po.amount_total if po else float('inf')
            date_order = po.date_order if po and po.date_order else fields.Datetime.from_string('9999-12-31 23:59:59')
            name = (vendor.name or '') if vendor else ''
            return (amount_total, date_order, name)

        # Determine the single global Preferred Supplier: most lowest-price
        # wins across all products; ties broken above.
        contenders = [vid for vid, cnt in win_count.items() if cnt > 0]
        preferred_vendor_id = None
        if contenders:
            top_score = max(win_count[vid] for vid in contenders)
            top_contenders = [vid for vid in contenders if win_count[vid] == top_score]
            preferred_vendor_id = sorted(top_contenders, key=tie_break_key)[0]

        return {
            'ordered_vendors': ordered_vendors,
            'vendor_by_id': vendor_by_id,
            'po_by_vendor': po_by_vendor,
            'lines': lines_data,
            'win_count': win_count,
            'preferred_vendor_id': preferred_vendor_id,
            'tie_break_key': tie_break_key,
        }

    def _get_recommended_supplier_id(self, tied_vendor_ids, matrix):
        """THE single tie-break resolver: collapses any set of tied-lowest
        vendors down to exactly one. Used everywhere a single supplier needs
        to be shown or awarded — never re-implemented anywhere else."""
        if not tied_vendor_ids:
            return None
        if len(tied_vendor_ids) == 1:
            return tied_vendor_ids[0]
        preferred_vendor_id = matrix['preferred_vendor_id']
        if preferred_vendor_id in tied_vendor_ids:
            return preferred_vendor_id
        return sorted(tied_vendor_ids, key=matrix['tie_break_key'])[0]

    def get_recommended_suppliers(self):
        """Public single source of truth.

        Returns {rfq_line_id: {'vendor': res.partner, 'lowest': float|None,
        'highest': float|None, 'prices': {vendor_id: price}}}.

        Called identically by the Quotation Comparison tab, the Products
        smart button, Award Complete, and Award Line Wise — they can never
        disagree on who the recommended supplier is.
        """
        self.ensure_one()
        matrix = self._get_price_matrix()
        result = {}
        for entry in matrix['lines']:
            winner_id = self._get_recommended_supplier_id(entry['tied_vendor_ids'], matrix)
            vendor = matrix['vendor_by_id'].get(winner_id, self.env['res.partner'])
            result[entry['line'].id] = {
                'vendor': vendor,
                'lowest': entry['lowest'],
                'highest': entry['highest'],
                'prices': {
                    v.id: p for v, p in zip(matrix['ordered_vendors'], entry['prices'])
                },
            }
        return result

    # ── Comparison matrix renderer (pure presentation, no business logic) ────
    def _build_comparison_html(self):
        """Render the dynamic Product x Vendor price comparison table as
        HTML. All actual supplier-recommendation logic lives in
        _get_price_matrix() / get_recommended_suppliers() above — this
        method only turns that data into markup."""
        self.ensure_one()
        if not self.line_ids:
            return False

        matrix = self._get_price_matrix()
        ordered_vendors = matrix['ordered_vendors']
        if not ordered_vendors:
            return False

        header_cells = Markup('').join(
            Markup('<th class="text-end o_multi_rfq_vendor_col">%s</th>') % (vendor.name or '')
            for vendor in ordered_vendors
        )

        row_chunks = [
            self._render_comparison_row(entry, matrix)
            for entry in matrix['lines']
        ]

        table = Markup(
            '<div class="o_multi_rfq_comparison_wrap">'
            '<table class="table table-sm table-bordered o_multi_rfq_comparison_table">'
            '<thead class="table-light"><tr>'
            '<th class="o_multi_rfq_product_col">%s</th>'
            '%s'
            '<th class="text-end">%s</th>'
            '<th>%s</th>'
            '</tr></thead>'
            '<tbody>%s</tbody>'
            '</table></div>'
        ) % (
            _('Product'),
            header_cells,
            _('Lowest Price'),
            _('Supplier'),
            Markup('').join(row_chunks),
        )
        return table

    def _render_comparison_row(self, entry, matrix):
        product = entry['product']
        prices = entry['prices']
        lowest = entry['lowest']
        highest = entry['highest']

        price_cells = []
        for price in prices:
            if not price:
                price_cells.append(
                    Markup('<td class="text-end text-muted o_multi_rfq_price">—</td>')
                )
                continue
            # Colour tier is decided per-cell so ties are handled correctly:
            # every vendor tied at the lowest price is green, every vendor
            # tied at the highest price is red, everything else is amber.
            # When all vendors quoted the same price, it is both the lowest
            # and the highest — it is shown as the lowest (green).
            if price == lowest:
                css_class = 'o_multi_rfq_price_lowest'
                color = _PRICE_COLOR_LOWEST
            elif price == highest:
                css_class = 'o_multi_rfq_price_highest'
                color = _PRICE_COLOR_HIGHEST
            else:
                css_class = 'o_multi_rfq_price_mid'
                color = _PRICE_COLOR_MID
            price_cells.append(
                Markup(
                    '<td class="text-end o_multi_rfq_price %s" '
                    'style="color:%s;font-weight:600">%s</td>'
                )
                % (css_class, color, '{:,.2f}'.format(price))
            )

        # Supplier column always shows exactly ONE vendor, resolved by the
        # single shared tie-break method — the exact same one used to
        # pre-fill the Award Line Wise wizard, so the two screens can never
        # disagree.
        winner_id = self._get_recommended_supplier_id(entry['tied_vendor_ids'], matrix)
        supplier_name = matrix['vendor_by_id'][winner_id].name or '' if winner_id else ''

        return Markup(
            '<tr>'
            '<td class="o_multi_rfq_product_col">%s</td>'
            '%s'
            '<td class="text-end o_multi_rfq_price_lowest" style="color:%s;font-weight:600">%s</td>'
            '<td class="o_multi_rfq_supplier">%s</td>'
            '</tr>'
        ) % (
            product.name or '',
            Markup('').join(price_cells),
            _PRICE_COLOR_LOWEST,
            ('{:,.2f}'.format(lowest) if lowest is not None else '—'),
            supplier_name,
        )


    # ── ORM ───────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('purchase.multi.rfq')
                    or _('New')
                )
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            if vals.get('mulkiya_attachment'):
                rec._log_mulkiya_uploaded()
        return records

    def write(self, vals):
        # Detect a genuinely new/replaced Mulkiya file BEFORE the write,
        # so the chatter message only fires when the content actually
        # changes (not on every unrelated save).
        logging_needed = self.env['purchase.multi.rfq']
        if 'mulkiya_attachment' in vals:
            logging_needed = self.filtered(
                lambda r: r.mulkiya_attachment != vals.get('mulkiya_attachment')
            )
        res = super().write(vals)
        for rec in logging_needed:
            rec._log_mulkiya_uploaded()
        return res

    def _log_mulkiya_uploaded(self):
        """Post the Mulkiya Copy to chatter as a real, visible attachment
        (it is already stored as a standard ir.attachment thanks to
        attachment=True on the field — this just makes that upload show
        up in the document's history, per the audit requirement).

        Posted on the parent Multi Vendor RFQ AND on every already-
        generated vendor RFQ/Purchase Order, since the Mulkiya must be
        visible from wherever the vendor is actually looking."""
        self.ensure_one()
        attachment = self._get_mulkiya_attachment()
        attachment_ids = [attachment.id] if attachment else []
        body = _('Mulkiya Copy uploaded: %s') % (self.mulkiya_filename or _('file'))
        self.message_post(body=body, attachment_ids=attachment_ids)
        for po in self.generated_rfq_ids:
            po.message_post(body=body, attachment_ids=attachment_ids)

    def copy(self, default=None):
        default = dict(default or {})
        default.update({'name': _('New'), 'state': 'draft'})
        return super().copy(default)

    # ── Buttons ───────────────────────────────────────────────────────────────
    def action_select_all_vendors(self):
        """Add 
        all active suppliers to vendor_ids."""
        self.ensure_one()
        all_suppliers = self.env['res.partner'].search(
            [('supplier_rank', '>', 0), ('active', '=', True)]
        )
        self.vendor_ids = all_suppliers

    def action_send_rfq(self):
        self.ensure_one()
        if not self.vendor_ids:
            raise UserError(_('Please select at least one vendor before sending.'))
        if not self.line_ids:
            raise UserError(_('Please add at least one product before sending.'))

        PurchaseOrder = self.env['purchase.order']
        template = self.env.ref(
            'odex_multi_vendor_rfq.email_template_multi_rfq',
            raise_if_not_found=False,
        )

        created_pos = PurchaseOrder
        mulkiya_attachment = self._get_mulkiya_attachment()
        for vendor in self.vendor_ids:
            existing = self.generated_rfq_ids.filtered(
                lambda r, v=vendor: r.partner_id == v
                and r.state in ('draft', 'sent')
            )
            if existing:
                continue
            po = PurchaseOrder.create(self._prepare_purchase_order_vals(vendor))
            po.write({'vendor_portal_token': secrets.token_urlsafe(32)})
            if mulkiya_attachment:
                po.message_post(
                    body=_('Mulkiya Copy uploaded: %s') % (self.mulkiya_filename or _('file')),
                    attachment_ids=[mulkiya_attachment.id],
                )
            created_pos |= po

        if template:
            email_values = self._get_mulkiya_email_values()
            for po in created_pos:
                try:
                    template.send_mail(po.id, force_send=True, email_values=email_values)
                except Exception:
                    # Don't block RFQ creation if email fails
                    pass       
        self.write({'state': 'sent'})
        if created_pos:
            [each.write({'state': 'sent'}) for each in created_pos]
        self.message_post(
            body=_('RFQ sent to %d vendor(s): %s') % (
                len(self.vendor_ids),
                ', '.join(self.vendor_ids.mapped('name')),
            )
        )
        return True

    def action_resend_rfq(self):
        self.ensure_one()
        template = self.env.ref(
            'odex_multi_vendor_rfq.email_template_multi_rfq',
            raise_if_not_found=False,
        )
        if template:
            email_values = self._get_mulkiya_email_values()
            for po in self.generated_rfq_ids.filtered(
                lambda r: r.state not in ('cancel',)
            ):
                try:
                    template.send_mail(po.id, force_send=True, email_values=email_values)
                except Exception:
                    pass
        self.message_post(body=_('RFQ re-sent to all vendors.'))
        return True

    def action_cancel(self):
        self.ensure_one()
        self.generated_rfq_ids.filtered(
            lambda r: r.state not in ('purchase', 'done', 'cancel')
        ).button_cancel()
        self.write({'state': 'cancel'})
        self.message_post(body=_('Multi Vendor RFQ cancelled.'))

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    # def action_set_comparison(self):
    #     self.write({'state': 'comparison'})

    def request_for_quotation(self):
        self.ensure_one()  
        order_lines = []
        for line in self.line_ids:
            order_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom': line.uom_id.id,
                    'name': line.description if line.description else line.product_id.display_name,
                    'product_uom_qty': line.quantity,
                    'part_no': line.part_no,
                    'parts_type': line.parts_type,
                    'custom_price': line.lowest_price,
                    'vendor_id': line.recommended_vendor_id.id,
                }))
        if self.inspection_id:
            so = self.env['sale.order'].create({
                    'partner_id': self.inspection_id.partner_id.id,
                    'inspection_id': self.inspection_id.id,
                    'job_id': self.inspection_id.id if self.inspection_id.is_jobcard else False,
                    'vehicle_id': self.vehicle_id.id if self.vehicle_id else False,
                    'origin': self.name,
                    'order_line': order_lines,  # Standard Odoo field is 'order_line'
                })
        if so:
            self.write({'state': 'in_quoatation'})
        return so

    # ── Smart button openers ──────────────────────────────────────────────────
    def action_view_generated_rfqs(self):
        """RFQs Sent — every Vendor RFQ generated from this Multi Vendor RFQ
        (excludes the internal Purchase Orders a line-wise award creates)."""
        self.ensure_one()
        return {
            'name': _('RFQs Sent'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('multi_rfq_id', '=', self.id), ('is_award_po', '=', False)],
            'context': {'create': False},
        }

    def action_view_quotations(self):
        """Quotations — only the Vendor RFQs that actually received a
        submitted price."""
        self.ensure_one()
        submitted_ids = self.generated_rfq_ids.filtered(
            lambda r: not r.is_award_po and any(l.price_unit for l in r.order_line)
        ).ids
        return {
            'name': _('Vendor Quotations'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', submitted_ids)],
            'context': {'create': False},
        }

    def action_view_purchase_orders(self):
        """Purchase Orders — the actual confirmed POs resulting from an
        award (both Complete and Line Wise create real Purchase Orders)."""
        self.ensure_one()
        return {
            'name': _('Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [
                ('multi_rfq_id', '=', self.id),
                ('state', '=', 'purchase'),
            ],
            'context': {'create': False},
        }

    def action_view_vendors(self):
        """Vendors — one row per invited vendor with their status/quoted
        amount, distinct from the raw RFQ/PO documents."""
        self.ensure_one()
        list_view = self.env.ref(
            'odex_multi_vendor_rfq.view_purchase_order_vendor_status_list',
            raise_if_not_found=False,
        )
        views = [(list_view.id if list_view else False, 'list'), (False, 'form')]
        return {
            'name': _('Invited Vendors'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'views': views,
            'domain': [('multi_rfq_id', '=', self.id), ('is_award_po', '=', False)],
            'context': {'create': False},
        }

    def action_view_products(self):
        """Products — the RFQ's own product lines, enriched with the
        recommended supplier / lowest price / awarded vendor / PO."""
        self.ensure_one()
        list_view = self.env.ref(
            'odex_multi_vendor_rfq.view_purchase_multi_rfq_line_list',
            raise_if_not_found=False,
        )
        form_view = self.env.ref(
            'odex_multi_vendor_rfq.view_purchase_multi_rfq_line_form',
            raise_if_not_found=False,
        )
        views = [
            (list_view.id if list_view else False, 'list'),
            (form_view.id if form_view else False, 'form'),
        ]
        return {
            'name': _('Products'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.multi.rfq.line',
            'view_mode': 'list,form',
            'views': views,
            'domain': [('rfq_id', '=', self.id)],
            'context': {'create': False},
        }

    # ── Award ─────────────────────────────────────────────────────────────────
    def action_award_complete(self):
        self.ensure_one()
        # Same single source of truth as the Comparison tab and Award Line
        # Wise: the vendor with the most lowest-price wins across all
        # products (never a separately-computed "cheapest total").
        matrix = self._get_price_matrix()
        preferred_vendor_id = matrix['preferred_vendor_id']
        return {
            'name': _('Award Complete RFQ'),
            'type': 'ir.actions.act_window',
            'res_model': 'award.rfq.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_multi_rfq_id': self.id,
                'default_award_mode': 'complete',
                'default_vendor_id': preferred_vendor_id,
                'award_mode': 'complete',
            },
        }

    def action_award_line_wise(self):
        self.ensure_one()
        return {
            'name': _('Award Line Wise'),
            'type': 'ir.actions.act_window',
            'res_model': 'award.rfq.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_multi_rfq_id': self.id,
                'default_award_mode': 'line',
                'award_mode': 'line',
            },
        }

    def _do_award_complete(self, vendor_id):
        """Complete Award: the winner's existing quotation already contains
        every line exactly as quoted, so it is confirmed as-is — nothing is
        removed from it. Losing vendors' RFQs are cancelled (an operational
        status change only); their quoted prices remain fully visible in the
        comparison forever because the comparison never filters by state."""
        self.ensure_one()
        winner_po = self.generated_rfq_ids.filtered(
            lambda r: r.partner_id.id == vendor_id
            and not r.is_award_po
            and r.state not in ('cancel',)
        )
        if not winner_po:
            raise UserError(_('No active RFQ found for the selected vendor.'))
        winner_po = winner_po[0]
        winner_po.button_confirm()
        winner_po.message_post(
            body=_('Purchase Order confirmed from Complete Award of "%s".') % self.name
        )
        winner_po.action_send_award_email()
        losers = self.generated_rfq_ids.filtered(
            lambda r: r.id != winner_po.id
            and not r.is_award_po
            and r.state not in ('purchase', 'done', 'cancel')
        )
        losers.button_cancel()

        # Permanent award record — never cleared by Cancel or by anything else.
        for rfq_line in self.line_ids:
            po_line = match_po_line_for_rfq_line(winner_po, rfq_line)
            rfq_line.write({
                'awarded_vendor_id': vendor_id,
                'awarded_po_id': winner_po.id,
                'awarded_price': po_line.price_unit if po_line else 0.0,
            })
        self.write({
            'state': 'awarded',
            'award_type': 'complete',
            'award_date': fields.Datetime.now(),
        })
        self.message_post(
            body=_('Awarded to <b>%s</b> (Complete Award). Purchase Order <b>%s</b> created.')
            % (winner_po.partner_id.name, winner_po.name)
        )

    # ── Print ─────────────────────────────────────────────────────────────────
    def action_print_comparison_report(self):
        return self.env.ref(
            'odex_multi_vendor_rfq.action_report_multi_rfq_comparison'
        ).report_action(self)

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _get_mulkiya_attachment(self):
        """The ir.attachment Odoo auto-creates for the mulkiya_attachment
        Binary field (attachment=True) — the single stored copy that every
        generated PO exposes via a related field, and that RFQ emails
        attach automatically."""
        self.ensure_one()
        if not self.mulkiya_attachment:
            return self.env['ir.attachment']
        return self.env['ir.attachment'].search([
            ('res_model', '=', 'purchase.multi.rfq'),
            ('res_field', '=', 'mulkiya_attachment'),
            ('res_id', '=', self.id),
        ], limit=1)

    def _get_mulkiya_email_values(self):
        """email_values to pass to template.send_mail() so the Mulkiya Copy
        is automatically included on every RFQ email, with no per-call
        duplication of the underlying file."""
        self.ensure_one()
        attachment = self._get_mulkiya_attachment()
        return {'attachment_ids': [(4, attachment.id)]} if attachment else {}

    def _prepare_purchase_order_vals(self, vendor):
        self.ensure_one()
        return {
            'partner_id': vendor.id,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'date_order': fields.Datetime.now(),
            'date_planned': self.rfq_deadline,
            'payment_term_id': self.payment_term_id.id,
            'vehicle_id': self.vehicle_id.id,
            'notes': self.notes,
            'multi_rfq_id': self.id,
            'order_line': [
                (0, 0, line._prepare_purchase_order_line_vals())
                for line in self.line_ids
            ],
            'origin': self.name,
        }
