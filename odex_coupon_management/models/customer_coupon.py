# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta


class CustomerCoupon(models.Model):
    _name = 'customer.coupon'
    _description = 'Customer Coupon'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'id desc'

    name = fields.Char(
        string='Coupon Number', readonly=True, copy=False,
        default='New', tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('posted', 'Posted'),
        ('partially_used', 'Partially Used'),
        ('used', 'Used'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)

    payment_status = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    ], string='Payment Status', default='unpaid', tracking=True,
       compute='_compute_payment_status', store=True)

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    # ── Customer Details ──────────────────────────────────────────────────
    customer_id = fields.Many2one(
        'res.partner', string='Customer Name', required=True, tracking=True,
    )
    mobile = fields.Char(
        string='Contact Number',
        compute='_compute_customer_details', store=True, readonly=False,
    )
    alternate_mobile = fields.Char(string='Alternate Number')
    tag_ids = fields.Many2many(
        'res.partner.category', string='Tags',
    )

    # ── Vehicle Details ───────────────────────────────────────────────────
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', tracking=True,
    )
    plate_number = fields.Char(
        string='License Plate',
        compute='_compute_vehicle_details', store=True, readonly=False,
    )
    vehicle_make_id = fields.Many2one(
        'fleet.vehicle.model.brand', string='Vehicle Make',
        compute='_compute_vehicle_details', store=True, readonly=False,
    )
    vehicle_model_id = fields.Many2one(
        'fleet.vehicle.model', string='Model',
        compute='_compute_vehicle_details', store=True, readonly=False,
    )
    chassis_no = fields.Char(
        string='Chassis No.',
        compute='_compute_vehicle_details', store=True, readonly=False,
    )
    colour = fields.Char(
        string='Colour',
        compute='_compute_vehicle_details', store=True, readonly=False,
    )
    engine_no = fields.Char(string='Engine No.')
    year = fields.Integer(
        string='Year',
        compute='_compute_vehicle_details', store=True, readonly=False,
    )
    odometer = fields.Float(string='Odometer Reading')

    # ── Coupon / Package Details ──────────────────────────────────────────
    coupon_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom'),
        ('service_package', 'Service Package'),
    ], string='Coupon Type', tracking=True)

    coupon_master_id = fields.Many2one(
        'coupon.master', string='Coupon Master', tracking=True,
    )
    description = fields.Text(string='Description')
    start_date = fields.Date(
        string='Start Date', default=fields.Date.today, tracking=True,
    )
    expiry_date = fields.Date(string='Expiry Date', tracking=True)
    validity_days = fields.Integer(
        string='Validity (Days)',
        compute='_compute_validity_days', store=True,
    )
    coupon_amount = fields.Monetary(
        string='Coupon Amount', currency_field='currency_id', tracking=True,
    )
    remaining_amount = fields.Monetary(
        string='Remaining Amount', currency_field='currency_id',
        compute='_compute_amounts', store=True,
    )
    utilized_amount = fields.Monetary(
        string='Utilized Amount', currency_field='currency_id',
        compute='_compute_amounts', store=True,
    )
    allowed_service_ids = fields.Many2many(
        'product.product',
        'customer_coupon_service_rel', 'coupon_id', 'product_id',
        string='Allowed Services',
        domain=[('type', 'in', ['service', 'consu'])],
    )

    # ── Payment Totals ────────────────────────────────────────────────────
    total_paid_amount = fields.Monetary(
        string='Total Paid Amount', currency_field='currency_id',
        compute='_compute_payment_totals', store=True,
    )
    balance_amount = fields.Monetary(
        string='Balance Amount', currency_field='currency_id',
        compute='_compute_payment_totals', store=True,
    )

    # ── Relations ─────────────────────────────────────────────────────────
    payment_ids = fields.One2many(
        'customer.coupon.payment', 'coupon_id', string='Payments',
        domain=[('payment_type', '=', 'regular')],
    )
    pdc_payment_ids = fields.One2many(
        'customer.coupon.payment', 'coupon_id', string='PDC Payments',
        domain=[('payment_type', '=', 'pdc')],
    )
    usage_ids = fields.One2many(
        'customer.coupon.usage', 'coupon_id', string='Usage History',
    )
    move_ids = fields.One2many(
        'account.move', 'coupon_id', string='Journal Entries',
        domain=[('move_type', '=', 'entry')],
    )
    invoice_ids = fields.One2many(
        'account.move', 'coupon_id', string='Invoice History',
        domain=[('move_type', 'in', ['out_invoice', 'out_refund'])],
    )

    # ── Smart button counts ───────────────────────────────────────────────
    payment_count = fields.Integer(compute='_compute_counts')
    usage_count = fields.Integer(compute='_compute_counts')
    invoice_count = fields.Integer(compute='_compute_counts')
    journal_entry_count = fields.Integer(compute='_compute_counts')

    has_outstanding_credits = fields.Boolean(
        compute='_compute_outstanding_credits',
    )
    service_count = fields.Integer(
        string='No. of Services',related='coupon_master_id.allowed_services_count',
        store=True,
    )
    used_service_count = fields.Integer(
        compute='_compute_coupon_service_count'
    )

    remaining_service_count = fields.Integer(
        compute='_compute_coupon_service_count'
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Customer Invoice',
        readonly=True,
        copy=False,
    )
    pdc_account_payment_ids = fields.One2many(
        'pdc.account.payment',
        'coupon_id',
        string='PDC Payments',
    )

    pdc_count = fields.Integer(
        compute='_compute_counts'
    )

    def _compute_counts(self):
        for rec in self:
            print("Inio98uoijklsdsdds")
            rec.payment_count = len(rec.payment_ids) + len(rec.pdc_payment_ids)
            rec.usage_count = len(rec.usage_ids)
            rec.invoice_count = len(rec.invoice_ids)
            rec.journal_entry_count = len(rec.move_ids)
            rec.pdc_count = len(rec.pdc_account_payment_ids)
            print("Inio98uoijklsffdsdds",rec.pdc_count )


    def action_view_coupon_pdc_payments(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('PDC Payments'),
            'res_model': 'pdc.account.payment',
            'view_mode': 'list,form',
            'domain': [('coupon_id', '=', self.id)],
        }

    @api.depends('usage_ids')
    def _compute_coupon_service_count(self):
        for rec in self:
            rec.used_service_count = len(set(rec.usage_ids.mapped('job_id').ids))

            rec.remaining_service_count = (
                    rec.coupon_master_id.allowed_services_count
                    - rec.used_service_count
            )

    # ── Computes ──────────────────────────────────────────────────────────

    # @api.depends('allowed_service_ids')
    # def _compute_service_count(self):
    #     for rec in self:
    #         rec.service_count = rec.coupon_master_id.allowed_services_count

    @api.depends('customer_id')
    def _compute_customer_details(self):
        for rec in self:
            if rec.customer_id:
                rec.mobile = rec.customer_id.mobile or rec.customer_id.phone or ''
            else:
                rec.mobile = ''

    @api.depends('vehicle_id')
    def _compute_vehicle_details(self):
        for rec in self:
            v = rec.vehicle_id
            if v:
                rec.plate_number = v.license_plate or ''
                rec.vehicle_make_id = v.model_id.brand_id if v.model_id else False
                rec.vehicle_model_id = v.model_id if v.model_id else False
                rec.chassis_no = v.vin_sn or ''
                rec.colour = v.color or ''
                rec.year = v.model_year or 0
            else:
                rec.plate_number = ''
                rec.vehicle_make_id = False
                rec.vehicle_model_id = False
                rec.chassis_no = ''
                rec.colour = ''
                rec.year = 0

    @api.depends('start_date', 'expiry_date')
    def _compute_validity_days(self):
        for rec in self:
            if rec.start_date and rec.expiry_date:
                rec.validity_days = (rec.expiry_date - rec.start_date).days
            else:
                rec.validity_days = 0

    @api.depends('usage_ids.amount', 'coupon_amount')
    def _compute_amounts(self):
        for rec in self:
            utilized = sum(rec.usage_ids.mapped('amount'))
            rec.utilized_amount = utilized
            rec.remaining_amount = rec.coupon_amount - utilized

    @api.depends(
        'payment_ids.amount', 'payment_ids.state',
        'pdc_payment_ids.amount', 'pdc_payment_ids.state',
        'coupon_amount',
    )
    def _compute_payment_totals(self):
        for rec in self:
            paid = sum(
                p.amount for p in rec.payment_ids if p.state == 'posted'
            ) + sum(
                p.amount for p in rec.pdc_payment_ids if p.state == 'posted'
            )
            rec.total_paid_amount = paid
            rec.balance_amount = rec.coupon_amount - paid

    @api.depends(
        'payment_ids.amount', 'payment_ids.state',
        'pdc_payment_ids.amount', 'pdc_payment_ids.state',
        'coupon_amount',
    )
    def _compute_payment_status(self):
        for rec in self:
            paid = sum(
                p.amount for p in rec.payment_ids if p.state == 'posted'
            ) + sum(
                p.amount for p in rec.pdc_payment_ids if p.state == 'posted'
            )
            if paid <= 0:
                rec.payment_status = 'unpaid'
            elif paid >= rec.coupon_amount:
                rec.payment_status = 'paid'
            else:
                rec.payment_status = 'partial'

    # def _compute_counts(self):
    #     for rec in self:
    #         rec.payment_count = len(rec.payment_ids) + len(rec.pdc_payment_ids)
    #         rec.usage_count = len(rec.usage_ids)
    #         rec.invoice_count = len(rec.invoice_ids)
    #         rec.journal_entry_count = len(rec.move_ids)

    @api.depends('customer_id')
    def _compute_outstanding_credits(self):
        for rec in self:
            if rec.customer_id and rec.id:
                credits = self.search([
                    ('customer_id', '=', rec.customer_id.id),
                    ('remaining_amount', '>', 0),
                    ('state', 'not in', ['cancelled', 'expired', 'used']),
                    ('id', '!=', rec.id),
                ])
                rec.has_outstanding_credits = bool(credits)
            else:
                rec.has_outstanding_credits = False

    # ── Onchange ──────────────────────────────────────────────────────────

    @api.onchange('coupon_master_id')
    def _onchange_coupon_master_id(self):
        if self.coupon_master_id:
            m = self.coupon_master_id
            self.coupon_type = m.coupon_type
            self.coupon_amount = m.amount
            self.currency_id = m.currency_id
            self.description = m.description
            self.allowed_service_ids = m.allowed_service_ids
            if m.auto_expiry and self.start_date and m.duration_days:
                self.expiry_date = self.start_date + timedelta(days=m.duration_days)

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if (self.coupon_master_id
                and self.coupon_master_id.auto_expiry
                and self.start_date
                and self.coupon_master_id.duration_days):
            self.expiry_date = self.start_date + timedelta(
                days=self.coupon_master_id.duration_days
            )

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id and self.vehicle_id.partner_id:
            self.customer_id = self.vehicle_id.partner_id

    # ── CRUD ──────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('customer.coupon') or 'New'
                )
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                continue

            # Coupon Product
            product = self.env['product.product'].search([
                ('name', '=', 'Coupon')
            ], limit=1)

            if not product:
                raise UserError(_("Coupon product not found."))

            # Create Customer Invoice
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': rec.customer_id.id,
                'coupon_id': rec.id,
                'invoice_date': fields.Date.today(),
                'invoice_origin': rec.name,
                'invoice_line_ids': [(0, 0, {
                    'product_id': product.id,
                    'name': rec.name,
                    'quantity': 1,
                    'price_unit': rec.coupon_amount,
                })]
            })

            invoice.action_post()

            rec.write({
                'invoice_id': invoice.id,
                'state': 'confirmed',
            })

            rec.message_post(
                body=_(
                    'Coupon confirmed. Invoice %s created.'
                ) % invoice.name
            )
    # ── Button Actions ────────────────────────────────────────────────────
    # def action_confirm(self):
    #     for rec in self:
    #         if rec.state != 'draft':
    #             continue
    #
    #         # Get configured coupon liability account
    #         coupon_account_id = int(
    #             self.env['ir.config_parameter'].sudo().get_param(
    #                 'odex_coupon.coupon_sales_account', 0
    #             )
    #         )
    #
    #         if not coupon_account_id:
    #             raise UserError(_("Please configure Coupon Sales Account."))
    #
    #         coupon_account = self.env['account.account'].browse(coupon_account_id)
    #
    #         # Customer receivable account
    #         receivable_account = rec.customer_id.property_account_receivable_id
    #         config = self._get_accounting_config()
    #         journal = config['default_journal']
    #         if not journal:
    #             raise UserError(_("Please configure Journal."))
    #         move_vals = {
    #             'date': fields.Date.today(),
    #             'ref': rec.name,
    #             'coupon_id': self.id,
    #             'journal_id': journal,
    #             'line_ids': [
    #                 (0, 0, {
    #                     'name': rec.name,
    #                     'partner_id': rec.customer_id.id,
    #                     'account_id': receivable_account.id,
    #                     'debit': rec.remaining_amount,
    #                     'credit': 0.0,
    #                 }),
    #                 (0, 0, {
    #                     'name': rec.name,
    #                     'partner_id': rec.customer_id.id,
    #                     'account_id': coupon_account.id,
    #                     'debit': 0.0,
    #                     'credit': rec.remaining_amount,
    #                 }),
    #             ]
    #         }
    #
    #         move = self.env['account.move'].create(move_vals)
    #         move.action_post()
    #
    #         rec.write({
    #             'state': 'confirmed',
    #             # 'move_id': move.id,
    #         })
    #
    #         rec.message_post(
    #             body=_('Coupon confirmed. Journal Entry %s created.') % move.name
    #         )
    # def action_confirm(self):
    #     for rec in self:
    #         if rec.state == 'draft':
    #             rec.state = 'confirmed'
    #             rec.message_post(body=_('Coupon confirmed.'))

    def action_post(self):
        for rec in self:
            if rec.state == 'confirmed':
                rec.state = 'posted'
                rec.message_post(body=_('Coupon posted.'))

    def action_cancel(self):
        for rec in self:
            if rec.state not in ('used', 'expired'):
                rec.state = 'cancelled'
                rec.message_post(body=_('Coupon cancelled.'))

    def action_reset_draft(self):
        for rec in self:
            if rec.state in ('confirmed', 'cancelled'):
                rec.state = 'draft'
                rec.message_post(body=_('Coupon reset to draft.'))

    def action_pay(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Payment'),
            'res_model': 'coupon.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_coupon_id': self.id,
                'default_amount': self.balance_amount,
                'default_payment_type': 'regular',
            },
        }

    # def action_pdc_payment(self):
    #     self.ensure_one()
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': _('PDC Payment'),
    #         'res_model': 'coupon.payment.wizard',
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': {
    #             'default_coupon_id': self.id,
    #             'default_amount': self.balance_amount,
    #             'default_payment_type': 'pdc',
    #             'default_payment_method': 'pdc',
    #         },
    #     }
    def action_pdc_payment(self):
        self.ensure_one()

        if not self.invoice_id:
            raise UserError(_("No invoice found for this coupon."))

        return self.invoice_id.action_invoice_pdc_register_payment()

    def action_view_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('coupon_id', '=', self.id),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
            ],
        }

    def action_view_journal_entries(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entries'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('coupon_id', '=', self.id),
                ('move_type', '=', 'entry'),
            ],
        }

    def action_print_coupon(self):
        return self.env.ref(
            'odex_coupon_management.action_report_customer_coupon'
        ).report_action(self)

    # ── State helpers ─────────────────────────────────────────────────────

    def _update_state_from_usage(self):
        for rec in self:
            if rec.remaining_amount <= 0:
                rec.state = 'used'
            elif rec.utilized_amount > 0 and rec.state == 'posted':
                rec.state = 'partially_used'

    def check_expiry(self):
        today = fields.Date.today()
        self.search([
            ('state', 'not in', ['expired', 'cancelled', 'used']),
            ('expiry_date', '<', today),
        ]).write({'state': 'expired'})

    # ── Accounting helpers ────────────────────────────────────────────────

    def _get_accounting_config(self):
        cfg = self.env['ir.config_parameter'].sudo()
        def _int(key):
            v = cfg.get_param(key, 0)
            try:
                return int(v) if v else 0
            except (ValueError, TypeError):
                return 0
        return {
            'unearned_revenue_account': _int('odex_coupon.unearned_revenue_account'),
            'coupon_sales_account': _int('odex_coupon.coupon_sales_account'),
            'pdc_account': _int('odex_coupon.pdc_account'),
            'default_journal': _int('odex_coupon.default_journal'),
            'vat_tax': _int('odex_coupon.vat_tax'),
        }

    def action_create_accounting_entry(self, payment):
        """Create Dr Cash/Bank/PDC  Cr Unearned Revenue journal entry."""
        self.ensure_one()
        config = self._get_accounting_config()
        journal = payment.journal_id

        unearned_id = config['unearned_revenue_account']
        if not unearned_id:
            # fallback: find any deferred-revenue type account
            acc = self.env['account.account'].search([
                ('account_type', 'in', ['liability_current']),
                ('company_ids', 'in', self.company_id.id),
            ], limit=1)
            unearned_id = acc.id if acc else False

        if not unearned_id:
            raise UserError(_(
                'Please configure the Unearned Revenue Account in '
                'Coupon Management → Configuration → Settings.'
            ))

        if payment.payment_type == 'pdc':
            debit_id = config['pdc_account']
            if not debit_id:
                acc = self.env['account.account'].search([
                    ('account_type', '=', 'asset_receivable'),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)
                debit_id = acc.id if acc else False
        else:
            debit_id = journal.default_account_id.id

        if not debit_id:
            raise UserError(_(
                'Could not determine the debit account. '
                'Please set a default account on journal "%s".'
            ) % journal.name)
        receivable_id = self.customer_id.property_account_receivable_id.id
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': payment.payment_date,
            'ref': _('Coupon Payment: %s') % self.name,
            'coupon_id': self.id,
            'line_ids': [
                (0, 0, {
                    'account_id': debit_id,
                    'debit': payment.amount,
                    'credit': 0.0,
                    'name': _('Coupon Payment - %s') % self.name,
                    'partner_id': self.customer_id.id,
                }),
                (0, 0, {
                    'account_id': receivable_id,
                    'debit': 0.0,
                    'credit': payment.amount,
                    'name': _('Unearned Revenue - %s') % self.name,
                    'partner_id': self.customer_id.id,
                }),
            ],
        })
        move.action_post()
        return move
class PdcAccountPayment(models.Model):
    _inherit = 'pdc.account.payment'

    coupon_id = fields.Many2one(
        'customer.coupon',
        string='Coupon',
        compute='_compute_coupon_id',
        store=True,
    )

    @api.depends('invoice_ids')
    def _compute_coupon_id(self):
        for rec in self:
            invoice = rec.invoice_ids[:1]
            rec.coupon_id = invoice.coupon_id.id if invoice and invoice.coupon_id else False

    def validate_pdc_payment(self):
        res = super().validate_pdc_payment()

        for rec in self:
            for invoice in rec.invoice_ids:
                if invoice.coupon_id:
                    invoice.coupon_id.state = 'posted'

        return res