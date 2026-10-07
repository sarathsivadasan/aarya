# -*- coding: utf-8 -*-
"""Add Pre/Final Inspection points to job cards created before 18.0.1.2.0."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    tasks = env['project.task'].with_context(active_test=False, tracking_disable=True,
                                             mail_notrack=True).search([('is_jobcard', '=', True)])
    for start in range(0, len(tasks), 500):
        tasks[start:start + 500]._ensure_inspection_points()
    _logger.info("job_card_extension: inspection points ensured on %s job cards", len(tasks))
