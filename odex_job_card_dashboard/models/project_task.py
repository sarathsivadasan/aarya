# -*- coding: utf-8 -*-
"""Live push: whenever something a dashboard widget shows changes, tell the
open dashboards to reload. No polling delay, no page reload."""
import logging

from odoo import models

_logger = logging.getLogger(__name__)

DASHBOARD_CHANNEL = 'job_card_dashboard'

# Any of these fields changing makes at least one widget stale.
TRIGGER_FIELDS = {
    'cc_stage_id', 'cc_stage_value', 'stage_id', 'state',
    'promise_date', 'date_end', 'date_deadline', 'is_close',
    'inspection_state', 'bay_id', 'priority',
    'user_ids', 'employees_id', 'employee_ids', 'technician_id',
    'vehicle_id', 'partner_id', 'number',
}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def _notify_job_card_dashboard(self, reason='write'):
        """Broadcast a lightweight refresh signal (no record data travels)."""
        try:
            self.env['bus.bus']._sendone(
                DASHBOARD_CHANNEL, 'job_card_dashboard/refresh', {'reason': reason},
            )
        except Exception:  # pragma: no cover - never break a business write
            _logger.debug('Job card dashboard bus notification failed', exc_info=True)

    def write(self, vals):
        result = super().write(vals)
        if TRIGGER_FIELDS.intersection(vals.keys()):
            self._notify_job_card_dashboard('write')
        return result

    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks._notify_job_card_dashboard('create')
        return tasks

    def unlink(self):
        self._notify_job_card_dashboard('unlink')
        return super().unlink()
