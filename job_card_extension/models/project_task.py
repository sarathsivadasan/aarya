from datetime import date, datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from collections import defaultdict

class Task(models.Model):
    _inherit = "project.task"

    def _get_default_stage_id(self):
        return self.env['job.card.stage'].search([], limit=1)

    @api.model
    def _default_company_id(self):
        if self._context.get('default_project_id'):
            return self.env['project.project'].browse(self._context['default_project_id']).company_id
        if self._context.get('default_is_jobcard'):
            return self.env.company

    # name = fields.Char(string='Title', tracking=True)
    cc_partner_phone = fields.Char(string="Contact Number", related="partner_id.phone", store=True)
    cc_partner_mobile = fields.Char(string="Alternate Number", related="partner_id.mobile", store=True)
    # cc_vehicle = fields.Many2one("fleet.vehicle", string="Vehicle",store=True, context="{'reg_no': True}", domain="")
    repair_sub_category_ids = fields.Many2many('repair.sub.category.custom', 'repair_sub_category_custom_task_rel',
                                               'sub_category_id', 'task_id', string="Job Type")
    warranty = fields.Many2one("job.card.warranty", string="Warranty")
    insurance_company_id = fields.Many2one('res.partner', string='Insurance Company', auto_join=True, tracking=True,
                                           domain="[('is_insurance', '=', True)]")
    policy_no = fields.Char("Policy Number")
    lpo_no = fields.Char("LPO Number")
    lpo_date = fields.Date("LPO Date")
    claim_no = fields.Char("Claim No.")
    promise_date = fields.Date("Promise Date")
    next_service_date = fields.Date('Next Service Date')
    final_inspection = fields.Boolean(string="Final Inspection", track_visibility='always')
    cc_stage_id = fields.Many2one('job.card.stage', string="Stage", default=_get_default_stage_id, track_visibility='always')
    cc_stage_value = fields.Char(string="Stage Value", related="cc_stage_id.value")
    cc_color = fields.Integer(string="Color", compute="get_color", store=True)
    requested_services_ids = fields.One2many('job.requested.service', 'task_id', 'Requested Services')
    # work_description_ids = fields.One2many('job.work.description', 'task_id', 'Work Description')
    company_id = fields.Many2one('res.company', string='Company', compute='_compute_company_id', store=True, readonly=False, recursive=True, copy=True, default=_default_company_id)
    quality_checklist_ids = fields.One2many('quality.checklist', 'job_card_id',
                                            string="Quality Checklist", default=lambda x: x.get_quality_checklist())
    ins_quality_checklist_ids = fields.One2many('ins.qc.checklist', 'job_card_id',
                                            string="Inspection Quality Checklist", default=lambda x: x.get_ins_quality_checklist())
    advance_payment_count = fields.Integer(string="Advance Payment Count", compute="count_advance_payment")
    last_update_status = fields.Selection(related="project_id.last_update_status")
    last_update_color = fields.Integer(related="project_id.last_update_color")

    use_coupon = fields.Boolean(string="Use Coupon")
    # gate_pass_id = fields.Many2one('fleet.gate.pass', string="Gate Pass")
    customer_coupon_id = fields.Many2one(
        'customer.coupon',
        string='Customer Coupon',   domain="""
        [
            ('vehicle_id', '=', vehicle_id),
            ('state', 'in', ['posted', 'partially_used']),
            ('remaining_amount', '>', 0)
        ]
    """
    )

    coupon_type = fields.Selection(
        related='customer_coupon_id.coupon_type',
        readonly=True
    )

    coupon_master_id = fields.Many2one(
        related='customer_coupon_id.coupon_master_id',
        readonly=True
    )

    allowed_service_ids = fields.Many2many(
        related='customer_coupon_id.allowed_service_ids',
        readonly=True
    )

    remaining_amount = fields.Monetary(
        related='customer_coupon_id.remaining_amount',
        currency_field='currency_id',
        readonly=True
    )

    utilized_amount = fields.Monetary(
        related='customer_coupon_id.utilized_amount',
        currency_field='currency_id',
        readonly=True
    )

    expiry_date = fields.Date(
        related='customer_coupon_id.expiry_date',
        readonly=True
    )

    validity_days = fields.Integer(
        related='customer_coupon_id.validity_days',
        readonly=True
    )

    coupon_status = fields.Selection(
        related='customer_coupon_id.state',
        readonly=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    used_service_count = fields.Integer(
        compute="_compute_coupon_counts"
    )

    remaining_service_count = fields.Integer(
        compute="_compute_coupon_counts"
    )
    job_type = fields.Selection([('redo', 'Redo Job')], string="Job Type")
    # po_id = fields.Many2one('purchase.order', string="Purchase Order")
    bay_id = fields.Many2one('job.card.bay', string="Job Bay")
    customer_waiting = fields.Boolean(string="Customer Waiting")
    # 1. One2many field to track historical bay movements
    bay_log_ids = fields.One2many(
        'job.card.bay.log', 
        'task_id', 
        string="Bay Usage Logs",
        readonly=True
    )
    po_count = fields.Integer(string='PO Count', compute='_compute_po_count')
    inspection_part_ids = fields.One2many(
        "vehicle.inspection.part",
        "inspection_id",
        string="Parts"
    )

    mv_rfq_ids = fields.One2many(
        'purchase.multi.rfq',
        'inspection_id',
        string="MV RFQs"
    )

    mv_rfq_count = fields.Integer(
        compute="_compute_mv_rfq_count",
        string="MV RFQs"
    )

    @api.depends('mv_rfq_ids')
    def _compute_mv_rfq_count(self):
        for rec in self:
            rec.mv_rfq_count = len(rec.mv_rfq_ids)

    def action_create_mv_rfq(self):
        self.ensure_one()

        order_lines = []
        print("order_linesorinspection_part_idsder_lines",  self.inspection_part_ids)
        for part in self.inspection_part_ids:
            if part.is_confirm:
                order_lines.append((0, 0, {
                    'product_id': part.product_id.id,
                    'uom_id': part.product_id.uom_po_id.id,
                    'part_no': part.part_no,
                    'parts_type': part.parts_type,
                    'quantity': part.quantity,
                }))
        print("order_linesorder_lines",order_lines)
        po_multi_rfq_id = self.env['purchase.multi.rfq'].create({
            # 'partner_id': self.partner_id.id,
            'inspection_id': self.id,
            'vehicle_id': self.vehicle_id.id if self.vehicle_id else False,
            # 'origin': self.name,
            'line_ids': order_lines,
        })
        self._add_log(
                 _("MVRFQ Created"),
                _("MVRFQ Created - %s", po_multi_rfq_id.name))
        return po_multi_rfq_id


    def _get_accounting_config(self):
        cfg = self.env['ir.config_parameter'].sudo()

        def _int(key):
            v = cfg.get_param(key, 0)
            try:
                return int(v) if v else 0
            except (ValueError, TypeError):
                return 0

        return {
            'coupon_invoice_account_id': _int('odex_coupon.coupon_invoice_account_id'),
            'coupon_sales_account_id': _int('odex_coupon.coupon_sales_account'),
        }

    @api.depends('customer_coupon_id')
    def _compute_coupon_counts(self):
        for rec in self:
            coupon = rec.customer_coupon_id

            if coupon:
                used = len(set(coupon.usage_ids.mapped('job_id').ids))
                rec.used_service_count = used
                rec.remaining_service_count = (
                        coupon.coupon_master_id.allowed_services_count - used
                )
            else:
                rec.used_service_count = 0
                rec.remaining_service_count = 0

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id_coupon(self):
        self.customer_coupon_id = False

        if not self.vehicle_id:
            return

        partner = self.vehicle_id.partner_id
        if not partner:
            return

        coupon = self.env['customer.coupon'].search([
            ('customer_id', '=', partner.id),
            ('vehicle_id', '=', self.vehicle_id.id),
            ('state', 'in', ['posted', 'partially_used']),
            ('remaining_amount', '>', 0),
        ], limit=1, order='expiry_date asc')

        self.customer_coupon_id = coupon

    def count_advance_payment(self):
        payment = self.env['account.payment'].search([('job_id', '=', self.id)])
        if payment:
            self.advance_payment_count = len(payment)
        else: 
            self.advance_payment_count = 0
    
    @api.depends('cc_stage_id', 'cc_stage_value')
    def get_color(self):
        for rec in self:
            if rec.cc_stage_value == 'in':
                rec.cc_color = 1
            elif rec.cc_stage_value == 'wip':
                rec.cc_color = 2  # Deep Blue
            elif rec.cc_stage_value == 'awaiting_parts':
                rec.cc_color = 3  # Orange
            elif rec.cc_stage_value == 'awaiting_approval':
                rec.cc_color = 4  # Purple
            elif rec.cc_stage_value == 'ready':
                rec.cc_color = 5  # Deep Green
            elif rec.cc_stage_value == 'no_action':
                rec.cc_color = 6  # Yellow
            elif rec.cc_stage_value == 'out':
                rec.cc_color = 7  # Orange
            elif rec.cc_stage_value == 'road_testing':
                rec.cc_color = 8  # Purple
            elif rec.cc_stage_value == 'washing':
                rec.cc_color = 9  # Deep Green
            elif rec.cc_stage_value == 'closed':
                rec.cc_color = 10  # red
            elif rec.cc_stage_value == 'awaiting_payment':
                rec.cc_color = 11  # Brown
            elif rec.cc_stage_value == 'urg':
                rec.cc_color = 12  # Brown
            else:
                rec.cc_color = 0

    @api.onchange('cc_stage_id', 'cc_stage_value')
    def onchange_cc_stage_value(self):
        for rec in self:
            if rec.cc_stage_value == 'closed':
                rec.customer_waiting = False

    def get_ins_quality_checklist(self):
        print("true,,,,,,,,,,")
        ins_quality_lines = []
        ins_checklist_with_serial = [
            (1, 'Registration card validity'),
            (2, 'Wheel caps'),
            (3, 'Spare tyre'),
            (4, 'Jack / tools'),
            (5, 'Wipers'),
            (6, 'Lights'),
            (7, 'Radio antena / function'),
            (8, 'Wind screen / glass'),
            (9, 'A/C Operation / cooling'),
            (10, 'Body scratches / dents'),
            (11, 'Police repair permit (acc. Veh)'),
        ]
        for line in ins_checklist_with_serial:
            vals = {
                'name': line[1],
                'serial_no': line[0],
            }
            ins_quality_lines.append((0, 0, vals))
        print("ins_quality_lines,,,,,,", ins_quality_lines)
        return ins_quality_lines

    def get_quality_checklist(self):
        quality_lines = []
        category_checklist = [
            'Under the Hood',
            'Under the Vehicle',
            'Exterior & Interior',
            'Miscellenous Inspection',
        ]
        quality_checklist_name_obj = self.env['quality.checklist.name']
        for cat in category_checklist:
            exist = quality_checklist_name_obj.search([('name', '=', cat)])
            if not exist:
                quality_checklist_name_obj.create({'name': cat})

        checklist_with_serial = [
            (1, 'Engine Oil', category_checklist[0]),
            (2, 'Transmission Fluid', category_checklist[0]),
            (3, 'Powersteering Fluid', category_checklist[0]),
            (4, 'Engine Coolant', category_checklist[0]),
            (5, 'Hoses & Water Pump', category_checklist[0]),
            (6, 'Drive Belts', category_checklist[0]),
            (7, 'Tensioner & Idler Bearings', category_checklist[0]),
            (8, 'Battery / Water Level / Condition', category_checklist[0]),
            (9, 'A/C System', category_checklist[0]),
            (10, 'Brake Fluid', category_checklist[0]),
            (11, 'Brake Master Cylinder', category_checklist[0]),
            (12, 'Brake Booster', category_checklist[0]),
            (13, 'Clutch Fluid', category_checklist[0]),
            (14, 'Clutch Cables & Linkings', category_checklist[0]),
            (15, 'Engine Oil Leaks', category_checklist[1]),
            (16, 'Transmission Oil Leaks', category_checklist[1]),
            (17, 'Transmission Cooler Pipes & Linkages', category_checklist[1]),
            (18, 'Transfercase Fluid', category_checklist[1]),
            (19, 'Differential Fluid', category_checklist[1]),
            (20, 'Gear Box Oil', category_checklist[1]),
            (21, 'Engine Mounts', category_checklist[1]),
            (22, 'Transmission Mounts', category_checklist[1]),
            (23, 'Exhaust System', category_checklist[1]),
            (24, 'Drive Shafts', category_checklist[1]),
            (25, 'Universal Joints', category_checklist[1]),
            (26, 'C.V. Joints', category_checklist[1]),
            (27, 'Front Shock Absorbers', category_checklist[1]),
            (28, 'Rear Shock Absorbers', category_checklist[1]),
            (29, 'Springs & Mounts', category_checklist[1]),
            (30, 'Upper Arms', category_checklist[1]),
            (31, 'Lower Arms', category_checklist[1]),
            (32, 'Stabilizer Links & Bushes', category_checklist[1]),
            (33, 'Tie Rods', category_checklist[1]),
            (34, 'Steering Rack / Box', category_checklist[1]),
            (35, 'Wheel & Tires (Incl Spare)', category_checklist[1]),
            (36, 'Tyre Pressure (Fill If Less)', category_checklist[1]),
            (37, 'Front Brakes', category_checklist[1]),
            (38, 'Rear Brakes', category_checklist[1]),
            (39, 'Hand Brake', category_checklist[1]),
            (40, 'Panel, Paintwork & Body Fittings', category_checklist[2]),
            (41, 'Windscreen & Other Glass', category_checklist[2]),
            (42, 'Washes & Wipers', category_checklist[2]),
            (43, 'All Lightings', category_checklist[2]),
            (44, 'Horn Tone', category_checklist[2]),
            (45, 'All Instruments & Accessories', category_checklist[2]),
            (46, 'Checked Engine Oil Cap Tighten', category_checklist[3]),
            (47, 'Checked Radiator Cap Tighten', category_checklist[3]),
            (48, 'Checked Brake Fluid Cap Tighten', category_checklist[3]),
            (49, 'Checked for Tools not left in the Vehicle', category_checklist[3]),
            (50, 'Checked for Abnormal Sounds', category_checklist[3]),
        ]
        category_used = []
        for line in checklist_with_serial:
            checklist_type_id = quality_checklist_name_obj.search([('name', '=', line[2])])
            if checklist_type_id.id not in category_used:
                category_used.append(checklist_type_id.id)
                section = {'name': checklist_type_id.name,
                           'display_type': 'line_section',
                           'serial_no': line[0] - 0.1,
                           }
                quality_lines.append((0, 0, section))
            vals = {
                'name': line[1],
                'checklist_name_id': checklist_type_id.id if checklist_type_id else False,
                'serial_no': line[0],
            }
            quality_lines.append((0, 0, vals))

        return quality_lines

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        for rec in result:
            if rec.name and self._context.get('default_is_jobcard') or rec.is_jobcard:
                rec.project_id = rec.project_id.create({
                    'name': rec.name, 
                    'company_id':rec.company_id.id,
                    'partner_id': rec.partner_id.id,
                    'allow_billable': True})
                if not rec.project_id.account_id:
                    rec.project_id._create_analytic_account()
                rec.analytic_account_id = rec.project_id.account_id.id
            if rec.odometer and rec.is_jobcard:
                self.env['fleet.vehicle.odometer'].create({
                    'date': rec.create_date.date(),
                    'vehicle_id': rec.vehicle_id.id,
                    'value': rec.odometer
                    })
            if rec.bay_id:
                if rec.bay_id.is_occupied:
                    raise ValidationError(_("Bay '%s' is already occupied!") % rec.bay_id.name)
                # Mark bay occupied & log entry
                rec.bay_id.is_occupied = True
                self.env['job.card.bay.log'].create({
                    'task_id': rec.id,
                    'bay_id': rec.bay_id.id,
                    'bay_in': fields.Datetime.now(),
                })
        return result 

    def write(self, vals):
        if 'bay_id' in vals:
            new_bay_id = vals['bay_id']
            now = fields.Datetime.now()
            
            for record in self:
                old_bay = record.bay_id
                
                # If changing or clearing the bay, close the open log entry
                if old_bay and (not new_bay_id or old_bay.id != new_bay_id):
                    old_bay.is_occupied = False
                    
                    # Find open log entry (where bay_out is False) and update bay_out
                    open_log = record.bay_log_ids.filtered(lambda l: l.bay_id == old_bay and not l.bay_out)
                    if open_log:
                        open_log.write({'bay_out': now})

                # If setting a new bay
                if new_bay_id and (not old_bay or old_bay.id != new_bay_id):
                    new_bay = self.env['job.card.bay'].browse(new_bay_id)
                    if new_bay.is_occupied:
                        raise ValidationError(_("Bay '%s' is already occupied!") % new_bay.name)
                    
                    new_bay.is_occupied = True
                    
                    # Create a new open log entry
                    self.env['job.card.bay.log'].create({
                        'task_id': record.id,
                        'bay_id': new_bay.id,
                        'bay_in': now,
                    })

        return super(Task, self).write(vals)

    def unlink(self):
        # Close open logs and free bays if Job Card is deleted
        now = fields.Datetime.now()
        for record in self:
            if record.bay_id:
                record.bay_id.is_occupied = False
                open_log = record.bay_log_ids.filtered(lambda l: not l.bay_out)
                if open_log:
                    open_log.write({'bay_out': now})
        return super(Task, self).unlink()

    # Action Button to free the bay manually from the Job Card
    def action_release_bay(self):
        """ Clears bay_id which automatically triggers write() logic to set bay_out """
        for record in self:
            record.bay_id = False


    def show_invoice(self):
        self.ensure_one()
        res = super(Task, self).show_invoice()
        move_type = 'out_invoice'
        if self._context.get('move_type') and self._context.get('move_type') :
            move_type = self._context.get('move_type')
            res['action'] = self.env.ref('account.action_move_in_invoice_type')
        res['context'] =str({
                'default_job_id': self.id,
                'default_move_type': move_type})
        res['domain'] = str([('job_id', '=', self.id), ('move_type', '=', move_type)])
        return res

    def show_bills(self):
        self.ensure_one()
        res = self.show_invoice()
        res['context'] = str({'default_job_id': self.id,
            'default_move_type': 'in_invoice'})
        return res

    def show_invoice_bills_lines(self):
        self.ensure_one()
        return {
            'name': 'Invoice & Bill Lines',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list',
            'views': [(self.env.ref('job_card_extension.view_invoice_bill_lines_list').id, 'list'),
                      (False, 'form')],
            'domain': [
                ('move_id.vehicle_id', '=', self.vehicle_id.id),
                ('move_id.move_type', 'in', ['out_invoice','in_invoice','out_refund','in_refund']),
                ('product_id', '!=', False),],  # exclude journal/tax/receivable lines
            # 'context': {'default_vehicle_id': self.vehicle_id.id},
        }

    def show_hr_expense(self):
        self.ensure_one()
        res = self.env.ref('hr_expense.hr_expense_actions_my_all')
        res = res.sudo().read()[0]
        res['context'] = str({'default_job_id': self.id,
                              'default_vehicle_id': self.vehicle_id.id if self.vehicle_id else None,
                              'default_customer_id': self.partner_id.id if self.partner_id else None,
                              'default_payment_mode': 'company_account',
                             })

        res['domain'] = [('job_id', '=', self.id)]
        return res

    def view_project_dashbord(self):
        if self.project_id:
            action = self.env['ir.actions.act_window']._for_xml_id('project.project_update_all_action')
            action['display_name'] = _("%(name)s Dashboard", name=self.project_id.name)
            action['context'] = self.env.context | {
                'active_model': 'project.project',
                'active_id': self.project_id.id}
            return action

            # print("true,,,", self.project_id)
            # self.project_id.project_update_all_action()

    def action_open_advance_payment(self):
        context = {'default_communication': self.name,
                   'default_job_id': self.id,
        }
        return {
            'name': _('Jobcard Advance Payment'),
            'res_model': 'jobcard.advance.payment.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': context,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def action_redojob(self):
        new_record = self.copy()
        self.job_type = "redo"
        cc_stage_id = self.env['job.card.stage'].search([('value', '=', 'redo')], limit=1)
        new_record.cc_stage_id = cc_stage_id.id if cc_stage_id else False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': new_record.id,
            'target': 'current',
        }

    def open_payments(self):
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_all_payments')
        action["domain"] = [("job_id", "=", self.id)]
        return action

    def create_purchase_order(self):
        self.ensure_one()
    
        # Group line commands by vendor
        vendor_lines = defaultdict(list)
        processed_lines = self.env['job.cost.sheet']
    
        for line in self.job_cost_sheet_ids:
            print("line,,,,,,,vendor_id", line.vendor_id)
            # Check selection and ensure a vendor is defined
            if line.invoice_checkbox and line.vendor_id and not line.is_po_created:
                vendor_lines[line.vendor_id.id].append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_po_id.id,
                    'name': line.product_id.display_name or line.part_no or '/',
                    'product_qty': line.quantity,
                    'part_no': line.part_no,
                    'parts_type': line.parts_type,
                    'price_unit': line.custom_price,
                }))
            # Keep track of this line to update its flag after creation
            processed_lines |= line

        created_po = self.env['purchase.order']
    
        # Create one Purchase Order per vendor
        for partner_id, lines in vendor_lines.items():
            po = self.env['purchase.order'].create({
                'partner_id': partner_id,
                'job_id': self.id,
                'vehicle_id': self.vehicle_id.id if self.vehicle_id else False,
                'origin': self.name,
                'order_line': lines,  # Standard Odoo field is 'order_line'
            })
            created_po |= po
            # self._add_log(
            #      _("Purchase RFQ Created"),
            #      _("Purchase RFQ Created - %s", created_po.name)) 

        # Mark the processed lines as PO Created
        processed_lines.write({'is_po_created': True})

        # Return action based on number of created POs
        if not created_po:
            return False
        else:
            return created_po

        # if len(created_po) == 1:
        #     return {
        #         'type': 'ir.actions.act_window',
        #         'name': 'Purchase Order',
        #         'res_model': 'purchase.order',
        #         'res_id': created_po.id,
        #         'view_mode': 'form',
        #     }

        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Purchase Orders',
        #     'res_model': 'purchase.order',
        #     'domain': [('id', 'in', created_po.ids)],
        #     'view_mode': 'list,form',
        # }

    def _compute_po_count(self):
        for rec in self:
            rec.po_count = self.env['purchase.order'].search_count([
                ('job_id', '=', rec.id)
            ])

    def action_view_purchase_orders(self):
        self.ensure_one()
        po = self.env['purchase.order'].search([('job_id', '=', self.id)])
        
        action = {
            'name': 'Purchase Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'context': {'default_job_id': self.id},
        }
        
        if len(po) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': po.id,
            })
        else:
            action.update({
                'view_mode': 'list,form',
                'domain': [('id', 'in', po.ids)],
            })       
        return action

    @api.onchange('customer_coupon_id')
    def _onchange_customer_coupon_id(self):
        self._onchange_coupon_services()

    @api.onchange('use_coupon', 'customer_coupon_id')
    def _onchange_coupon_services(self):

        commands = []

        # Remove existing coupon lines
        for line in self.job_cost_sheet_ids:
            print("34342342dd3423443", line.coupon_line)
            if line.coupon_line:
                if line.id:
                    commands.append((2, line.id))
                else:
                    commands.append((3, line.id))

        # If unchecked, just remove coupon lines and stop
        if not self.use_coupon:
            self.update({
                'job_cost_sheet_ids': commands
            })
            return

        if not self.customer_coupon_id:
            self.update({
                'job_cost_sheet_ids': commands
            })
            return

        coupon_master = self.customer_coupon_id.coupon_master_id
        if not coupon_master:
            self.update({
                'job_cost_sheet_ids': commands
            })
            return
        config = self._get_accounting_config()

        coupon_invoice_account_id = config['coupon_invoice_account_id']
        coupon_sales_account_id = config['coupon_sales_account_id']
        if not coupon_invoice_account_id:
            raise ValidationError(
                _('Please set Invoice Account from the settings'))
        if not coupon_sales_account_id:
            raise ValidationError(
                _('Please set Sales Account from the settings'))
        # Add coupon services
        for index, service_line in enumerate(
                coupon_master.allowed_service_line_ids.sorted('sequence'), start=1):
            product = service_line.product_id

            account = product.product_tmpl_id.get_product_accounts(
                fiscal_pos=None
            ).get('income')
            commands.append((0, 0, {
                'coupon_line': True,
                'coupon_service_no': index,
                'product_id': product.id,
                'name': service_line.description or product.display_name,
                'quantity': 1.0,
                'uom_id': product.uom_id.id,
                'price_unit': service_line.unit_price,
                'account_id': account.id if account else False,
                'cost_type': 'service',
            }))

        self.update({
            'job_cost_sheet_ids': commands
        })

