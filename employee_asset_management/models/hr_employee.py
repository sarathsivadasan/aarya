from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    asset_assignment_ids = fields.One2many(
        comodel_name='employee.asset.assignment',
        inverse_name='employee_id',
        string='Assigned Assets',
    )
    assigned_asset_count = fields.Integer(
        string='Assets',
        compute='_compute_assigned_asset_count',
    )

    def _compute_assigned_asset_count(self):
        grouped = self.env['employee.asset.assignment']._read_group(
            domain=[
                ('employee_id', 'in', self.ids),
                ('state', '=', 'assigned'),
            ],
            groupby=['employee_id'],
            aggregates=['__count'],
        )
        mapped_data = {employee.id: count for employee, count in grouped}
        for employee in self:
            employee.assigned_asset_count = mapped_data.get(employee.id, 0)

    def action_open_employee_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assets of %s', self.name),
            'res_model': 'employee.asset.assignment',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
                'search_default_group_by_state': 1,
            },
        }
