# -*- coding: utf-8 -*-
"""JSON endpoints for the gate pass front-end.

All endpoints are ``auth="user"`` and route through the ORM, so record rules
and access rights apply.  API keys are never sent here - the OCR key stays in
system parameters and is only read server side.
"""
import logging

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class GatePassController(http.Controller):

    def _gate_pass(self, gate_pass_id):
        record = request.env["odex.gate.pass"].browse(int(gate_pass_id)).exists()
        if not record:
            raise UserError("Gate pass not found.")
        record.check_access("read")
        return record

    @http.route("/odex_gate_pass/ocr/status", type="json", auth="user")
    def ocr_status(self):
        return request.env["odex.ocr.service"].get_status()

    @http.route("/odex_gate_pass/ocr/scan", type="json", auth="user")
    def ocr_scan(self, gate_pass_id, image, kind="plate"):
        record = self._gate_pass(gate_pass_id)
        record.check_access("write")
        try:
            if kind == "mulkiya":
                return record.ocr_scan_mulkiya(image)
            return record.ocr_scan_plate(image)
        except (UserError, AccessError) as err:
            return {"error": str(err)}

    @http.route("/odex_gate_pass/ocr/apply", type="json", auth="user")
    def ocr_apply(self, gate_pass_id, values):
        record = self._gate_pass(gate_pass_id)
        record.check_access("write")
        try:
            return record.apply_scan_result(values)
        except (UserError, AccessError) as err:
            return {"error": str(err)}

    @http.route("/odex_gate_pass/vehicle/lookup", type="json", auth="user")
    def vehicle_lookup(self, gate_pass_id):
        record = self._gate_pass(gate_pass_id)
        record.check_access("write")
        try:
            record.action_lookup_vehicle()
            return {
                "vehicle_id": record.vehicle_id.id,
                "vehicle_name": record.vehicle_id.display_name,
            }
        except (UserError, AccessError) as err:
            return {"error": str(err)}

    @http.route("/odex_gate_pass/photo/add", type="json", auth="user")
    def photo_add(self, gate_pass_id, image, photo_type="other", caption=None):
        record = self._gate_pass(gate_pass_id)
        record.check_access("write")
        try:
            photo = request.env["odex.gate.pass.photo"].create({
                "gate_pass_id": record.id,
                "image": image,
                "photo_type": photo_type,
                "caption": caption or False,
            })
            return {"photo_id": photo.id, "photo_count": len(record.photo_ids)}
        except (UserError, AccessError) as err:
            return {"error": str(err)}
