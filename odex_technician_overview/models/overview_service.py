# -*- coding: utf-8 -*-
"""Live dashboard data service. Read-only, no stored records.

SINGLE SOURCE OF TRUTH
======================
Primary path (_collect_from_portal): reads the exact same records the
Odex Garage Technician Portal reads — account.analytic.line rows
(task.job_card_daily_report_ids) whose task is a Job Card
(task_id.is_jobcard) or a Vehicle Inspection (task_id.is_vc), with the
technician on `employees_id`. Status, elapsed time and display times are
NOT recalculated here: they are delegated to the portal's own
`technician_status` compute, `_elapsed_seconds()` and `_display_dt()`,
so both screens can never disagree.

Fallback path (_collect_from_adapter): the original generic adapter,
kept only for databases where the portal is not installed.

Performance: one search on account.analytic.line per refresh with a
bounded domain; all task/vehicle/partner values resolved through
recordset prefetching (no per-row browse loops with fresh queries).
"""
from datetime import datetime, timedelta, time

import pytz

from odoo import api, models, fields

OPEN_STATUSES = ("working", "paused", "delayed", "assigned")


class OdexTechnicianOverview(models.AbstractModel):
    _name = "odex.technician.overview"
    _description = "Odex Technician Overview Service"

    # ------------------------------------------------------------------
    # Portal availability
    # ------------------------------------------------------------------
    @api.model
    def _portal_available(self):
        if "account.analytic.line" not in self.env or \
                "project.task" not in self.env:
            return False
        AAL = self.env["account.analytic.line"]
        Task = self.env["project.task"]
        return ("employees_id" in AAL._fields
                and "is_jobcard" in Task._fields
                and "is_vc" in Task._fields
                and hasattr(AAL, "_elapsed_seconds")
                and hasattr(AAL, "_is_paused"))

    # ------------------------------------------------------------------
    # Security scoping
    # ------------------------------------------------------------------
    @api.model
    def _allowed_technician_ids(self):
        """hr.employee ids the current user may see; None = unrestricted."""
        user = self.env.user
        if user.has_group("odex_technician_overview.group_overview_manager") \
                or user.has_group("base.group_system"):
            return None
        Employee = self.env["hr.employee"].sudo()
        if user.has_group("odex_technician_overview.group_overview_advisor"):
            ids = set()
            if self._portal_available():
                # Advisor = project.task.user_ids ("Service Advisor" in
                # job_card_extension). Technicians of their tasks come
                # from the tasks' analytic lines.
                lines = self.env["account.analytic.line"].sudo().search([
                    ("employees_id", "!=", False),
                    ("task_id.user_ids", "in", user.id),
                    "|", ("task_id.is_jobcard", "=", True),
                    ("task_id.is_vc", "=", True),
                ])
                ids = set(lines.mapped("employees_id").ids)
            else:
                ids = self._adapter_advisor_technician_ids(user)
            return list(ids)
        emps = Employee.search([("user_id", "=", user.id)])
        return emps.ids

    @api.model
    def _adapter_advisor_technician_ids(self, user):
        ids = set()
        adapter = self.env["odex.overview.adapter"]
        Employee = self.env["hr.employee"].sudo()
        for model_name in (adapter.job_card_model(),
                           adapter.inspection_model()):
            if not model_name:
                continue
            fmap = adapter.field_map(model_name)
            if not fmap.get("advisor") or not fmap.get("technician"):
                continue
            Model = self.env[model_name].sudo()
            adv_field = fmap["advisor"]
            adv_target = Model._fields[adv_field].comodel_name
            if adv_target == "res.users":
                adv_val = user.id
            else:
                emp = Employee.search([("user_id", "=", user.id)], limit=1)
                adv_val = emp.id
            if not adv_val:
                continue
            groups = Model._read_group(
                [(adv_field, "=", adv_val)],
                groupby=[fmap["technician"]], aggregates=["__count"],
            )
            for tech, _count in groups:
                if tech:
                    ids.add(tech.id)
        return ids

    # ------------------------------------------------------------------
    # Date helpers
    # ------------------------------------------------------------------
    @api.model
    def _tz(self):
        return pytz.timezone(self.env.user.tz or "UTC")

    @api.model
    def _date_range(self, period, date_from=None, date_to=None):
        """(date, date) window in local terms. Used against the analytic
        line's `date` field, which job_card_extension fills in the same
        local (Dubai) convention as its datetimes."""
        today = datetime.now(self._tz()).date()
        if period == "today":
            start, end = today, today
        elif period == "yesterday":
            start = end = today - timedelta(days=1)
        elif period == "week":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
        elif period == "last_week":
            end = today - timedelta(days=today.weekday() + 1)
            start = end - timedelta(days=6)
        elif period == "last_7":
            start, end = today - timedelta(days=6), today
        elif period == "month":
            start, end = today.replace(day=1), today
        elif period == "last_month":
            first = today.replace(day=1)
            end = first - timedelta(days=1)
            start = end.replace(day=1)
        elif period == "quarter":
            q = (today.month - 1) // 3
            start, end = today.replace(month=q * 3 + 1, day=1), today
        elif period == "year":
            start, end = today.replace(month=1, day=1), today
        elif period == "custom" and date_from and date_to:
            start = fields.Date.from_string(date_from)
            end = fields.Date.from_string(date_to)
        else:
            start, end = today, today
        return start, end

    @api.model
    def _range_utc(self, period, date_from=None, date_to=None):
        start, end = self._date_range(period, date_from, date_to)
        tz = self._tz()
        start_dt = tz.localize(datetime.combine(start, time.min))
        end_dt = tz.localize(datetime.combine(end, time.max))
        return (start_dt.astimezone(pytz.utc).replace(tzinfo=None),
                end_dt.astimezone(pytz.utc).replace(tzinfo=None))

    # ------------------------------------------------------------------
    # PRIMARY: collect from the Technician Portal's own records
    # ------------------------------------------------------------------
    @api.model
    def _collect_from_portal(self, filters):
        AAL = self.env["account.analytic.line"].sudo()
        allowed = self._allowed_technician_ids()
        d_start, d_end = self._date_range(
            filters.get("period", "today"),
            filters.get("date_from"), filters.get("date_to"))

        work_type = filters.get("work_type")
        if work_type == "job_card":
            type_dom = [("task_id.is_jobcard", "=", True)]
        elif work_type == "inspection":
            type_dom = [("task_id.is_vc", "=", True)]
        else:
            type_dom = ["|", ("task_id.is_jobcard", "=", True),
                        ("task_id.is_vc", "=", True)]

        # In window, OR still open (started/assigned and not ended) so a
        # job started before the window and still active stays visible.
        domain = [("employees_id", "!=", False)] + type_dom + [
            "|",
            "&", ("date", ">=", d_start), ("date", "<=", d_end),
            ("is_end_time", "=", False),
        ]
        if allowed is not None:
            domain.append(("employees_id", "in", allowed))
        if filters.get("technician_id"):
            domain.append(
                ("employees_id", "=", int(filters["technician_id"])))
        if filters.get("department_id"):
            domain.append(("employees_id.department_id", "=",
                           int(filters["department_id"])))
        if filters.get("advisor_id"):
            domain.append(
                ("task_id.user_ids", "in", int(filters["advisor_id"])))
        if filters.get("vehicle_id"):
            domain.append(
                ("task_id.vehicle_id", "=", int(filters["vehicle_id"])))
        if filters.get("customer_id"):
            domain.append(
                ("task_id.partner_id", "=", int(filters["customer_id"])))

        lines = AAL.search(domain, order="id desc", limit=4000)
        # prefetch related records in bulk
        lines.mapped("task_id.vehicle_id.license_plate")
        lines.mapped("task_id.partner_id.name")
        lines.mapped("employees_id.department_id")

        docs = []
        for line in lines:
            task = line.task_id
            if not task:
                continue
            vehicle = task.vehicle_id if "vehicle_id" in task._fields \
                else False
            partner = task.partner_id
            advisor = task.user_ids[:1] if task.user_ids else False

            # --- portal-owned logic, reused verbatim ---
            raw_status = line.technician_status  # portal compute
            elapsed_h = line._elapsed_seconds() / 3600.0
            is_ticking = raw_status == "running"

            status = {
                "running": "working",
                "paused": "paused",
                "completed": "completed",
                "not_started": "assigned",
            }.get(raw_status, "assigned")

            # standard time: same figure the portal shows as
            # "Allocated Hours" (sum of requested services' assign_hours)
            if "requested_services_ids" in task._fields:
                standard = sum(
                    task.requested_services_ids.mapped("assign_hours"))
            elif "allocated_hours" in task._fields:
                standard = task.allocated_hours or 0.0
            else:
                standard = 0.0

            # stage: job card CC stage, else inspection state
            stage = ""
            if "cc_stage_id" in task._fields and task.cc_stage_id:
                stage = task.cc_stage_id.name
            elif task.is_vc and "inspection_state" in task._fields \
                    and task.inspection_state:
                sel = dict(task._fields["inspection_state"].selection or [])
                stage = sel.get(task.inspection_state,
                                task.inspection_state)

            def short_dt(dt_val):
                # employee-tz display via the portal's own _display_dt
                # ('dd/mm/YYYY HH:MM') -> keep it compact for the table
                disp = line._display_dt(dt_val)
                return disp.split(" ")[1] if disp else False

            operation = line.product_id.display_name \
                if line.product_id else (line.name or "")
            doc_number = (task.number if task.is_jobcard
                          and getattr(task, "number", False)
                          else task.name) or ""

            docs.append({
                "id": line.id,
                "model": "account.analytic.line",
                "task_id": task.id,
                "name": doc_number,
                "technician_id": line.employees_id.id,
                "technician": line.employees_id.display_name,
                "vehicle_id": vehicle.id if vehicle else False,
                "vehicle": vehicle.display_name if vehicle else "",
                "registration": (vehicle.license_plate or "")
                if vehicle else "",
                "customer_id": partner.id if partner else False,
                "customer": partner.display_name if partner else "",
                "advisor_id": advisor.id if advisor else False,
                "advisor": advisor.name if advisor else "",
                "operation": operation,
                "remarks": "",
                "state_raw": raw_status,
                "status": status,
                "stage": stage,
                "work_type": "job_card" if task.is_jobcard else "inspection",
                "start_time": short_dt(line.start_datetime),
                "pause_time": short_dt(line.pause_datetime),
                "resume_time": short_dt(line.resume_datetime),
                "end_time": short_dt(line.end_datetime),
                "has_ended": bool(line.is_end_time),
                "is_ticking": is_ticking,
                "standard_hours": standard,
                "elapsed_hours": elapsed_h,
                "pause_hours": line.total_pause_time or 0.0,
                "date": fields.Date.to_string(line.date)
                if line.date else False,
            })
        return docs

    # ------------------------------------------------------------------
    # FALLBACK: generic adapter (portal not installed)
    # ------------------------------------------------------------------
    @api.model
    def _collect_from_adapter(self, filters):
        adapter = self.env["odex.overview.adapter"]
        allowed = self._allowed_technician_ids()
        start_utc, end_utc = self._range_utc(
            filters.get("period", "today"),
            filters.get("date_from"), filters.get("date_to"))
        work_type_filter = filters.get("work_type")
        docs, sources = [], []
        if work_type_filter in (None, "", "all", "job_card"):
            sources.append(("job_card", adapter.job_card_model()))
        if work_type_filter in (None, "", "all", "inspection"):
            sources.append(("inspection", adapter.inspection_model()))
        now = fields.Datetime.now()
        for work_type, model_name in sources:
            if not model_name:
                continue
            fmap = adapter.field_map(model_name)
            Model = self.env[model_name].sudo()
            date_field = fmap.get("date") or "create_date"
            if fmap.get("end_time"):
                domain = ["|", "&", (date_field, ">=", start_utc),
                          (date_field, "<=", end_utc),
                          (fmap["end_time"], "=", False)]
            else:
                domain = [(date_field, ">=", start_utc),
                          (date_field, "<=", end_utc)]
            if allowed is not None and fmap.get("technician"):
                domain.append((fmap["technician"], "in", allowed))
            if filters.get("technician_id") and fmap.get("technician"):
                domain.append(
                    (fmap["technician"], "=", int(filters["technician_id"])))
            if filters.get("advisor_id") and fmap.get("advisor"):
                domain.append(
                    (fmap["advisor"], "=", int(filters["advisor_id"])))
            for rec in Model.search(domain, order="id desc", limit=2000):
                doc = adapter.read_document(rec, fmap)
                doc["work_type"] = work_type
                doc["is_ticking"] = doc["status"] == "working"
                doc["has_ended"] = bool(doc["end_time"])
                # elapsed from timestamps
                elapsed = doc["actual_hours"]
                if not elapsed and doc["start_time"]:
                    start = fields.Datetime.from_string(doc["start_time"])
                    end = fields.Datetime.from_string(doc["end_time"]) \
                        if doc["end_time"] else now
                    elapsed = max(
                        (end - start).total_seconds() / 3600.0
                        - (doc["pause_hours"] or 0.0), 0.0)
                doc["elapsed_hours"] = elapsed or 0.0
                docs.append(doc)
        if filters.get("department_id"):
            dep_id = int(filters["department_id"])
            tech_ids = {d["technician_id"] for d in docs
                        if d["technician_id"]}
            emp_map = {
                e["id"]: e["department_id"][0]
                if e["department_id"] else False
                for e in self.env["hr.employee"].sudo().search_read(
                    [("id", "in", list(tech_ids))], ["department_id"])
            }
            docs = [d for d in docs
                    if emp_map.get(d["technician_id"]) == dep_id]
        return docs

    # ------------------------------------------------------------------
    # Common post-processing + public collection API
    # ------------------------------------------------------------------
    @api.model
    def _collect_documents(self, filters):
        if self._portal_available():
            docs = self._collect_from_portal(filters)
        else:
            docs = self._collect_from_adapter(filters)

        for doc in docs:
            std = doc["standard_hours"]
            elapsed = doc["elapsed_hours"]
            # Delayed: exceeded standard time while not completed.
            # Status itself still comes from the portal; this is only the
            # "exceeded" overlay the dashboard needs.
            if doc["status"] in ("working", "paused") and std \
                    and elapsed > std:
                doc["status"] = "delayed"
            doc["variance_hours"] = (elapsed - std) if std else 0.0
            doc["remaining_hours"] = max(std - elapsed, 0.0) if std else 0.0
            doc["productivity"] = self._productivity(
                std, elapsed, doc["status"])

        status_filter = filters.get("status")
        if status_filter and status_filter != "all":
            docs = [d for d in docs if d["status"] == status_filter]
        search = (filters.get("search") or "").strip().lower()
        if search:
            docs = [d for d in docs if search in " ".join([
                d["technician"], d["vehicle"], d["registration"],
                d["customer"], d["name"], d["operation"]]).lower()]
        return docs

    @api.model
    def _productivity(self, std, elapsed, status):
        if status in ("idle", "assigned"):
            return 0
        if not std:
            return 100 if status == "completed" else 0
        if not elapsed:
            return 100
        return round(min(std / elapsed, 1.5) * 100)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, filters=None):
        filters = filters or {}
        docs = self._collect_documents(filters)
        allowed = self._allowed_technician_ids()

        emp_domain = [("id", "in", allowed)] if allowed is not None else []
        if filters.get("department_id"):
            emp_domain.append(
                ("department_id", "=", int(filters["department_id"])))
        employees = self.env["hr.employee"].sudo().search_read(
            emp_domain, ["name", "department_id", "barcode"], limit=500)
        emp_ids = [e["id"] for e in employees]

        # one line per technician for the table:
        # working/delayed > paused > assigned > latest (e.g. completed)
        rank = {"working": 0, "delayed": 0, "paused": 1, "assigned": 2}
        best_by_tech = {}
        for doc in docs:
            tid = doc["technician_id"]
            if not tid:
                continue
            current = best_by_tech.get(tid)
            doc_rank = rank.get(doc["status"], 3)
            if current is None or doc_rank < current[0]:
                best_by_tech[tid] = (doc_rank, doc)

        rows = []
        for emp in employees:
            entry = best_by_tech.get(emp["id"])
            doc = entry[1] if entry else None
            row = {
                "technician_id": emp["id"],
                "technician": emp["name"],
                "employee_code": emp["barcode"] or "",
                "department": emp["department_id"][1]
                if emp["department_id"] else "",
                "avatar": "/web/image/hr.employee/%s/avatar_128" % emp["id"],
                "status": "idle",
                "work_type": "", "document": "", "document_id": False,
                "task_id": False, "model": "", "vehicle": "",
                "registration": "", "customer": "", "operation": "",
                "stage": "", "remarks": "",
                "start_time": False, "pause_time": False,
                "resume_time": False, "end_time": False,
                "is_ticking": False,
                "standard_hours": 0.0, "elapsed_hours": 0.0,
                "variance_hours": 0.0, "remaining_hours": 0.0,
                "productivity": 0,
            }
            if doc:
                row.update({
                    "status": doc["status"],
                    "work_type": doc["work_type"],
                    "document": doc["name"],
                    "document_id": doc["id"],
                    "task_id": doc.get("task_id") or False,
                    "model": doc["model"],
                    "vehicle": doc["vehicle"],
                    "registration": doc["registration"],
                    "customer": doc["customer"],
                    "operation": doc["operation"],
                    "stage": doc["stage"] or doc["state_raw"],
                    "remarks": doc["remarks"],
                    "start_time": doc["start_time"],
                    "pause_time": doc["pause_time"],
                    "resume_time": doc["resume_time"],
                    "end_time": doc["end_time"],
                    "is_ticking": doc.get("is_ticking", False),
                    "standard_hours": doc["standard_hours"],
                    "elapsed_hours": round(doc["elapsed_hours"], 4),
                    "variance_hours": round(doc["variance_hours"], 4),
                    "remaining_hours": round(doc["remaining_hours"], 4),
                    "productivity": doc["productivity"],
                })
            rows.append(row)

        if filters.get("status") and filters["status"] != "all":
            rows = [r for r in rows if r["status"] == filters["status"]]
        search = (filters.get("search") or "").strip().lower()
        if search:
            rows = [r for r in rows if search in " ".join([
                r["technician"], r["vehicle"], r["registration"],
                r["customer"], r["document"], r["operation"]]).lower()]

        return {
            "server_time": fields.Datetime.to_string(fields.Datetime.now()),
            "kpis": self._kpis(rows, docs, emp_ids),
            "rows": rows,
            "charts": self._charts(rows, docs),
            "is_manager": allowed is None,
        }

    @api.model
    def _kpis(self, rows, docs, emp_ids):
        def rcount(status):
            return len([r for r in rows if r["status"] == status])

        prods = [r["productivity"] for r in rows
                 if r["productivity"] and r["status"] not in
                 ("idle", "assigned")]
        repair = [d["elapsed_hours"] for d in docs
                  if d["work_type"] == "job_card" and d["elapsed_hours"]]
        inspect = [d["elapsed_hours"] for d in docs
                   if d["work_type"] == "inspection" and d["elapsed_hours"]]
        return {
            "total_technicians": len(emp_ids),
            "working_now": rcount("working") + rcount("delayed"),
            "paused": rcount("paused"),
            "idle": rcount("idle"),
            "completed_today": len(
                [d for d in docs if d["status"] == "completed"]),
            "delayed_jobs": len(
                [d for d in docs if d["status"] == "delayed"]),
            "avg_productivity": round(sum(prods) / len(prods))
            if prods else 0,
            "avg_repair_hours": round(sum(repair) / len(repair), 2)
            if repair else 0,
            "avg_inspection_hours": round(sum(inspect) / len(inspect), 2)
            if inspect else 0,
            "inspections_running": len(
                [d for d in docs if d["work_type"] == "inspection"
                 and d["status"] in ("working", "paused", "delayed")]),
            "job_cards_running": len(
                [d for d in docs if d["work_type"] == "job_card"
                 and d["status"] in ("working", "paused", "delayed")]),
        }

    @api.model
    def _charts(self, rows, docs):
        prod_labels, prod_values, prod_types = [], [], []
        for r in rows:
            if r["document"]:
                prod_labels.append(r["technician"].split(" ")[0])
                prod_values.append(r["productivity"])
                prod_types.append(r["work_type"])
        std_vs_actual = {
            "labels": [r["technician"].split(" ")[0]
                       for r in rows if r["standard_hours"]],
            "standard": [round(r["standard_hours"], 2)
                         for r in rows if r["standard_hours"]],
            "actual": [round(r["elapsed_hours"], 2)
                       for r in rows if r["standard_hours"]],
        }
        status_counts = {}
        for r in rows:
            status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        delayed_by_tech = {}
        for d in docs:
            if d["status"] == "delayed" and d["technician"]:
                key = d["technician"].split(" ")[0]
                delayed_by_tech[key] = delayed_by_tech.get(key, 0) + 1
        return {
            "productivity": {"labels": prod_labels, "values": prod_values,
                             "types": prod_types},
            "status": status_counts,
            "std_vs_actual": std_vs_actual,
            "delayed": {"labels": list(delayed_by_tech.keys()),
                        "values": list(delayed_by_tech.values())},
            "work_type": {
                "job_card": len([d for d in docs
                                 if d["work_type"] == "job_card"]),
                "inspection": len([d for d in docs
                                   if d["work_type"] == "inspection"]),
            },
        }

    # ------------------------------------------------------------------
    @api.model
    def get_filter_options(self):
        allowed = self._allowed_technician_ids()
        emp_domain = [("id", "in", allowed)] if allowed is not None else []
        Employee = self.env["hr.employee"].sudo()
        techs = Employee.search_read(
            emp_domain, ["name", "department_id"], limit=500)
        techs = [{
            "id": t["id"], "name": t["name"],
            "department_id": t["department_id"][0]
            if t["department_id"] else False,
        } for t in techs]
        deps = self.env["hr.department"].sudo().search_read([], ["name"])
        advisors = self.env["res.users"].sudo().search_read(
            [("share", "=", False)], ["name"], limit=200)
        return {"technicians": techs, "departments": deps,
                "advisors": advisors}
