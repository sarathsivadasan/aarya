# -*- coding: utf-8 -*-
"""Seed status colours/icons on install so the dashboard is never grey."""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    try:
        env['job.card.stage']._seed_dashboard_styles()
        env['job.card.dashboard.config'].get_config()
    except Exception:  # pragma: no cover - install must never fail on styling
        _logger.warning('Job card dashboard: could not seed default styles',
                        exc_info=True)
