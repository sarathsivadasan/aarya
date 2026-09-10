from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FleetVehicleLogServices(models.Model):
    _inherit = "fleet.vehicle.log.services"

    vehicle_id = fields.Many2one('fleet.vehicle', 'Vehicle', required=False, help='Vehicle concerned by this log')
    fleet_service_sheet_ids = fields.One2many('fleet.service.sheet', 'fleet_service_id', string="Fleet Service Sheet")


class FleetServiceSheet(models.Model):
    _name = "fleet.service.sheet"
    _description = 'Fleet Vehicle Log Service'

    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
        'product_id', 'fleet_service_id.vendor_id', 'fleet_service_id.currency_id')
    def _compute_price(self):
        for rec in self:
            rec.tax_amount = 0.0
            currency = rec.fleet_service_id and rec.fleet_service_id.currency_id or None
            price = rec.price_unit * (1 - (rec.discount or 0.0) / 100.0)
            taxes = False
            if rec.invoice_line_tax_ids:
                taxes = rec.invoice_line_tax_ids.compute_all(price, currency, rec.quantity, product=rec.product_id, partner=rec.fleet_service_id.vendor_id)
            if taxes:
                for taxe in taxes['taxes']:
                    rec.tax_amount += taxe['amount']
            rec.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else rec.quantity * price
            if rec.fleet_service_id.currency_id and rec.fleet_service_id.currency_id != rec.fleet_service_id.company_id.currency_id:
                price_subtotal_signed = rec.fleet_service_id.currency_id.with_context(date=rec.fleet_service_id.create_date).compute(price_subtotal_signed, rec.fleet_service_id.company_id.currency_id)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.price_unit = self.product_id.lst_price
        self.uom_id = self.product_id.uom_id.id
        self.name = self.product_id.name
        self.cost_type = self.product_id.cost_type
        company = self.fleet_service_id.company_id
        product = self.product_id
        invoice_line_obj = self.env['account.move.line']
        account = self.product_id.product_tmpl_id.get_product_accounts(fiscal_pos=None)['income']
        if account:
           self.account_id = account.id

    @api.onchange('barcode_custom')
    def onchange_barcode_custom(self):
        for rec in self:
            if rec.barcode_custom:
                product_id = rec.product_id.search([('barcode', '=', rec.barcode_custom)], limit=1)
                if product_id:
                    rec.product_id = product_id.id
            elif rec.product_id:
                rec.barcode_custom = rec.product_id.barcode

    @api.onchange('price_factor', 'price_custom')
    def onchange_price_factor(self):
        for rec in self:
            if rec.price_factor and rec.price_factor.factor_percent:
                if rec.price_unit:
                    rec.update({
                        'price_unit': rec.price_custom * (1 + rec.price_factor.factor_percent/100)
                    })
            else:
                rec.update({
                    'price_unit': rec.price_custom
                })

    name = fields.Text(string='Description', required=True)
    product_id = fields.Many2one('product.product', string="Product")
    cost_type = fields.Selection(
         [('spare_parts', 'Spare Parts'),
         ('discount', 'Discount'),
         ('service', 'Service'),
         ('consumables', 'Consumables'),
         ('labour', 'Labour'),
         ('sublet', 'Sublet'),
         ('tyre', 'Tyre'),
         ('scrap', 'Scrap'),
         ],
        string='Type',
        default='service',
    )
    account_id = fields.Many2one('account.account', string="Account", required=True)
    # account_analytic_id = fields.Many2one('account.analytic.account', related=".analytic_account_id",
    #     string='Analytic Account')
    quantity = fields.Float(
        string='Quantity', digits='Product Unit of Measure', required=True, default=1)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', ondelete='set null', index=True)
    price_unit = fields.Float(string='Unit Price', required=True, digits='Product Price')
    discount = fields.Float(string='Discount (%)',
        digits='Discount', default=0.0)
    invoice_line_tax_ids = fields.Many2many('account.tax', string='Taxes')
    fleet_service_id = fields.Many2one('fleet.vehicle.log.services', string="Fleet Log Service")
    tax_amount = fields.Float(string='Tax Amount', store=True, readonly=True,
        compute='_compute_price', help="Total tax amount")
    price_subtotal = fields.Float(string='Amount', store=True, readonly=True, compute='_compute_price',
        help="Total amount without taxes")
    price_custom = fields.Float(string="Price", required=True)
    price_factor = fields.Many2one("price.factor", string="Price Factor")
    barcode_custom = fields.Char(string="Part No.")

    

