# -*- coding: utf-8 -*-
"""Schema adapter for the Odex Technician Overview.

This module NEVER stores workshop data. It resolves, at runtime, which
models and field names exist in the installed database (Odex Garage
Technician Portal, Job Card, Vehicle Inspection, Timesheets) and exposes
a uniform read API on top of them.

All model / field name assumptions live HERE and only here. If a field is
named differently on the target server, add it to the candidate lists
below — nothing else in the module needs to change.
"""
import logging

from odoo import api, models, fields

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Candidate model names (first existing one wins)
# ---------------------------------------------------------------------------
JOB_CARD_MODELS = [
    "job.card",
    "garage.job.card",
    "workshop.job.card",
    "vehicle.job.card",
    "odex.job.card",
]
INSPECTION_MODELS = [
    "vehicle.inspection",
    "garage.vehicle.inspection",
    "fleet.vehicle.inspection",
    "odex.vehicle.inspection",
    "vehicle.inspection.report",
]

# ---------------------------------------------------------------------------
# Candidate field names, per logical role
# ---------------------------------------------------------------------------
FIELD_CANDIDATES = {
    "technician": ["technician_id", "mechanic_id", "assigned_technician_id",
                   "employee_id", "technician_ids"],
    "vehicle": ["vehicle_id", "fleet_vehicle_id"],
    "customer": ["customer_id", "partner_id", "client_id"],
    "advisor": ["service_advisor_id", "advisor_id", "sale_advisor_id",
                "user_id"],
    "state": ["state", "status"],
    "stage": ["stage_id"],
    "operation": ["operation", "service_type_id", "repair_type_id",
                  "description", "name"],
    "remarks": ["remarks", "note", "notes", "internal_notes"],
    "start_time": ["start_time", "actual_start_time", "date_start",
                   "start_datetime", "timer_start"],
    "end_time": ["end_time", "actual_end_time", "date_end",
                 "end_datetime", "timer_end"],
    "pause_time": ["pause_time", "last_pause_time", "timer_pause"],
    "resume_time": ["resume_time", "last_resume_time", "timer_resume"],
    "standard_hours": ["standard_time", "std_time", "standard_hours",
                       "planned_hours", "allocated_hours", "expected_time"],
    "actual_hours": ["actual_time", "actual_hours", "elapsed_time",
                     "total_time", "duration"],
    "pause_duration": ["pause_duration", "total_pause_time", "break_time"],
    "date": ["date", "create_date"],
    "department": ["department_id"],
    "team": ["team_id"],
    "workshop": ["workshop_id", "branch_id", "company_id"],
}

# Normalised status buckets. Raw state values are lower-cased and matched.
STATE_BUCKETS = {
    "working": {"in_progress", "progress", "working", "started", "start",
                "running", "ongoing", "wip"},
    "paused": {"pause", "paused", "on_hold", "hold", "waiting"},
    "completed": {"done", "completed", "complete", "closed", "finished",
                  "ready", "invoiced", "delivered"},
    "idle": {"draft", "new", "pending", "to_do", "assigned", "open"},
    "cancelled": {"cancel", "cancelled", "canceled"},
}


class OdexOverviewAdapter(models.AbstractModel):
    _name = "odex.overview.adapter"
    _description = "Odex Overview Schema Adapter"

    # -- resolution -------------------------------------------------------
    @api.model
    def _resolve_model(self, candidates):
        for name in candidates:
            if name in self.env and self.env[name]._auto:
                return name
        return None

    @api.model
    def job_card_model(self):
        return self._resolve_model(JOB_CARD_MODELS)

    @api.model
    def inspection_model(self):
        return self._resolve_model(INSPECTION_MODELS)

    @api.model
    def _field(self, model_name, role):
        """Return the concrete field name for a logical role, or None."""
        if not model_name:
            return None
        model_fields = self.env[model_name]._fields
        for candidate in FIELD_CANDIDATES.get(role, []):
            if candidate in model_fields:
                return candidate
        return None

    @api.model
    def field_map(self, model_name):
        """Full role -> field-name map for one model (cached per registry)."""
        return {
            role: self._field(model_name, role)
            for role in FIELD_CANDIDATES
        }

    # -- helpers ----------------------------------------------------------
    @api.model
    def normalize_state(self, raw_state):
        if not raw_state:
            return "idle"
        raw = str(raw_state).lower()
        for bucket, values in STATE_BUCKETS.items():
            if raw in values:
                return bucket
        return "idle"

    @api.model
    def to_hours(self, value):
        """Standard/actual time fields may be float hours or char 'HH:MM'."""
        if not value:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            parts = str(value).split(":")
            return int(parts[0]) + int(parts[1]) / 60.0
        except (ValueError, IndexError):
            return 0.0

    @api.model
    def read_document(self, record, fmap):
        """Uniform dict for one job card / inspection record."""
        def m2o(role):
            fname = fmap.get(role)
            if not fname:
                return (False, "")
            val = record[fname]
            if isinstance(val, models.BaseModel):
                val = val[:1]
                return (val.id, val.display_name) if val else (False, "")
            return (False, str(val) if val else "")

        def raw(role, default=False):
            fname = fmap.get(role)
            return record[fname] if fname else default

        def dt(role):
            val = raw(role)
            return fields.Datetime.to_string(val) if val else False

        tech_id, tech_name = m2o("technician")
        veh_id, veh_name = m2o("vehicle")
        cust_id, cust_name = m2o("customer")
        adv_id, adv_name = m2o("advisor")
        stage_id, stage_name = m2o("stage")

        state_raw = raw("state") or (stage_name or "")
        operation = raw("operation")
        if isinstance(operation, models.BaseModel):
            operation = operation.display_name

        vehicle_rec = False
        if fmap.get("vehicle") and record[fmap["vehicle"]]:
            vehicle_rec = record[fmap["vehicle"]][:1]
        registration = ""
        if vehicle_rec and "license_plate" in vehicle_rec._fields:
            registration = vehicle_rec.license_plate or ""

        return {
            "id": record.id,
            "model": record._name,
            "name": record.display_name,
            "technician_id": tech_id,
            "technician": tech_name,
            "vehicle_id": veh_id,
            "vehicle": veh_name,
            "registration": registration,
            "customer_id": cust_id,
            "customer": cust_name,
            "advisor_id": adv_id,
            "advisor": adv_name,
            "operation": operation or "",
            "remarks": raw("remarks") or "",
            "state_raw": state_raw,
            "status": self.normalize_state(state_raw),
            "stage": stage_name,
            "start_time": dt("start_time"),
            "end_time": dt("end_time"),
            "pause_time": dt("pause_time"),
            "resume_time": dt("resume_time"),
            "standard_hours": self.to_hours(raw("standard_hours")),
            "actual_hours": self.to_hours(raw("actual_hours")),
            "pause_hours": self.to_hours(raw("pause_duration")),
            "date": dt("date") or dt("start_time"),
        }
