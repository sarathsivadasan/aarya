# -*- coding: utf-8 -*-
"""Presentation settings for job card statuses.

The dashboard never keeps its own copy of the status list: it reads
``job.card.stage`` directly and only adds the presentation attributes an
administrator needs (colour, icon, order, visibility).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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

# Boolean flags the workflow module itself may define on job.card.stage to
# mark the closing status.  Checked before any name matching.
NATIVE_CLOSED_FLAGS = ('is_close', 'is_closed', 'closed', 'is_closing_stage')
CLOSED_VALUES = ('closed', 'close')

# Names a normal status may not take: they belong to calculated cards.
RESERVED_STATUS_NAMES = ('total job card', 'total job cards')

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
    dashboard_is_closed = fields.Boolean(
        string='Closed Status',
        help='Job cards currently in a status ticked here are treated as '
             'closed: they are excluded from the Total Job Card figure. '
             'Reopening a job card (moving it to any other status) makes it '
             'count again. If no status is ticked, the closing status is '
             'detected automatically.',
    )

    @api.constrains('name')
    def _check_reserved_dashboard_name(self):
        for stage in self:
            if (stage.name or '').strip().lower() in RESERVED_STATUS_NAMES:
                raise ValidationError(_(
                    '"%s" is a calculated dashboard card, not a job card status. '
                    'Configure it from Workshop Dashboard / Configuration / '
                    'Calculated Cards.', stage.name))

    @api.model
    def _dashboard_closed_stages(self):
        """Statuses that mean "closed", resolved without any hardcoded id.

        Order of preference:
        1. statuses an administrator ticked as *Closed Status*;
        2. a boolean flag defined by the workflow module on the stage;
        3. the stage technical value (``closed``);
        4. the stage name (``ilike 'close'``) - same keyword the style
           suggestion already uses for the Closed card.
        """
        flagged = self.search([('dashboard_is_closed', '=', True)])
        if flagged:
            return flagged
        for candidate in NATIVE_CLOSED_FLAGS:
            field = self._fields.get(candidate)
            if field and field.type == 'boolean' and field.store:
                stages = self.search([(candidate, '=', True)])
                if stages:
                    return stages
        if 'value' in self._fields and self._fields['value'].store:
            stages = self.search([('value', 'in', list(CLOSED_VALUES))])
            if stages:
                return stages
        return self.search([('name', 'ilike', 'close')])

    @api.model
    def _seed_closed_stages(self):
        """Tick *Closed Status* on the detected stage(s) once, so the
        configuration screen shows what the dashboard is actually using.
        Never overrides a choice an administrator already made."""
        if self.search_count([('dashboard_is_closed', '=', True)]):
            return True
        detected = self._dashboard_closed_stages()
        if detected:
            detected.write({'dashboard_is_closed': True})
        return True

    @api.model
    def action_open_calculated_cards(self):
        """Header button of the Status Cards list."""
        self.env['job.card.dashboard.card']._ensure_cards()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odex_job_card_dashboard.action_job_card_dashboard_card')
        return action

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
