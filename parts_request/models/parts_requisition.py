# -*- coding: utf-8 -*-
import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_is_zero


class JobcardPartsRequisition(models.Model):
    _name = 'jobcard.part.requisition'
    _description = "Jobcard Part Requisition"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']  # odoo11
    _order = 'id desc'

    name = fields.Char(
        string='Number',
        index=True,
        readonly=1,
    )
    job_id = fields.Many2one("project.task", string="Jobcard")
    job_cost_sheet_id = fields.Many2one("job.cost.sheet", string="Job Cost Sheet")
    register_no = fields.Char(string="Register No.")
    cc_vehicle_model = fields.Many2one("fleet.vehicle.model", string="Vehicle Model")
    state = fields.Selection([
        ('draft', 'New'),
        ('approve', 'Approved'),
        ('reject', 'Rejected')],
        default='draft',
        tracking=True
    )
    request_date = fields.Date(
        string='Requisition Date',
        default=lambda self: fields.Date.context_today(self),
        required=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1),
        required=False,
        copy=True,
    )
    approve_reject_employee_id = fields.Many2one(
        'hr.employee',
        string='Approved/Rejected by',
        readonly=True,
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.user.company_id,
        required=True,
        copy=True,
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        copy=True, default=lambda self: self.env.ref('stock.stock_location_stock')
    )
    dest_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        required=False,
        copy=True, default=lambda self: self.env.ref('stock.stock_location_customers')
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
    )
    description = fields.Char(
        string='Description',
        required=True,
    )
    qty_available = fields.Float(string="On Hand", related="product_id.qty_available")
    qty = fields.Float(
        string='Quantity',
        default=1,
        required=True,
    )
    uom_id = fields.Many2one(
        'uom.uom',#product.uom in odoo11
        string='Unit of Measure',
        required=True,
    )
    cost_price = fields.Float(related="product_id.standard_price")
    sale_price = fields.Float(related="product_id.list_price")
    cost_type = fields.Selection(
        [('spare_parts', 'Spare Parts'),
         ('material', 'Material'),
         ('consumables', 'Consumables'),
         ('paint_material', 'Paint Material'),
         ('sublet', 'Sublet'),
         ],
        string='Type',
        default='spare_parts',
    )
    delivery_picking_id = fields.Many2one(
        'stock.picking',
        string='Stock Picking',
        readonly=True,
        copy=False,
    )
    po_id = fields.Many2one('purchase.order', string="Purchase Order")

    @api.onchange('product_id')
    def onchange_product_id(self):
        for rec in self:
            # rec.description = rec.product_id.name
            rec.description = rec.product_id.display_name
            rec.uom_id = rec.product_id.uom_id.id

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'reject'):
                raise UserError(
                    _('You can not delete Part Request which is not in draft or rejected state.'))
        return super(JobcardPartsRequisition, self).unlink()

    @api.model
    def create(self, vals):
        name = self.env['ir.sequence'].next_by_code('jobcard.parts.requisition.seq')
        vals.update({
            'name': name
        })
        res = super(JobcardPartsRequisition, self).create(vals)
        return res

    def show_picking(self):
        self.ensure_one()
        res = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        res['domain'] = str([('jobcard_part_requisition_id', '=', self.id)])
        return res

    def user_approve(self):
        for rec in self:
            # rec.userrapp_date = fields.Date.today()
            # rec.is_approved = True
            # if rec.task_id:
            #     rec.task_id.cc_stage_id=2
            # create picking and remove products from inventory
            rec.request_stock()
            rec.state = 'approve'
            rec.approve_reject_employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            rec.job_cost_sheet_id.qty_approve = rec.qty

    def user_reject(self):
        for rec in self:
            rec.state = 'reject'
            rec.approve_reject_employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            if rec.task_id:
                if rec.task_id.journal_entry_id:
                    rec.task_id.journal_entry_id.button_cancel()

    @api.model
    def _prepare_pick_vals(self, stock_id=False):
        pick_vals = {
            'product_id': self.product_id.id,
            'product_uom_qty': self.qty,
            'product_uom': self.uom_id.id,
            'location_id': stock_id.location_id.id or self.location_id.id,
            'location_dest_id': stock_id.location_dest_id.id or self.dest_location_id.id,
            'name': self.product_id.name,
            'picking_type_id': stock_id.picking_type_id.id, 
            # or self.custom_picking_type_id.id,
            'picking_id': stock_id.id,
            'jobcard_part_requisition_id': self.id,
            'company_id': self.company_id.id,
        }
        return pick_vals

    def request_stock(self):
        stock_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        # internal_obj = self.env['stock.picking.type'].search([('code','=', 'internal')], limit=1)
        # internal_obj = self.env['stock.location'].search([('usage','=', 'internal')], limit=1)
        #         if not internal_obj:
        #             raise UserError(_('Please Specified Internal Picking Type.'))
        for rec in self:
            # if not rec.location_id.id:
            #    raise UserError(_('Select Source location under the picking details.'))
                # if not rec.custom_picking_type_id.id:
                    
                #                        raise UserError(_('Select Picking Type under the picking details.'))
                #                    raise UserError(_('Select Picking Type under the picking details.'))
                # if not rec.dest_location_id:
                #     raise UserError(_('Select Destination location under the picking details.'))
                #                 if not rec.employee_id.dest_location_id.id or not rec.employee_id.department_id.dest_location_id.id:
                #                   raise UserError(_('Select Destination location under the picking details.'))
                #  
            custom_picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'outgoing'), ("company_id", "=", rec.company_id.id)], limit=1).id                   
            picking_vals = {
                'partner_id': rec.employee_id.sudo().user_partner_id.id,
                'location_id': rec.location_id.id,
                'location_dest_id': rec.dest_location_id and rec.dest_location_id.id or rec.employee_id.dest_location_id.id or rec.employee_id.department_id.dest_location_id.id,
                'picking_type_id': custom_picking_type_id,  # internal_obj.id,
                # 'note': rec.reason,
                'jobcard_part_requisition_id': rec.id,
                'origin': rec.name,
                'company_id': rec.company_id.id,
                }
            stock_id = stock_obj.sudo().create(picking_vals)
            delivery_vals = {
                'delivery_picking_id': stock_id.id,
            }
            rec.write(delivery_vals)

            move_id = False  # custom test
            pick_vals = rec._prepare_pick_vals(stock_id)
            move_id = move_obj.sudo().create(pick_vals)
            # custom test start==>
            if move_id:
                stock_move = self.env['stock.move'].sudo().search(
                    [('reference', '=', rec.delivery_picking_id.name)])

                account_setup_job = self.env.ref('job_card_extension.account_setup_job_card')
                if not account_setup_job or any(not field for field in [
                    account_setup_job.debit_account,
                    account_setup_job.credit_account,
                    account_setup_job.journal_id,
                ]):
                    raise ValidationError(_('Missing values in Job auto-account setup.'))

                debit_acc = account_setup_job.debit_account   #==>debit
                credit_acc = account_setup_job.credit_account  #==>credit
                journal_id = account_setup_job.journal_id  #==>journal
                prec = self.env['decimal.precision'].precision_get('Account')
                stock_valuation_layer = self.env['stock.valuation.layer'].sudo().search(
                    [('stock_move_id', '=', move_id.id)])
                # 9538
                requisition = move_id.jobcard_part_requisition_id
                req_cost = requisition.cost_price
                req_qty = requisition.qty
                req_total = req_cost * req_qty
                if rec.job_id:
                    entry_dict = {
                        'move_type': 'entry',
                        'date': fields.Date.today(),
                        'journal_id': journal_id.id,
                        'job_id': rec.job_id.id,
                        'ref': _('%s - %s') % (rec.job_id.name, move_id.reference),
                        'currency_id': self.env.company.currency_id.id,
                        'line_ids': [
                            (0, 0, {
                                'name': str(rec.job_id.name) + str(rec.name),
                                'account_id': debit_acc.id,
                                'debit': req_total if req_total else 0.00,
                                'credit': 0.00,
                                'amount_currency': req_total if req_total else 0.00,
                                'currency_id': self.env.company.currency_id.id,
                                'journal_id': journal_id.id,
                                'product_id': move_id.product_id.id,
                                'quantity': req_qty,
                                # 'price_custom': req_total if req_total else 0.00,
                            }),
                            (0, 0, {
                                'name': str(rec.job_id.name) + str(rec.name),
                                'product_id': move_id.product_id.id,
                                'account_id': credit_acc.id,
                                'debit': 0.00,
                                'credit': req_total if req_total else 0.00,
                                'amount_currency': -(req_total if req_total else 0.00),
                                'currency_id': self.env.company.currency_id.id,
                                'journal_id': journal_id.id,
                                'quantity': req_qty,
                                # 'price_custom': req_total if req_total else 0.00,
                            }),
                        ],
                    }
                    new_journal_items = self.env['account.move'].sudo().create(entry_dict)
                    if new_journal_items:
                        rec.job_id.journal_entry_id = new_journal_items.id
                        new_journal_items.action_post()
                        # rec.job_id.line_ids = [(4, journal_line_id) for journal_line_id in
                        #                         new_journal_items.line_ids.ids]
                        # rec.task_id.line_ids = new_journal_items.line_ids.ids
                

                # custom test END==>
                # Check if the picking type is a delivery order
                if stock_id.state == 'draft':
                    stock_id.action_confirm()
                    stock_id.action_assign()

                for move in stock_id.move_ids.filtered(lambda m: m.state not in ["done", "cancel"]):
                    if move.move_line_ids:
                        # If reservation created lines, fill their quantity
                        for move_line in move.move_line_ids:
                            move_line.quantity = (
                                move_line.quantity_product_uom
                                or move_line.product_uom_qty
                                or move.product_uom_qty
                            )
                    else:
                        # If reservation did NOT create lines (no reservation), set quantity directly on move
                        move.quantity = move.product_uom_qty

                # 5. Validate the picking
                stock_id.button_validate()
                        
    def action_create_purchase_order(self):
        # Get all selected records
        requisitions = self.env['jobcard.part.requisition'].browse(self._context.get('active_ids'))
        for rec in requisitions:
            if rec.state == 'approve':
                raise ValidationError(
                    _("This %s number of part requisition already in approve state, so yo can not create purchase order for that", rec.name)
                )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                # 'default_partner_id': self.employee_id.partner_id.id if self.employee_id else False,
                # 'default_origin': self.name,
                'default_order_line': [
                    (0, 0, {
                        'product_id': rec.product_id.id,
                        'product_qty': rec.qty,
                        'price_unit': rec.cost_price,
                        'part_requisition_id': rec.id,
                        'product_uom': rec.product_id.uom_po_id.id,
                        # 'name': self.name,
                    }) for rec in requisitions
                ]
                }
            }