class JobCardWarranty(models.Model):
    _name = "job.card.warranty"

    name = fields.Char(string="Name")

class JobCardBay(models.Model):
    _name = "job.card.bay"
    _description = "Job Card Bay"

    name = fields.Char(string="Name")
    is_occupied = fields.Boolean(string="Is Occupied", default=False)

# 2. Log Model to store individual history entries
class JobCardBayLog(models.Model):
    _name = 'job.card.bay.log'
    _description = 'Job Card Bay History Log'
    _order = 'bay_in desc'  # Shows newest logs at top

    task_id = fields.Many2one('project.task', string="Job Card", ondelete='cascade')
    bay_id = fields.Many2one('job.card.bay', string="Bay", required=True)
    bay_in = fields.Datetime(string="Bay In", required=True)
    bay_out = fields.Datetime(string="Bay Out")
    duration = fields.Float(
        string="Total Hours", 
        compute="_compute_duration", 
        store=True,
        help="Total duration spent in the bay (calculated as Bay Out - Bay In, or current time if active)."
    )

    @api.depends('bay_in', 'bay_out')
    def _compute_duration(self):
        now = fields.Datetime.now()
        for record in self:
            if record.bay_in:
                # Use bay_out if closed, otherwise calculate up to the current time
                end_time = record.bay_out if record.bay_out else now
                
                # Time difference in seconds converted to hours
                delta = end_time - record.bay_in
                record.duration = delta.total_seconds() / 3600.0
            else:
                record.duration = 0.0





