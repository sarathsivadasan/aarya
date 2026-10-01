# -*- coding: utf-8 -*-
# jobcard.part.requisition already exists in full (parts_request module):
# name (auto-sequenced), job_id, job_cost_sheet_id, employee_id, product_id,
# description, qty, qty_available (related), uom_id, cost_type,
# state = draft/approve/reject (NOT draft/submitted/approved/rejected/issued
# - an earlier version of this module assumed a 'submitted' state that
# does not exist and would have crashed on write).
#
# In the real workflow, creating a line already puts it in 'draft', which
# IS the "awaiting approval" state (see user_approve()/user_reject() in
# parts_request/models/parts_requisition.py) - there is no separate
# technician-submits step. The portal's "Submit Parts Request" action is
# therefore just "create the line(s)"; nothing further to transition.
#
# `remarks` below is genuinely new (no collision) - free-text instructions
# per line, e.g. "required urgently".

from odoo import fields, models


class JobcardPartRequisition(models.Model):
    _inherit = 'jobcard.part.requisition'

    remarks = fields.Char(string='Remarks')

    # Free-text "Part" column shown and edited in the portal Parts tab.
    # Purely additive - no existing field of this name in parts_request.
    # v5.0.0: this is now the ONLY model behind the Parts tab (the
    # vehicle.inspection.part branch was removed with Vehicle Inspection).
    part = fields.Char(
        string='Part',
        help='Free-text part information entered by the technician from '
             'the Technician Portal Parts tab.')
