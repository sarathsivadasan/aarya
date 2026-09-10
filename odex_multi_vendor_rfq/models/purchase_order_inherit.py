# -*- coding: utf-8 -*-
import secrets
from odoo import api, fields, models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    multi_rfq_id = fields.Many2one(
        'purchase.multi.rfq',
        string='Multi Vendor RFQ',
        ondelete='set null',
        index=True,
        copy=False,
    )
    is_multi_rfq = fields.Boolean(
        string='From Multi RFQ',
        compute='_compute_is_multi_rfq',
        store=True,
    )
    is_award_po = fields.Boolean(
        string='Award-Created PO',
        default=False,
        copy=False,
        help='True only for the confirmed Purchase Order created by a '
             'Line Wise award. The vendor\'s original quotation (with every '
             'product they quoted on) is a separate record and is never '
             'modified or deleted by the award.',
    )
    vendor_portal_token = fields.Char(
        string='Vendor Portal Token',
        copy=False,
        index=True,
    )
    vendor_submitted = fields.Boolean(
        string='Vendor Submitted',
        default=False,
        copy=False,
        tracking=True,
    )

    # ── Mulkiya Copy ──────────────────────────────────────────────────────────
    # Stored ONLY on purchase.multi.rfq. This is a plain related field (not
    # stored here), so every generated Vendor RFQ and Purchase Order always
    # shows exactly the current Mulkiya with zero duplication.
    mulkiya_attachment = fields.Binary(
        related='multi_rfq_id.mulkiya_attachment', string='Mulkiya Copy', readonly=True,
    )
    mulkiya_filename = fields.Char(
        related='multi_rfq_id.mulkiya_filename', readonly=True,
    )

    # ── Vendor-status display (used by the Vendors smart button) ────────────────
    quotation_status = fields.Selection(
        selection=[('pending', 'Pending'), ('submitted', 'Submitted')],
        string='Quotation Status', compute='_compute_quotation_status',
    )
    award_status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('awarded', 'Awarded'),
            ('not_awarded', 'Not Awarded'),
        ],
        string='Award Status', compute='_compute_award_status',
    )
    quoted_amount = fields.Monetary(
        string='Total Quoted Amount', related='amount_total', readonly=True,
    )
    partner_email = fields.Char(
        string='Vendor Email', related='partner_id.email', readonly=True,
    )
    partner_phone = fields.Char(
        string='Vendor Phone', related='partner_id.phone', readonly=True,
    )

    @api.depends('multi_rfq_id')
    def _compute_is_multi_rfq(self):
        for rec in self:
            rec.is_multi_rfq = bool(rec.multi_rfq_id)

    @api.depends('order_line.price_unit')
    def _compute_quotation_status(self):
        for rec in self:
            rec.quotation_status = (
                'submitted' if any(l.price_unit for l in rec.order_line) else 'pending'
            )

    @api.depends('state', 'multi_rfq_id.state', 'multi_rfq_id.awarded_vendor_ids')
    def _compute_award_status(self):
        for rec in self:
            if rec.state == 'purchase':
                rec.award_status = 'awarded'
            elif rec.multi_rfq_id and rec.multi_rfq_id.state == 'awarded':
                rec.award_status = 'not_awarded'
            else:
                rec.award_status = 'pending'

    def action_send_award_email(self):
        """Automatically email this awarded Purchase Order to its vendor.

        Uses Odoo's STANDARD purchase email template and the STANDARD
        portal.mixin access token (purchase.order already inherits
        portal.mixin in Odoo core) — no custom token, no hardcoded domain.
        Shared by both Award Complete and Award Line Wise so there is
        exactly one implementation of "send the awarded PO"."""
        self.ensure_one()
        template = self.env.ref(
            'purchase.email_template_edi_purchase', raise_if_not_found=False
        )
        if not template:
            return False
        # Standard Odoo secure sharing token (portal.mixin) — generated on
        # demand, never hardcoded.
        self._portal_ensure_token()
        email_values = {}
        mulkiya = self.multi_rfq_id._get_mulkiya_attachment() if self.multi_rfq_id else False
        if mulkiya:
            email_values['attachment_ids'] = [(4, mulkiya.id)]
        try:
            template.send_mail(self.id, force_send=True, email_values=email_values)
        except Exception:
            # Never let a failed email block the award itself.
            self.message_post(
                body=_('Automatic Purchase Order email failed to send — '
                       'please send it manually.')
            )
            return False
        # get_portal_url() (from portal.mixin) builds the secure link from
        # web.base.url + the access token — never a hardcoded domain.
        self.message_post(
            body=_('Purchase Order emailed to %s. Portal link: %s')
            % (self.partner_id.name, self.get_portal_url())
        )
        return True

    def action_send_rfq_via_email(self):
        """Send/re-send the portal link email to this specific vendor."""
        self.ensure_one()
        # Ensure token exists
        if not self.vendor_portal_token:
            self.vendor_portal_token = secrets.token_urlsafe(32)

        template = self.env.ref(
            'odex_multi_vendor_rfq.email_template_multi_rfq',
            raise_if_not_found=False,
        )
        if not template:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Email template not found.'),
                    'type': 'warning',
                },
            }

        # Open the Odoo compose wizard pre-filled with the template
        compose_ctx = {
            'default_model': 'purchase.order',
            'default_res_ids': [self.id],
            'default_use_template': True,
            'default_template_id': template.id,
            'default_composition_mode': 'comment',
            'force_email': True,
        }
        return {
            'name': _('Send Portal Link to %s') % self.partner_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': compose_ctx,
        }


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # Points back to the EXACT RFQ line this quotation line was generated
    # for. Required because a Multi Vendor RFQ can list the same product
    # more than once (e.g. two separate "Alternator" needs) — matching
    # purely by product_id would silently collapse those into a single
    # price. Every price lookup used by the comparison, the recommended
    # supplier logic, and the award wizard must match on this field, never
    # on product_id alone.
    multi_rfq_line_id = fields.Many2one(
        'purchase.multi.rfq.line',
        string='Multi RFQ Line',
        ondelete='set null',
        index=True,
        copy=False,
    )
