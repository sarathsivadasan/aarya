# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Pre Inspection / Final Inspection tabs.

    * Existing ins.qc.checklist lines (the old inspection checklist) become Pre Inspection.
    * Open job cards created before this version get the default Pre / Final Inspection
      lines, so the tabs are filled when they are reopened. Closed job cards are left as
      they are; their tab shows a "Load ... Checklist" button instead.
    """
    if not version:
        return
    cr.execute("UPDATE ins_qc_checklist SET inspection_type = 'pre' WHERE inspection_type IS NULL")

    env = api.Environment(cr, SUPERUSER_ID, {})
    Task = env['project.task'].with_context(active_test=False)
    domain = [('is_jobcard', '=', True)]
    is_close = Task._fields.get('is_close')
    if is_close is not None and is_close.store:
        domain.append(('is_close', '=', False))
    tasks = Task.search(domain)
    _logger.info("job_card_extension: loading Pre / Final Inspection checklists on %s job cards", len(tasks))
    for start in range(0, len(tasks), 500):
        batch = tasks[start:start + 500]
        batch._load_inspection_checklist('pre')
        batch._load_inspection_checklist('final')
