# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class WorkshopBooking(models.Model):
    _inherit = 'odex.workshop.booking'

    gate_pass_id = fields.Many2one(
        'fleet.gate.pass', string="Gate Pass", readonly=True, copy=False,
        index=True, ondelete='set null')

    # ------------------------------------------------------------------
    # Mark as Arrived  ->  Gate Pass IN
    # ------------------------------------------------------------------
    def action_mark_arrived(self):
        """Mark the booking as arrived and book the vehicle IN at the gate.

        Both the booking form button and the dashboard "Mark as Arrived"
        button end up here, so one override covers both. The parent method
        validates the state first; if it raises, no gate pass is created.
        """
        super().action_mark_arrived()
        passes = self.env['fleet.gate.pass']
        for rec in self:
            passes |= rec._ensure_gate_pass()
        if len(self) == 1 and passes:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Vehicle IN"),
                    'message': _("Gate Pass %s created.", passes.name),
                    'type': 'success',
                    'sticky': False,
                },
            }
        return True

    def _ensure_gate_pass(self):
        """Create the IN gate pass for this booking unless one is already open."""
        self.ensure_one()
        GatePass = self.env['fleet.gate.pass']
        current = self.gate_pass_id
        if current and current.state in ('in', 'revisit'):
            return GatePass  # vehicle is already booked in; never duplicate
        gate_pass = GatePass.create(GatePass._prepare_vals_from_booking(self))
        self.gate_pass_id = gate_pass.id
        gate_pass.message_post(body=_(
            "Created automatically from booking %s (marked as arrived).",
            self.name))
        self.message_post(body=_(
            "Gate Pass %s created - vehicle IN.", gate_pass.name))
        return gate_pass

    # ------------------------------------------------------------------
    # Navigation / dashboard
    # ------------------------------------------------------------------
    def action_open_gate_pass(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gate Pass'),
            'res_model': 'fleet.gate.pass',
            'view_mode': 'form',
            'res_id': self.gate_pass_id.id,
        }

    @api.model
    def get_booking_detail(self, booking_id):
        detail = super().get_booking_detail(booking_id)
        booking = self.browse(int(booking_id))
        detail['gate_pass'] = booking.gate_pass_id.name or ''
        return detail
