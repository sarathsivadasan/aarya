# -*- coding: utf-8 -*-
"""Administrator-editable dashboard settings.

One active record per company.  Every layout / threshold decision the front
end makes is read from here, so behaviour can be changed without touching code.
"""
from odoo import api, fields, models


class JobCardDashboardConfig(models.Model):
    _name = 'job.card.dashboard.config'
    _description = 'Job Card Dashboard Configuration'
    _order = 'id desc'

    name = fields.Char(required=True, default='Dashboard Configuration')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )

    # ---------------------------------------------------------------- behaviour
    auto_refresh = fields.Boolean(string='Auto Refresh', default=True)
    refresh_interval = fields.Integer(
        string='Refresh Interval (seconds)', default=30,
        help='Minimum 10 seconds. The dashboard also refreshes instantly when a '
             'job card status, technician, inspection or promise date changes.',
    )
    default_date_filter = fields.Selection(
        [('today', 'Today'), ('yesterday', 'Yesterday'), ('week', 'This Week'),
         ('month', 'This Month'), ('all', 'All Time')],
        string='Default Date Filter', default='all', required=True,
    )
    date_field = fields.Selection(
        [('create_date', 'Creation Date'), ('promise_date', 'Promise Date'),
         ('date_start', 'Start Date')],
        string='Filter Job Cards On', default='create_date', required=True,
    )
    list_limit = fields.Integer(
        string='Rows per Table', default=10,
        help='Number of records loaded in each dashboard table and drill-down list.',
    )

    # ---------------------------------------------------------------- thresholds
    overdue_warning_days = fields.Integer(string='Overdue - Warning (days)', default=1)
    overdue_critical_days = fields.Integer(string='Overdue - Critical (days)', default=3)
    overdue_severe_days = fields.Integer(string='Overdue - Severe (days)', default=7)
    efficiency_target = fields.Integer(
        string='Technician Efficiency Target (%)', default=80,
    )

    # ---------------------------------------------------------------- widgets
    show_status_cards = fields.Boolean(string='Status Cards', default=True)
    show_bays = fields.Boolean(string='Bay Occupancy', default=True)
    show_today_jobs = fields.Boolean(string="Today's Job Cards", default=True)
    show_overdue = fields.Boolean(string='Overdue Job Cards', default=True)
    show_quick_actions = fields.Boolean(string='Quick Actions', default=True)
    show_waiting = fields.Boolean(string='Customer Waiting', default=True)
    show_alerts = fields.Boolean(string='Priority Alerts', default=True)

    _sql_constraints = [
        ('refresh_positive', 'CHECK(refresh_interval >= 10)',
         'The refresh interval must be at least 10 seconds.'),
    ]

    @api.model
    def get_config(self):
        """Return the active configuration for the current company, creating it
        on first use so the dashboard never renders without settings."""
        config = self.search([
            ('company_id', 'in', [self.env.company.id, False]),
        ], limit=1)
        if not config:
            config = self.sudo().create({
                'name': 'Dashboard Configuration',
                'company_id': self.env.company.id,
            })
        return config

    @api.model
    def get_config_values(self):
        config = self.get_config()
        return {
            'auto_refresh': config.auto_refresh,
            'refresh_interval': max(10, config.refresh_interval or 30),
            'default_date_filter': config.default_date_filter,
            'date_field': config.date_field,
            'list_limit': max(1, config.list_limit or 10),
            'overdue_warning_days': config.overdue_warning_days,
            'overdue_critical_days': config.overdue_critical_days,
            'overdue_severe_days': config.overdue_severe_days,
            'efficiency_target': config.efficiency_target,
            'widgets': {
                'status_cards': config.show_status_cards,
                'bays': config.show_bays,
                'today_jobs': config.show_today_jobs,
                'overdue': config.show_overdue,
                'quick_actions': config.show_quick_actions,
                'waiting': config.show_waiting,
                'alerts': config.show_alerts,
            },
        }

    def action_open_stages(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Status Cards',
            'res_model': 'job.card.stage',
            'view_mode': 'list,form',
            'target': 'current',
        }
