# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Recompute is_yes_no on existing 50 Points lines with the new rule."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['quality.checklist'].with_context(active_test=False).search([])
    if lines:
        env.add_to_compute(lines._fields['is_yes_no'], lines)
        lines.flush_recordset(['is_yes_no'])
