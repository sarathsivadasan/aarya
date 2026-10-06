# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GatePass(models.Model):
    _name = 'fleet.gate.pass'
    _description = "Fleet Gate Pass"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc'

    # ------------------------------------------------------------------
    # Identification / lifecycle
    # ------------------------------------------------------------------
    name = fields.Char(string='Number', index=True, readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, index=True,
        default=lambda self: self.env.company)
    state = fields.Selection([
        ('in', 'IN'),
        ('revisit', 'Revisit'),
        ('out', 'OUT')],
        default='in', tracking=True, index=True)
    active = fields.Boolean(default=True)
    date_in = fields.Datetime(
        'Date Time In', default=fields.Datetime.now, index=True, tracking=True)
    date_out = fields.Datetime('Date Time Out', tracking=True)
    promise_date = fields.Datetime('Promise Date', tracking=True, index=True)
    approved_id = fields.Many2one(
        'res.users', string="Approved By",
        default=lambda self: self.env.user)
    advisor_id = fields.Many2one(
        'res.users', string="Service Advisor", index=True, tracking=True,
        default=lambda self: self.env.user)
    job_type = fields.Selection([
        ('general_service', 'General Service'),
        ('repair', 'Repair'),
        ('maintenance', 'Maintenance'),
        ('body_paint', 'Body & Paint'),
        ('electrical', 'Electrical'),
        ('other', 'Other')],
        string="Job Type", default='general_service', tracking=True)
    out_reason = fields.Selection([
        ('delivery', 'Delivery'),
        ('revisit', 'Revisit'),
        ('continuation', 'Continuation'),
        ('rework', 'Rework')],
        string="OUT Reason", tracking=True)

    # ------------------------------------------------------------------
    # Customer
    # ------------------------------------------------------------------
    partner_id = fields.Many2one(
        'res.partner', string="Customer Name", index=True, tracking=True)
    partner_phone = fields.Char(
        string="Mobile No.", related="partner_id.phone", store=True)
    partner_email = fields.Char(
        string="Email ID", related="partner_id.email", store=True)
    partner_address = fields.Char(
        string="Address", compute="_compute_partner_address")
    whatsapp_number = fields.Char(string="WhatsApp")
    alternate_contact = fields.Char(string="Alternative Contact")
    alternate_mobile = fields.Char(string="Mobile No.")
    customer_type = fields.Selection([
        ('existing', 'Existing Customer'),
        ('walkin', 'Walk-in')],
        string="Customer Type", default='walkin', index=True)

    # ------------------------------------------------------------------
    # Driver (optional)
    # ------------------------------------------------------------------
    driver_name = fields.Char(string="Driver Name")
    driver_license_no = fields.Char(string="License No.")
    driver_license_expiry = fields.Date(string="License Expiry")
    driver_mobile = fields.Char(string="Driver Mobile")

    # ------------------------------------------------------------------
    # Vehicle (m2o + snapshot fields: data as-received for history)
    # ------------------------------------------------------------------
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string="Registration Number", index=True, tracking=True)
    registration_no = fields.Char(string="Registration No.", index=True)
    vin = fields.Char(string="VIN / Chassis No.", index=True)
    engine_no = fields.Char(string="Engine No.")
    brand_id = fields.Many2one(
        'fleet.vehicle.model.brand', related="vehicle_id.vehicle_make_id",
        store=True, string="Brand")
    model_id = fields.Many2one(
        "fleet.vehicle.model", related="vehicle_id.model_id",
        store=True, string="Model")
    vehicle_color_id = fields.Many2one(
        'vehicle.color', string="Colors", related="vehicle_id.color_id",
        store=True)
    variant = fields.Char(string="Variant")
    manufacturing_year = fields.Char(string="Manufacturing Year")
    fuel_type = fields.Selection([
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('hybrid', 'Hybrid'),
        ('electric', 'Electric'),
        ('lpg', 'LPG'),
        ('other', 'Other')],
        string="Fuel Type")
    transmission = fields.Selection([
        ('automatic', 'Automatic'),
        ('manual', 'Manual'),
        ('cvt', 'CVT')],
        string="Transmission")
    engine_capacity = fields.Char(string="Engine Capacity")
    plate_source = fields.Char(string="Plate Source")
    odometer = fields.Float(string="Odometer (KM)")

    # ------------------------------------------------------------------
    # Vehicle condition
    # ------------------------------------------------------------------
    fuel_level = fields.Selection([
        ('0', 'Empty'),
        ('1', '1/4'),
        ('2', '1/2'),
        ('3', '3/4'),
        ('4', 'Full')],
        string="Fuel Level", default='2')
    visible_damage = fields.Boolean(string="Visible Damage")
    tyre_condition = fields.Selection([
        ('good', 'Good'),
        ('average', 'Average'),
        ('poor', 'Poor')],
        string="Tyre Condition", default='good')
    accessories = fields.Char(string="Accessories")
    condition_remarks = fields.Text(string="Remarks")
    customer_complaint = fields.Text(string="Customer Complaints", tracking=True)
    condition_video = fields.Binary(string="Condition Video", attachment=True)
    condition_video_filename = fields.Char()

    # ------------------------------------------------------------------
    # Media / damage map / signature
    # ------------------------------------------------------------------
    image_ids = fields.One2many(
        'fleet.gate.pass.image', 'gate_pass_id', string="Vehicle Images")
    damage_ids = fields.One2many(
        'fleet.gate.pass.damage', 'gate_pass_id', string="Damage Markers")
    signature = fields.Binary(string="Customer Signature", copy=False)
    signature_date = fields.Datetime(string="Signed On", copy=False)
    signature_user_id = fields.Many2one(
        'res.users', string="Collected By", copy=False)

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------
    note = fields.Html(string="Internal Notes")
    customer_note = fields.Html(string="Customer Notes")

    # ------------------------------------------------------------------
    # Booking integration (soft link until booking model bridge restored)
    # ------------------------------------------------------------------
    booking_ref = fields.Char(string="Booking No.", index=True, copy=False)

    # ------------------------------------------------------------------
    # Linked workshop documents
    # ------------------------------------------------------------------
    task_ids = fields.One2many('project.task', 'gate_pass_id', string="Tasks")
    sale_order_ids = fields.One2many(
        'sale.order', 'gate_pass_id', string="Estimates")
    invoice_ids = fields.One2many(
        'account.move', 'gate_pass_id', string="Invoices",
        domain=[('move_type', '=', 'out_invoice')])
    log_ids = fields.One2many(
        'fleet.gate.pass.log', 'gate_pass_id', string="Entry / Exit Logs")
    timeline_ids = fields.One2many(
        'fleet.gate.pass.timeline', 'gate_pass_id', string="Timeline")

    # ------------------------------------------------------------------
    # Synced statuses (stored computes -> dashboard/list are index-fast)
    # ------------------------------------------------------------------
    estimate_status = fields.Selection([
        ('none', '-'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')],
        string="Estimation", compute="_compute_doc_statuses",
        store=True, index=True)
    job_card_status = fields.Selection([
        ('none', '-'),
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')],
        string="Job Card", compute="_compute_doc_statuses",
        store=True, index=True)
    invoice_status = fields.Selection([
        ('none', '-'),
        ('generated', 'Generated'),
        ('paid', 'Paid')],
        string="Invoice", compute="_compute_doc_statuses",
        store=True, index=True)
    vehicle_status = fields.Selection([
        ('in_workshop', 'In Workshop'),
        ('waiting_approval', 'Waiting Approval'),
        ('repair_in_progress', 'Repair in Progress'),
        ('invoice_ready', 'Invoice Ready'),
        ('ready_for_delivery', 'Ready for Delivery'),
        ('delivered', 'Delivered'),
        ('revisit', 'Revisit / Rework')],
        string="Vehicle Status", compute="_compute_vehicle_status",
        store=True, index=True, tracking=True)
    payment_status = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('paid', 'Paid')],
        string="Payment Status", compute="_compute_doc_statuses",
        store=True, index=True)

    is_overdue = fields.Boolean(
        string="Promise Overdue", compute="_compute_is_overdue",
        search="_search_is_overdue")

    # Smart-button counters
    job_card_count = fields.Integer(compute="_compute_counts", string="Job Cards")
    estimate_count = fields.Integer(compute="_compute_counts", string="Quotations")
    invoice_count = fields.Integer(compute="_compute_counts", string="Invoices")
    history_count = fields.Integer(compute="_compute_counts", string="Vehicle History")

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)',
         'Gate Pass number must be unique per company.'),
    ]

    # ==================================================================
    # Computes
    # ==================================================================
    def _compute_partner_address(self):
        for rec in self:
            p = rec.partner_id
            rec.partner_address = ", ".join(
                filter(None, [p.street, p.street2, p.city, p.country_id.name])
            ) if p else False

    @api.depends('task_ids', 'task_ids.state', 'task_ids.is_jobcard',
                 'sale_order_ids', 'sale_order_ids.state',
                 'invoice_ids', 'invoice_ids.state',
                 'invoice_ids.payment_state')
    def _compute_doc_statuses(self):
        for rec in self:
            job_cards = rec.task_ids.filtered('is_jobcard')
            estimates = rec.sale_order_ids
            invoices = rec.invoice_ids.filtered(
                lambda m: m.state != 'cancel')

            # Estimation
            if not estimates:
                rec.estimate_status = 'none'
            elif any(so.state == 'sale' for so in estimates):
                rec.estimate_status = 'approved'
            elif all(so.state == 'cancel' for so in estimates):
                rec.estimate_status = 'rejected'
            else:
                rec.estimate_status = 'pending'

            # Job card
            if not job_cards:
                rec.job_card_status = 'none'
            elif all(t.state in ('1_done', '1_canceled') for t in job_cards):
                rec.job_card_status = 'completed'
            elif any(t.state == '01_in_progress' for t in job_cards):
                rec.job_card_status = 'in_progress'
            else:
                rec.job_card_status = 'open'

            # Invoice + payment
            posted = invoices.filtered(lambda m: m.state == 'posted')
            # Payment is binary: Paid only when every posted customer
            # invoice is fully paid; anything else (no invoice, unpaid,
            # partial) is Not Paid.
            if not posted:
                rec.invoice_status = 'none'
                rec.payment_status = 'not_paid'
            elif all(m.payment_state in ('paid', 'in_payment', 'reversed')
                     for m in posted):
                rec.invoice_status = 'paid'
                rec.payment_status = 'paid'
            else:
                rec.invoice_status = 'generated'
                rec.payment_status = 'not_paid'

    @api.depends('state', 'out_reason', 'estimate_status',
                 'job_card_status', 'invoice_status', 'payment_status')
    def _compute_vehicle_status(self):
        for rec in self:
            if rec.state == 'out':
                rec.vehicle_status = 'delivered'
            elif rec.state == 'revisit':
                rec.vehicle_status = 'revisit'
            elif rec.invoice_status == 'paid':
                rec.vehicle_status = 'ready_for_delivery'
            elif rec.invoice_status == 'generated':
                rec.vehicle_status = 'invoice_ready'
            elif rec.job_card_status in ('open', 'in_progress'):
                rec.vehicle_status = 'repair_in_progress'
            elif rec.job_card_status == 'completed':
                rec.vehicle_status = 'invoice_ready'
            elif rec.estimate_status == 'pending':
                rec.vehicle_status = 'waiting_approval'
            else:
                rec.vehicle_status = 'in_workshop'

    @api.depends('promise_date', 'state')
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_overdue = bool(
                rec.promise_date and rec.promise_date < now
                and rec.state != 'out')

    def _search_is_overdue(self, operator, value):
        domain = [('promise_date', '<', fields.Datetime.now()),
                  ('state', '!=', 'out')]
        if (operator == '=' and value) or (operator == '!=' and not value):
            return domain
        return ['!'] + domain

    def _compute_counts(self):
        for rec in self:
            rec.job_card_count = len(rec.task_ids.filtered('is_jobcard'))
            rec.estimate_count = len(rec.sale_order_ids)
            rec.invoice_count = len(rec.invoice_ids)
            rec.history_count = self.search_count([
                ('vehicle_id', '=', rec.vehicle_id.id),
                ('id', '!=', rec.id),
            ]) if rec.vehicle_id else 0

    # ==================================================================
    # ORM
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = seq.next_by_code('gate.pass.seq')
        records = super().create(vals_list)
        for rec in records:
            rec._create_log('in', _("Gate Pass created"))
            rec._log_timeline('gate_pass_in')
        return records

    @api.onchange('vehicle_id')
    def onchange_vehicle_id(self):
        for rec in self:
            v = rec.vehicle_id
            if not v:
                continue
            if v.partner_id:
                rec.partner_id = v.partner_id.id
                rec.customer_type = 'existing'
            rec.registration_no = v.license_plate
            rec.vin = v.vin_sn
            if not rec.odometer:
                rec.odometer = v.odometer

    @api.onchange('partner_id')
    def _onchange_partner_type(self):
        for rec in self:
            if rec.partner_id and not rec._origin.partner_id:
                prior = self.search_count([
                    ('partner_id', '=', rec.partner_id.id)])
                rec.customer_type = 'existing' if prior else 'walkin'

    # ==================================================================
    # Workflow actions
    # ==================================================================
    def vehicle_out(self):
        for rec in self:
            if rec.state == 'out':
                raise UserError(_("Gate Pass %s is already OUT.") % rec.name)
            rec.write({
                'date_out': fields.Datetime.now(),
                'state': 'out',
                'out_reason': rec.out_reason or 'delivery',
            })
            rec._create_log('out', _("Vehicle OUT (%s)") % dict(
                rec._fields['out_reason'].selection).get(rec.out_reason, ''))
            rec._log_timeline('gate_pass_out')

    def vehicle_revisit(self):
        for rec in self:
            rec.write({'state': 'revisit', 'date_out': False})
            rec._create_log('revisit', _("Vehicle revisit"))
            rec._log_timeline('revisit')

    def action_sign(self):
        for rec in self:
            if rec.signature and not rec.signature_date:
                rec.write({
                    'signature_date': fields.Datetime.now(),
                    'signature_user_id': self.env.user.id,
                })

    # ------------------------------------------------------------------
    # Logs / timeline helpers
    # ------------------------------------------------------------------
    def _create_log(self, log_type, remarks=False):
        self.ensure_one()
        self.env['fleet.gate.pass.log'].sudo().create({
            'gate_pass_id': self.id,
            'log_type': log_type,
            'user_id': self.env.user.id,
            'advisor_id': self.advisor_id.id,
            'remarks': remarks or False,
        })

    def _log_timeline(self, event, note=False):
        """Idempotent per (gate pass, event) unless repeated events allowed."""
        self.ensure_one()
        Timeline = self.env['fleet.gate.pass.timeline'].sudo()
        repeatable = ('revisit', 'gate_pass_out', 'gate_pass_in')
        if event not in repeatable and Timeline.search_count([
                ('gate_pass_id', '=', self.id), ('event', '=', event)]):
            return
        Timeline.create({
            'gate_pass_id': self.id,
            'event': event,
            'user_id': self.env.user.id,
            'note': note or False,
        })

    # ==================================================================
    # Smart button / navigation actions
    # ==================================================================
    def _base_action(self, name, res_model, domain, context=None):
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'view_mode': 'list,form',
            'domain': domain,
            'context': context or {},
        }

    def action_view_job_card(self):
        self.ensure_one()
        job_cards = self.task_ids.filtered('is_jobcard')
        return self._base_action(
            _('Job Cards'), 'project.task',
            [('id', 'in', job_cards.ids)],
            {'default_is_jobcard': True,
             'default_gate_pass_id': self.id,
             'default_vehicle_id': self.vehicle_id.id,
             'default_partner_id': self.partner_id.id})

    def action_view_estimates(self):
        self.ensure_one()
        return self._base_action(
            _('Quotations'), 'sale.order',
            [('id', 'in', self.sale_order_ids.ids)],
            {'default_gate_pass_id': self.id,
             'default_partner_id': self.partner_id.id})

    def action_view_invoices(self):
        self.ensure_one()
        return self._base_action(
            _('Invoices'), 'account.move',
            [('id', 'in', self.invoice_ids.ids)],
            {'default_move_type': 'out_invoice',
             'default_gate_pass_id': self.id,
             'default_partner_id': self.partner_id.id})

    def action_view_history(self):
        self.ensure_one()
        return self._base_action(
            _('Vehicle History'), 'fleet.gate.pass',
            [('vehicle_id', '=', self.vehicle_id.id),
             ('id', '!=', self.id)])
