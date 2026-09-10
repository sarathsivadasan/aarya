# -*- coding: utf-8 -*-
#
# v4.0.0 - PART FIELD (requirement 2)
# =====================================================================
# `part` (Char) already exists on vehicle.inspection.part - you added it.
# It is deliberately NOT redeclared here: redeclaring would shadow the
# definition you own and could change its string/help/size behind your
# back. Everything below reads and writes it through the ORM and guards
# with `'part' in self._fields`, so if the field is ever renamed this
# degrades to "no part column" instead of crashing.
#
# WHAT THIS FILE DOES
# -------------------
# vehicle.inspection.part.inspection_id points at a project.task. A
# Vehicle Inspection and a Job Card are two different project.task rows,
# so the same physical part can be represented by one line on each. The
# requirement is that editing `part` in the Parts tab updates BOTH sides
# without creating duplicates.
#
# We therefore:
#   1. discover the counterpart task at runtime (_linked_part_tasks on
#      project.task) by probing for a many2one that links the two tasks -
#      no hardcoded field name, because the linking field lives in
#      vehicle_inspection_report / job_card and differs by install;
#   2. find the MATCHING line on that task (same product, else same
#      part_no, else same part text) and UPDATE it;
#   3. never create a line during propagation. If the counterpart has no
#      matching line there is nothing to duplicate into - the value stays
#      visible through the read-side fallback below instead.
#
# Recursion is stopped with a context flag, so A -> B -> A terminates.

from odoo import api, fields, models, _

SYNC_FLAG = 'tp_part_sync'


class VehicleInspectionPart(models.Model):
    _inherit = 'vehicle.inspection.part'

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @api.model
    def _has_part_field(self):
        return 'part' in self._fields

    def _part_value(self):
        """This line's own `part` text, or '' when the field is absent."""
        self.ensure_one()
        return (self.part or '') if self._has_part_field() else ''

    def _counterpart_lines(self):
        """Lines on the linked Job Card / Vehicle Inspection that describe
        the SAME part as this one. Matching is by product first (the only
        reliable key), then part number, then the part text itself."""
        self.ensure_one()
        task = self.inspection_id
        # inspection_id is a project.task on the reviewed schema; the
        # hasattr guard means a differently-wired install degrades to
        # "no counterpart" rather than raising.
        if not task or not hasattr(task, '_linked_part_tasks'):
            return self.browse()
        others = task._linked_part_tasks()
        if not others:
            return self.browse()
        candidates = self.sudo().search([
            ('inspection_id', 'in', others.ids),
            ('id', '!=', self.id),
        ])
        if not candidates:
            return self.browse()
        if self.product_id:
            matched = candidates.filtered(
                lambda l, p=self.product_id: l.product_id.id == p.id)
            if matched:
                return matched
        if self.part_no:
            matched = candidates.filtered(
                lambda l, n=self.part_no: (l.part_no or '') == n)
            if matched:
                return matched
        own = self._part_value()
        if own:
            matched = candidates.filtered(lambda l, v=own: l._part_value() == v)
            if matched:
                return matched
        return self.browse()

    def effective_part(self):
        """The value to SHOW in the Parts tab.

        Own value wins. When this line has no part text yet but the
        counterpart record (the related Job Card, or the Vehicle
        Inspection the Job Card came from) does, that value is surfaced
        instead so the technician sees the part information that already
        exists rather than an empty box. The origin is returned alongside
        so the UI can label it.
        """
        self.ensure_one()
        own = self._part_value()
        if own:
            return own, 'own'
        for other in self._counterpart_lines():
            value = other._part_value()
            if value:
                task = other.inspection_id
                source = 'job_card' if task.is_jobcard else (
                    'inspection' if task.is_vc else 'related')
                return value, source
        return '', 'own'

    # ------------------------------------------------------------------
    # propagation
    # ------------------------------------------------------------------
    def _propagate_part(self):
        """Push this line's `part` onto the matching counterpart line(s).
        Updates in place - never creates - so nothing is duplicated."""
        if not self._has_part_field() or self.env.context.get(SYNC_FLAG):
            return
        for line in self:
            value = line._part_value()
            if not value:
                continue
            targets = line._counterpart_lines().filtered(
                lambda l, v=value: l._part_value() != v)
            if targets:
                targets.with_context(**{SYNC_FLAG: True}).sudo().write({'part': value})

    def _log_part_change(self, value):
        self.ensure_one()
        task = self.inspection_id
        if not task or not hasattr(task, '_add_log'):
            return
        task.sudo()._add_log(
            'Parts Updated',
            _('Part information for %(product)s set to "%(value)s".') % {
                'product': self.product_id.display_name or _('line %s') % self.id,
                'value': value or '-',
            })

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if self._has_part_field() and not self.env.context.get(SYNC_FLAG):
            lines.filtered(lambda l: l._part_value())._propagate_part()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'part' in vals and not self.env.context.get(SYNC_FLAG):
            self._propagate_part()
        return res

    # ------------------------------------------------------------------
    # portal serializer
    # ------------------------------------------------------------------
    def to_portal_dict(self):
        self.ensure_one()
        part_value, part_source = self.effective_part()
        return {
            'id': self.id,
            'model': 'vehicle.inspection.part',
            'part_no': self.part_no or '',
            'part': part_value,
            'part_source': part_source,
            'part_editable': self._has_part_field(),
            'product': self.product_id.display_name,
            'qty': self.quantity,
            'qty_available': self.product_id.qty_available,
            'state': False,
            'remarks': '',
            'cost_type': False,
        }
