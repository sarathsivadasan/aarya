# -*- coding: utf-8 -*-
"""Calculated (non-workflow) dashboard cards.

``job.card.stage`` is the workflow: every record there is a status a job card
can be put in.  A card such as *Total Job Card* is not a status - it is a
figure computed across statuses - so it must never appear in the job card
status bar or status selection.  It therefore lives in its own small model
that carries exactly the same presentation fields as the status cards
(colour, icon, order, visibility) and is merged with them by the dashboard
service.

Only one record per ``card_type`` can exist, and it cannot be deleted - an
administrator hides it with *On Dashboard* instead.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

CARD_TYPES = [
    ('total_job_card', 'Total Job Card'),
]

# Presentation defaults per card type (Font Awesome 4 - the version Odoo 18
# ships; ``fa-clipboard-list`` is FA5 and would render as an empty square).
CARD_DEFAULTS = {
    'total_job_card': {
        'name': 'Total Job Card',
        'color': '#4F46E5',
        'icon': 'fa-clipboard',
    },
}

# Prefix of the id the front end receives, so a calculated card can never
# collide with a numeric ``job.card.stage`` id.
SPECIAL_KEY = {
    'total_job_card': 'total_job_card',
}


class JobCardDashboardCard(models.Model):
    _name = 'job.card.dashboard.card'
    _description = 'Job Card Dashboard Calculated Card'
    _order = 'dashboard_sequence, id'

    name = fields.Char(required=True, translate=True)
    card_type = fields.Selection(
        CARD_TYPES, string='Card Type', required=True, readonly=True,
        default='total_job_card',
        help='Which calculated figure this card shows. Calculated cards are '
             'not job card statuses and never appear on the job card itself.',
    )
    is_total_job_card = fields.Boolean(
        string='Is Total Job Card', compute='_compute_is_total_job_card',
        store=True, readonly=True,
    )
    description = fields.Char(
        string='Tooltip',
        default='All open job cards - every status except Closed',
        translate=True,
    )
    dashboard_color = fields.Char(
        string='Dashboard Colour',
        help='Hex colour used for this card on the dashboard, e.g. #4F46E5.',
    )
    dashboard_icon = fields.Char(
        string='Dashboard Icon',
        help='Font Awesome 4 class name without the "fa " prefix, e.g. fa-clipboard.',
    )
    dashboard_sequence = fields.Integer(
        string='Dashboard Order', default=0,
        help='Cards are ordered by this value together with the status cards. '
             'On a tie the calculated card is shown first.',
    )
    show_on_dashboard = fields.Boolean(string='Show on Dashboard', default=True)

    _sql_constraints = [
        ('card_type_unique', 'UNIQUE(card_type)',
         'This calculated card already exists. Edit the existing one instead.'),
    ]

    @api.depends('card_type')
    def _compute_is_total_job_card(self):
        for card in self:
            card.is_total_job_card = card.card_type == 'total_job_card'

    @api.ondelete(at_uninstall=False)
    def _unlink_never(self):
        raise UserError(_(
            'Calculated dashboard cards cannot be deleted. '
            'Untick "On Dashboard" to hide the card instead.'))

    # ------------------------------------------------------------------
    @api.model
    def _ensure_cards(self):
        """Create any missing calculated card (idempotent, safe on upgrade)."""
        existing = set(self.sudo().search([]).mapped('card_type'))
        for card_type, _label in CARD_TYPES:
            if card_type in existing:
                continue
            defaults = CARD_DEFAULTS.get(card_type, {})
            self.sudo().create({
                'card_type': card_type,
                'name': defaults.get('name', _label),
                'dashboard_color': defaults.get('color'),
                'dashboard_icon': defaults.get('icon'),
            })
        return True

    @api.model
    def _dashboard_cards(self):
        """Visible calculated cards, in the same shape as a status card."""
        result = []
        for card in self.search([('show_on_dashboard', '=', True)]):
            defaults = CARD_DEFAULTS.get(card.card_type, {})
            result.append({
                'id': SPECIAL_KEY[card.card_type],
                'name': card.name,
                'value': '',
                'color': (card.dashboard_color or defaults.get('color') or '#6366F1').strip(),
                'icon': (card.dashboard_icon or defaults.get('icon') or 'fa-tasks').strip(),
                'sequence': card.dashboard_sequence or 0,
                'card_type': card.card_type,
                'is_special': True,
                'tooltip': card.description or '',
            })
        return result

    def action_apply_default_style(self):
        """Same "Suggest style" behaviour as the status cards."""
        for card in self:
            defaults = CARD_DEFAULTS.get(card.card_type, {})
            card.write({
                'dashboard_color': defaults.get('color'),
                'dashboard_icon': defaults.get('icon'),
            })
        return True
