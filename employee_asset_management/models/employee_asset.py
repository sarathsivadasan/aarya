from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EmployeeAssetAssignment(models.Model):
    _name = 'employee.asset.assignment'
    _description = 'Employee Asset Assignment'
    _inherit = ['mail.thread']
    _order = 'assign_date desc, id desc'

    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        required=True,
        index=True,
        ondelete='cascade',
        tracking=True,
    )
    department_id = fields.Many2one(
        related='employee_id.department_id',
        string='Department',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    asset_id = fields.Many2one(
        comodel_name='product.product',
        string='Asset Name',
        required=True,
        index=True,
        tracking=True,
        help='Asset selected from the existing product catalogue.',
    )
    asset_category_id = fields.Many2one(
        related='asset_id.categ_id',
        string='Asset Category',
        store=True,
        readonly=True,
    )
    serial_number = fields.Char(
        string='Serial Number / Barcode',
        index=True,
        tracking=True,
        copy=False,
        help='Physical serial number or barcode of the asset. '
             'It can be typed in or filled with a barcode scanner.',
    )
    assign_date = fields.Date(
        string='Assign Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    return_date = fields.Date(
        string='Asset Return Date',
        tracking=True,
        copy=False,
    )
    condition_note = fields.Text(
        string='Note for Health Condition',
        help='Physical condition of the asset when assigned or returned.',
    )
    notes = fields.Text(string='Notes')
    state = fields.Selection(
        selection=[
            ('assigned', 'Assigned'),
            ('returned', 'Returned'),
        ],
        string='Status',
        default='assigned',
        required=True,
        index=True,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Display name
    # ------------------------------------------------------------------
    @api.depends('asset_id', 'serial_number', 'employee_id')
    def _compute_display_name(self):
        for record in self:
            name = record.asset_id.display_name or _('Asset')
            if record.serial_number:
                name = '%s [%s]' % (name, record.serial_number)
            record.display_name = name

    # ------------------------------------------------------------------
    # Onchange
    # ------------------------------------------------------------------
    @api.onchange('return_date')
    def _onchange_return_date(self):
        for record in self:
            if record.return_date:
                record.state = 'returned'
            elif record.state == 'returned':
                record.state = 'assigned'

    @api.onchange('state')
    def _onchange_state(self):
        for record in self:
            if record.state == 'returned' and not record.return_date:
                record.return_date = fields.Date.context_today(record)
            elif record.state == 'assigned' and record.return_date:
                record.return_date = False

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        for record in self:
            if record.employee_id.company_id:
                record.company_id = record.employee_id.company_id

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('assign_date', 'return_date')
    def _check_dates(self):
        for record in self:
            if record.return_date and record.assign_date \
                    and record.return_date < record.assign_date:
                raise ValidationError(_(
                    'The Asset Return Date cannot be earlier than the Assign Date.'
                ))

    @api.constrains('state', 'return_date')
    def _check_state_dates(self):
        for record in self:
            if record.state == 'returned' and not record.return_date:
                raise ValidationError(_(
                    'A returned asset must have an Asset Return Date.'
                ))
            if record.state == 'assigned' and record.return_date:
                raise ValidationError(_(
                    'An assigned asset cannot have an Asset Return Date. '
                    'Set the status to Returned instead.'
                ))

    @api.constrains('serial_number', 'state', 'asset_id', 'company_id')
    def _check_unique_active_serial(self):
        for record in self:
            if record.state != 'assigned' or not record.serial_number:
                continue
            duplicate = self.search([
                ('id', '!=', record.id),
                ('state', '=', 'assigned'),
                ('serial_number', '=ilike', record.serial_number.strip()),
                ('company_id', '=', record.company_id.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'This asset is already assigned to another employee.\n\n'
                    'Serial Number / Barcode: %(serial)s\n'
                    'Asset: %(asset)s\n'
                    'Currently assigned to: %(employee)s (since %(date)s)\n\n'
                    'Return the asset first, then it can be assigned again.',
                    serial=duplicate.serial_number,
                    asset=duplicate.asset_id.display_name,
                    employee=duplicate.employee_id.display_name,
                    date=duplicate.assign_date or '',
                ))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('serial_number'):
                vals['serial_number'] = vals['serial_number'].strip()
            if vals.get('return_date') and not vals.get('state'):
                vals['state'] = 'returned'
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('serial_number'):
            vals['serial_number'] = vals['serial_number'].strip()
        if 'return_date' in vals and 'state' not in vals:
            vals['state'] = 'returned' if vals.get('return_date') else 'assigned'
        return super().write(vals)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_return_asset(self):
        """Mark the asset as returned, keeping the full history."""
        today = fields.Date.context_today(self)
        for record in self:
            if record.state == 'returned':
                continue
            record.write({
                'state': 'returned',
                'return_date': record.return_date or today,
            })
        return True

    def action_set_to_assigned(self):
        """Undo a return (correction by HR)."""
        for record in self:
            record.write({
                'state': 'assigned',
                'return_date': False,
            })
        return True
