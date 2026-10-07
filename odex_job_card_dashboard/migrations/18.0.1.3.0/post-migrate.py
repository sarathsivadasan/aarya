# -*- coding: utf-8 -*-
"""18.0.1.3.0 - Total Job Card.

Existing databases do not run post_init_hook again, so seed here once:
* create the Total Job Card calculated card if the data file has not;
* tick "Closed Status" on the detected closing stage(s), unless an
  administrator already ticked one.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['job.card.dashboard.card']._ensure_cards()
    env['job.card.stage']._seed_closed_stages()
