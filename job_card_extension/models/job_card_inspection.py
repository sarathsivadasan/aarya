# -*- coding: utf-8 -*-
"""Pre Inspection and Final Inspection tabs on the job card.

Both reuse quality.checklist (same model as the QC tab), separated by
quality.checklist.inspection_type."""
from odoo import fields, models

PRE_INSPECTION_POINTS = [
    'Registration card validity',
    'Wheel caps',
    'Spare tyre',
    'Jack / tools',
    'Wipers',
    'Lights',
    'Radio antenna / function',
    'Wind screen / glass',
    'A/c Operation / cooling',
    'Body scratches / dents',
    'Police repair permit (acc. Veh)',
]

FINAL_INSPECTION_POINTS = [
    ('1. BASIC CHECK POINTS – INTERIOR AND EXTERIOR OF THE VEHICLE', [
        'All exterior and interior lights are operational',
        'Headlights are aligned and aimed properly',
        'Exterior & interior cleanliness',
        'All doors, Bonnet, tailgate locks, inner handles operational',
        'Windows, mirrors and other controls are operational',
        'Presence of any warning lights',
        'Body repair conditions (fits and tolerances with paint quality and match)',
    ]),
    ('2. BASIC CHECK POINTS – UNDER HOOD & UNDERNEATH', [
        'All fluids levels are correct',
        'Leaks from any joints, pipes, hoses etc.',
        'All removed components are refixed properly and secured',
        'Leakages from underneath of vehicle',
    ]),
]


def _pre_lines():
    return [(0, 0, {'name': name, 'serial_no': i, 'inspection_type': 'pre', 'check_mark': False})
            for i, name in enumerate(PRE_INSPECTION_POINTS, start=1)]


def _final_lines():
    lines, serial = [], 0
    for section, points in FINAL_INSPECTION_POINTS:
        serial += 1
        lines.append((0, 0, {'name': section, 'display_type': 'line_section',
                             'serial_no': serial, 'inspection_type': 'final', 'check_mark': False}))
        for name in points:
            serial += 1
            lines.append((0, 0, {'name': name, 'serial_no': serial,
                                 'inspection_type': 'final', 'check_mark': False}))
    return lines


class ProjectTaskInspection(models.Model):
    _inherit = 'project.task'

    # Existing QC field keeps its default; the domain only keeps the new
    # Pre/Final lines out of the QC tab.
    quality_checklist_ids = fields.One2many(
        'quality.checklist', 'job_card_id', string="Quality Checklist",
        domain=[('inspection_type', '=', 'qc')],
        default=lambda x: x.get_quality_checklist())
    pre_inspection_ids = fields.One2many(
        'quality.checklist', 'job_card_id', string="Pre Inspection",
        domain=[('inspection_type', '=', 'pre')],
        default=lambda self: _pre_lines())
    final_inspection_ids = fields.One2many(
        'quality.checklist', 'job_card_id', string="Final Inspection",
        domain=[('inspection_type', '=', 'final')],
        default=lambda self: _final_lines())

    def _ensure_inspection_points(self):
        """Give job cards created before this version their checklist points."""
        for task in self.filtered('is_jobcard'):
            vals = {}
            if not task.pre_inspection_ids:
                vals['pre_inspection_ids'] = _pre_lines()
            if not task.final_inspection_ids:
                vals['final_inspection_ids'] = _final_lines()
            if vals:
                task.write(vals)

    def action_load_inspection_points(self):
        self._ensure_inspection_points()
        return True
