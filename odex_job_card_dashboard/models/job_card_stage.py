# -*- coding: utf-8 -*-
"""Presentation settings for job card statuses.

The dashboard never keeps its own copy of the status list: it reads
``job.card.stage`` directly and only adds the presentation attributes an
administrator needs (colour, icon, order, visibility).
"""
from odoo import api, fields, models

# Keyword -> (hex colour, font-awesome icon).  Used only to seed sensible
# defaults the first time a stage is displayed; administrators can override
# every value from Settings, and nothing is hardcoded in the front end.
DEFAULT_STYLE = [
    (('redo', 'rework', 'again'), '#F43F5E', 'fa-refresh'),
    (('vehicle in', 'vehicle_in', 'checkin', 'check in', 'reception'), '#3B82F6', 'fa-car'),
    (('inspect',), '#8B5CF6', 'fa-search'),
    (('estimate', 'quotation', 'quote'), '#EC4899', 'fa-file-text-o'),
    (('approval', 'approve', 'urg'), '#F59E0B', 'fa-check-circle-o'),
    (('progress', 'wip', 'repair', 'working'), '#10B981', 'fa-wrench'),
    (('part', 'spare'), '#EF4444', 'fa-cube'),
    (('road', 'test drive', 'testing'), '#06B6D4', 'fa-road'),
    (('wash', 'clean', 'polish'), '#A855F7', 'fa-tint'),
    (('ready', 'delivery ready'), '#0EA5E9', 'fa-truck'),
    (('deliver', 'out', 'handover'), '#22C55E', 'fa-check'),
    (('payment', 'invoice', 'billing'), '#F97316', 'fa-money'),
    (('cancel', 'reject'), '#94A3B8', 'fa-ban'),
    (('close', 'done', 'complete'), '#64748B', 'fa-lock'),
]

FALLBACK_COLOR = '#6366F1'
FALLBACK_ICON = 'fa-tasks'


def guess_style(*labels):
    """Return ``(colour, icon)`` guessed from a stage name / technical value."""
    haystack = ' '.join([(l or '') for l in labels]).lower()
    for keywords, color, icon in DEFAULT_STYLE:
        for keyword in keywords:
            if keyword in haystack:
                return color, icon
    return FALLBACK_COLOR, FALLBACK_ICON


class JobCardStage(models.Model):
    _inherit = 'job.card.stage'

    dashboard_color = fields.Char(
        string='Dashboard Colour',
        help='Hex colour used for this status on the dashboard, e.g. #3B82F6.',
    )
    dashboard_icon = fields.Char(
        string='Dashboard Icon',
        help='Font Awesome 4 class name without the "fa " prefix, e.g. fa-car.',
    )
    dashboard_sequence = fields.Integer(
        string='Dashboard Order', default=10,
        help='Order in which the status cards appear on the dashboard.',
    )
    show_on_dashboard = fields.Boolean(
        string='Show on Dashboard', default=True,
    )

    @api.model
    def _dashboard_stages(self):
        """Stages to render, already ordered, with style defaults applied."""
        stages = self.search([]).sorted(
            key=lambda s: (s.dashboard_sequence or 0, s.id)
        )
        result = []
        for stage in stages:
            if not stage.show_on_dashboard:
                continue
            value = stage.value if 'value' in stage._fields else ''
            color, icon = guess_style(stage.display_name, value)
            result.append({
                'id': stage.id,
                'name': stage.display_name,
                'value': value or '',
                'color': (stage.dashboard_color or color).strip(),
                'icon': (stage.dashboard_icon or icon).strip(),
                'sequence': stage.dashboard_sequence or 0,
            })
        return result

    def action_apply_default_style(self):
        """Reset colour + icon to the automatic suggestion."""
        for stage in self:
            value = stage.value if 'value' in stage._fields else ''
            color, icon = guess_style(stage.display_name, value)
            stage.write({'dashboard_color': color, 'dashboard_icon': icon})
        return True

    @api.model
    def _seed_dashboard_styles(self):
        """Fill colour/icon on stages that have none yet (idempotent)."""
        for stage in self.search([]):
            if stage.dashboard_color and stage.dashboard_icon:
                continue
            value = stage.value if 'value' in stage._fields else ''
            color, icon = guess_style(stage.display_name, value)
            stage.write({
                'dashboard_color': stage.dashboard_color or color,
                'dashboard_icon': stage.dashboard_icon or icon,
            })
        return True
