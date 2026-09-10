from odoo import models, fields, api
from lxml import etree
from ast import literal_eval

class Task(models.Model):
    _inherit = "project.task"

    # contact_person_name = fields.Char(string="Contact Person Name", required=False)
    is_vc = fields.Boolean(default=False)
    inspection_state = fields.Selection(
        [('vehicle_in', 'Vehicle In'),('inspection_started', 'Inspection Started'), ('inspection_finished', 'Inspection Finished')],
        string="State", default="vehicle_in", tracking=True)
    # cc_state_color =  fields.Selection(
    #     [('1', 'Pink Orange'),('2', 'Green')],string="Colour")
    cc_state_color = fields.Integer(string="Color")

    # cc_stage_id = fields.Selection(
    #     selection_add=[('inspection_started', 'Inspection Started'), ('inspection_finished', 'Inspection Finished')],
    #     string="State", default="inspection_started", domain=_get_domain, tracking=True)
    id_card = fields.Binary(string="ID Card")
    inspection_estimated_hour_ids = fields.One2many(
        "vehicle.inspection.estimated.hours",
        "inspection_id",
        string="Estimated Hours"
    )
    # vehicle_photo = fields.Image("Image")
    # date_time_in = fields.Datetime(string="Date Time In", readolny=False)
    # date_time_out = fields.Datetime(string="Date Time Out", readolny=False)
    # fuel_gauge = fields.Char("Fuel Gauge")
    # fleet_service_id = fields.Many2one('fleet.vehicle.log.services', string="Fleet Service")

    # @api.onchange('fleet_service_id')
    # def onchange_fleet_service_id(self):
    #     for rec in self:
    #         if rec.fleet_service_id:
    #             """
    #                 Create Job cost sheet and material requisition
    #             """
    #             # if self.state not in ['sale']:
    #             #     raise ValidationError(_('Confirm the order first.'))
    #             job_cost_sheet = self.env['job.cost.sheet']
    #             material_requisition_line = self.env['material.purchase.requisition.line']

    #             if rec.fleet_service_id.fleet_service_sheet_ids:
    #                 service_sheet_ids = rec.fleet_service_id.fleet_service_sheet_ids
    #                 cost_sheet_lines = service_sheet_ids.filtered(lambda x: x.cost_type not in ['material', 'spare_parts'])
    #                 requisition_lines = service_sheet_ids.filtered(lambda x: x.cost_type in ['material', 'spare_parts'])
    #                 if cost_sheet_lines:
    #                     rec.job_cost_sheet_ids= [(5, 0, 0)]  # Clear existing cost sheet lines
    #                     for line in cost_sheet_lines:
    #                         job_cost_sheet.create({
    #                             'cost_type': line.cost_type,
    #                             'product_id': line.product_id.id,
    #                             'account_id': line.account_id.id,
    #                             'account_analytic_id': None,
    #                             'quantity': line.quantity,
    #                             'uom_id': line.uom_id.id,
    #                             # 'cc_sale_price': line.cc_sale_price,
    #                             'price_unit': line.price_unit,
    #                             'price_custom': line.price_custom,
    #                             'price_factor': line.price_factor.id,
    #                             'barcode_custom': line.barcode_custom,
    #                             'invoice_line_tax_ids': line.invoice_line_tax_ids,
    #                             'price_subtotal': line.price_subtotal,
    #                             'task_id': rec.id,
    #                             'name': line.name,
    #                             'discount': line.discount,
    #                             # 'cc_check_box': True
    #                         })

    #                 if requisition_lines:
    #                     rec.material_requisition_ids = [(5, 0, 0)] # Clear existing material requisition 
    #                     material_requisition_obj = self.env['material.purchase.requisition']
    #                     employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)])
    #                     lines = []
    #                     material_requisition_id = material_requisition_obj.create({'employee_id': employee_id.id,
    #                                     'department_id': employee_id.department_id.id,
    #                                     'request_date': fields.Date.today(),
    #                                     'task_id': rec.id or rec._origin.id}) 
    #                     for line in requisition_lines:
    #                         material_requisition_line.create({
    #                             'requisition_type': 'internal',
    #                             'barcode': line.barcode_custom,
    #                             'product_id': line.product_id.id,
    #                             'description': line.name,
    #                             'qty': line.quantity,
    #                             'uom': line.uom_id.id,
    #                             'requisition_id': material_requisition_id.id,
    #                         })



    def show_estimate(self):
        self.ensure_one()
        res = self.env.ref('sale.action_quotations_with_onboarding')
        res = res.sudo().read()[0]
        order_lines = []
        if self.inspection_part_ids:
            for each in self.inspection_part_ids:
                if each.is_confirm:
                    line_vals = {'product_id': each.product_id.id,
                                 'part_no': each.part_no,
                                 'parts_type': each.parts_type,
                                 'product_uom_qty': each.quantity,}
                    print("self.mv_rfq_ids,,,,,,,,,,,", self.mv_rfq_ids[0])
                    if self.mv_rfq_ids and self.mv_rfq_ids[0].state == 'received':
                        print("true,,,,,,,,,,,,,,,")
                        for line in self.mv_rfq_ids[0].line_ids:
                            if line.product_id == each.product_id:
                                line_vals.update({'custom_price': line.lowest_price,
                                                'vendor_id': line.recommended_vendor_id.id,})
                    order_lines.append(line_vals)
        print("order_lines,,,,,,,,,", order_lines)
        res['domain'] = str([('inspection_id', '=', self.id)])
        res['context'] = str({
                # 'default_job_id': self.id,
                'default_inspection_id': self.id,
                'default_vehicle_id': self.vehicle_id.id if self.vehicle_id else None,
                'default_partner_id': self.partner_id.id if self.partner_id else None,
                'default_order_line': order_lines,
                'from_inspection': True,})
        return res                    

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(Task, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                       submenu=submenu)

        # Check if the view is the specific form view we want to modify
        form_view_id = self.env.ref('project.view_task_form2').id
        c_form_view_id = self.env.ref('vehicle_inspection_report.view_form_v_job_card_extension').id
        is_vc = self.env.context.get('is_vc')
        if res.get('view_id', False) == form_view_id or res.get('view_id', False) == c_form_view_id and res.get('type', False) == 'form':
            vc =  self.env.context.get('default_is_vc',False)
            if vc:
                toolbar_rec = res.get('toolbar', {})
                print_actions = toolbar_rec.get('print', [])
                # Filter out the "Job Cards" print option
                filtered_print_actions = [action for action in print_actions if action['name'] != 'Job Cards']

                # Update the toolbar with the filtered print actions
                res['toolbar']['print'] = filtered_print_actions
            else:
                toolbar_rec = res.get('toolbar', {})
                print_actions = toolbar_rec.get('print', [])

                # Filter out the "Job Cards" print option
                filtered_print_actions = [action for action in print_actions if action['name'] != 'Vehicle Inspection Report']

                # Update the toolbar with the filtered print actions
                res['toolbar']['print'] = filtered_print_actions

            # Optionally modify the form view's XML arch if needed
            doc = etree.XML(res['arch'])
            # Modify other XML elements here if required (readonly fields, etc.)

            # Save any XML modifications back to the response
            res['arch'] = etree.tostring(doc)

        return res

    # def action_create_cost_lines(self):
    #     for rec in self:
    #         for each in rec.material_requisition_line_ids:
    #             each.action_add_line_in_cost_sheet()

    def action_done(self):
        for rec in self:
            rec.inspection_state = 'inspection_finished'

    @api.onchange('inspection_state')
    def onchange_inspection_state(self):
        for rec in self:
            if rec.inspection_state:
                if rec.inspection_state == 'inspection_started':
                    rec.cc_state_color = 1
                elif rec.inspection_state == 'inspection_finished':
                    rec.cc_state_color = 2
                else:
                    rec.cc_state_color = 0

    @api.model_create_multi
    def create(self, vals_list):
        custom_task_sequence_ignore = literal_eval(self.env['ir.config_parameter'].sudo().get_param('job_card.custom_task_sequence_ignore', 'False'))
        for vals in vals_list:
            if custom_task_sequence_ignore:
                if self._context.get('default_is_vc'):
                    vc_sequence = self.env['ir.sequence'].next_by_code('vc.project.task')
                    vals['name'] = vc_sequence   
        rec = super(Task, self).create(vals_list)
        if rec.name and self._context.get('default_is_vc') or rec.is_vc:
            rec.project_id = rec.project_id.create({
                'name': rec.name, 
                'company_id':rec.company_id.id,
                'partner_id': rec.partner_id.id,
                'allow_billable': True})
            if not rec.project_id.account_id:
                rec.project_id._create_analytic_account()
            rec.analytic_account_id = rec.project_id.account_id.id
        return rec

            # return {
        #     "type": "ir.actions.act_window",
        #     "res_model": "purchase.multi.rfq",
        #     "res_id": po_multi_rfq_id.id,
        #     "view_mode": "form",
        # }

    def action_view_mv_rfq(self):
        self.ensure_one()
        res = self.env.ref('odex_multi_vendor_rfq.action_purchase_multi_rfq')
        res = res.sudo().read()[0]
        order_lines = []
        if self.inspection_part_ids:
            for each in self.inspection_part_ids:
                if each.is_confirm == True:
                    order_lines.append({'product_id': each.product_id.id,
                                        'uom_id': each.product_id.uom_po_id.id,
                                        'part_no': each.part_no,
                                        'parts_type': each.parts_type,
                                        'quantity': each.quantity})
        res['domain'] = str([('inspection_id', '=', self.id)])
        res['context'] = str({
                'default_inspection_id': self.id,
                'default_line_ids': order_lines,})
        return res

# class FleetVehicleModel(models.Model):
#     _inherit = 'fleet.vehicle.model'

#     @api.depends('name', 'brand_id')
#     def name_get(self):
#         res = []
#         for record in self:
#             name = record.name
#             if record.brand_id.name:
#                 name = name
#             res.append((record.id, name))
#         return res

    # @api.depends('name', 'brand_id')
    # def name_get(self):
    #     res = []
    #     for record in self:
    #         name = record.name
    #         # Check if brand_id exists and is a valid record
    #         if record.brand_id and record.brand_id.name:
    #             name = f"{record.brand_id.name} {name}"
    #         res.append((record.id, name))
    #     return res

class VehicleInspectionEstimatedHours(models.Model):
    _name = "vehicle.inspection.estimated.hours"
    _description = "Vehicle Inspection Estimated Hours"

    inspection_id = fields.Many2one(
        "project.task",
        required=True,
        ondelete="cascade"
    )

    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        required=True
    )
    assign_hours = fields.Float(string="Assign Hours", digits=(16, 2))