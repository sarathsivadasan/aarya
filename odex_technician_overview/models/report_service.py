# -*- coding: utf-8 -*-
"""Reporting service. All reports are computed live from the source
documents collected by odex.technician.overview — no reporting tables."""
from collections import defaultdict
from datetime import datetime

from odoo import api, models, fields

REPORT_TYPES = [
    "productivity", "job_card", "inspection",
    "time_analysis", "attendance", "workshop",
]


class OdexOverviewReport(models.AbstractModel):
    _name = "odex.overview.report"
    _description = "Odex Overview Report Service"

    # ------------------------------------------------------------------
    @api.model
    def get_report(self, filters=None):
        filters = dict(filters or {})
        report_type = filters.get("report_type", "productivity")
        Overview = self.env["odex.technician.overview"]
        docs = Overview._collect_documents(filters)
        method = getattr(self, "_report_%s" % report_type,
                         self._report_productivity)
        data = method(docs, filters)
        data["report_type"] = report_type
        data["generated_at"] = fields.Datetime.to_string(
            fields.Datetime.now())
        data["trend"] = self._trend(docs, filters.get("group_by", "day"))
        return data

    # ------------------------------------------------------------------
    @api.model
    def _period_key(self, doc, group_by):
        if not doc.get("date"):
            return "unknown"
        dt = fields.Datetime.from_string(doc["date"])
        if group_by == "day":
            return dt.strftime("%Y-%m-%d")
        if group_by == "week":
            return "%s-W%02d" % (dt.isocalendar()[0], dt.isocalendar()[1])
        if group_by == "month":
            return dt.strftime("%Y-%m")
        if group_by == "quarter":
            return "%s-Q%d" % (dt.year, (dt.month - 1) // 3 + 1)
        if group_by == "year":
            return str(dt.year)
        return dt.strftime("%Y-%m-%d")

    @api.model
    def _trend(self, docs, group_by):
        buckets = defaultdict(lambda: {"count": 0, "completed": 0,
                                       "prod": [], "std": 0.0, "actual": 0.0})
        for d in docs:
            key = self._period_key(d, group_by)
            b = buckets[key]
            b["count"] += 1
            if d["status"] == "completed":
                b["completed"] += 1
            if d["productivity"]:
                b["prod"].append(d["productivity"])
            b["std"] += d["standard_hours"]
            b["actual"] += d["elapsed_hours"]
        labels = sorted(k for k in buckets if k != "unknown")
        return {
            "labels": labels,
            "jobs": [buckets[k]["count"] for k in labels],
            "completed": [buckets[k]["completed"] for k in labels],
            "productivity": [
                round(sum(buckets[k]["prod"]) / len(buckets[k]["prod"]))
                if buckets[k]["prod"] else 0 for k in labels],
            "standard": [round(buckets[k]["std"], 2) for k in labels],
            "actual": [round(buckets[k]["actual"], 2) for k in labels],
        }

    # ------------------------------------------------------------------
    @api.model
    def _by_technician(self, docs):
        per = defaultdict(list)
        for d in docs:
            if d["technician"]:
                per[(d["technician_id"], d["technician"])].append(d)
        return per

    @api.model
    def _report_productivity(self, docs, filters):
        rows = []
        for (tid, name), items in sorted(self._by_technician(docs).items(),
                                         key=lambda kv: kv[0][1]):
            completed = [d for d in items if d["status"] == "completed"]
            delayed = [d for d in items if d["status"] == "delayed"]
            pending = [d for d in items
                       if d["status"] in ("idle", "assigned", "working", "paused")]
            repair = [d["elapsed_hours"] for d in items
                      if d["work_type"] == "job_card" and d["elapsed_hours"]]
            inspect = [d["elapsed_hours"] for d in items
                       if d["work_type"] == "inspection"
                       and d["elapsed_hours"]]
            std = sum(d["standard_hours"] for d in items)
            actual = sum(d["elapsed_hours"] for d in items)
            pause = sum(d["pause_hours"] for d in items)
            exceeded = sum(max(d["variance_hours"], 0) for d in items)
            prods = [d["productivity"] for d in items if d["productivity"]]
            rows.append({
                "technician_id": tid, "technician": name,
                "assigned": len(items), "completed": len(completed),
                "pending": len(pending), "delayed": len(delayed),
                "productivity": round(sum(prods) / len(prods))
                if prods else 0,
                "efficiency": round(std / actual * 100) if actual else 0,
                "avg_repair": round(sum(repair) / len(repair), 2)
                if repair else 0,
                "avg_inspection": round(sum(inspect) / len(inspect), 2)
                if inspect else 0,
                "working_hours": round(actual, 2),
                "pause_hours": round(pause, 2),
                "standard_hours": round(std, 2),
                "actual_hours": round(actual, 2),
                "exceeded_hours": round(exceeded, 2),
                "overtime_hours": round(max(actual - 8.0, 0), 2),
            })
        return {"title": "Technician Productivity Report", "rows": rows,
                "columns": [
                    ("technician", "Technician"), ("assigned", "Assigned"),
                    ("completed", "Completed"), ("pending", "Pending"),
                    ("delayed", "Delayed"),
                    ("productivity", "Productivity %"),
                    ("efficiency", "Efficiency %"),
                    ("avg_repair", "Avg Repair (h)"),
                    ("avg_inspection", "Avg Inspection (h)"),
                    ("working_hours", "Working (h)"),
                    ("pause_hours", "Pause (h)"),
                    ("standard_hours", "Standard (h)"),
                    ("actual_hours", "Actual (h)"),
                    ("exceeded_hours", "Exceeded (h)"),
                    ("overtime_hours", "Overtime (h)"),
                ]}

    @api.model
    def _report_job_card(self, docs, filters):
        docs = [d for d in docs if d["work_type"] == "job_card"]
        return self._doc_summary(docs, "Job Card Report")

    @api.model
    def _report_inspection(self, docs, filters):
        docs = [d for d in docs if d["work_type"] == "inspection"]
        return self._doc_summary(docs, "Vehicle Inspection Report")

    @api.model
    def _doc_summary(self, docs, title):
        rows = []
        for (tid, name), items in sorted(self._by_technician(docs).items(),
                                         key=lambda kv: kv[0][1]):
            completed = [d for d in items if d["status"] == "completed"]
            times = [d["elapsed_hours"] for d in completed
                     if d["elapsed_hours"]]
            rows.append({
                "technician_id": tid, "technician": name,
                "total": len(items), "completed": len(completed),
                "pending": len([d for d in items if d["status"] in
                                ("idle", "assigned", "working", "paused")]),
                "delayed": len([d for d in items
                                if d["status"] == "delayed"]),
                "avg_completion": round(sum(times) / len(times), 2)
                if times else 0,
            })
        totals = {
            "total": sum(r["total"] for r in rows),
            "completed": sum(r["completed"] for r in rows),
            "pending": sum(r["pending"] for r in rows),
            "delayed": sum(r["delayed"] for r in rows),
        }
        return {"title": title, "rows": rows, "totals": totals,
                "columns": [
                    ("technician", "Technician"), ("total", "Total"),
                    ("completed", "Completed"), ("pending", "Pending"),
                    ("delayed", "Delayed"),
                    ("avg_completion", "Avg Completion (h)"),
                ]}

    @api.model
    def _report_time_analysis(self, docs, filters):
        rows = []
        for d in sorted(docs, key=lambda x: (x["technician"], x["name"])):
            rows.append({
                "technician": d["technician"], "document": d["name"],
                "work_type": "Job Card" if d["work_type"] == "job_card"
                else "Vehicle Inspection",
                "standard_hours": round(d["standard_hours"], 2),
                "actual_hours": round(d["elapsed_hours"], 2),
                "variance_hours": round(d["variance_hours"], 2),
                "exceeded_hours": round(max(d["variance_hours"], 0), 2),
                "pause_hours": round(d["pause_hours"], 2),
                "status": d["status"].title(),
            })
        return {"title": "Time Analysis Report", "rows": rows,
                "columns": [
                    ("technician", "Technician"), ("document", "Document"),
                    ("work_type", "Type"),
                    ("standard_hours", "Standard (h)"),
                    ("actual_hours", "Actual (h)"),
                    ("variance_hours", "Variance (h)"),
                    ("exceeded_hours", "Exceeded (h)"),
                    ("pause_hours", "Pause (h)"), ("status", "Status"),
                ]}

    @api.model
    def _report_attendance(self, docs, filters):
        """Attendance summary from hr.attendance if installed, else derived
        from first start / last end per technician per day."""
        rows = []
        Overview = self.env["odex.technician.overview"]
        start_utc, end_utc = Overview._range_utc(
            filters.get("period", "today"),
            filters.get("date_from"), filters.get("date_to"))
        allowed = Overview._allowed_technician_ids()
        if "hr.attendance" in self.env:
            domain = [("check_in", ">=", start_utc),
                      ("check_in", "<=", end_utc)]
            if allowed is not None:
                domain.append(("employee_id", "in", allowed))
            atts = self.env["hr.attendance"].sudo().search_read(
                domain, ["employee_id", "check_in", "check_out",
                         "worked_hours"], limit=5000)
            per = defaultdict(list)
            for a in atts:
                per[a["employee_id"]].append(a)
            work_by_tech = defaultdict(float)
            for d in docs:
                if d["technician_id"]:
                    work_by_tech[d["technician_id"]] += d["elapsed_hours"]
            for (eid, ename), items in per.items():
                worked = sum(a["worked_hours"] or 0 for a in items)
                busy = work_by_tech.get(eid, 0.0)
                rows.append({
                    "technician": ename,
                    "login": fields.Datetime.to_string(
                        min(a["check_in"] for a in items)),
                    "logout": fields.Datetime.to_string(
                        max(a["check_out"] for a in items
                            if a["check_out"]))
                    if any(a["check_out"] for a in items) else "",
                    "working_hours": round(worked, 2),
                    "busy_hours": round(busy, 2),
                    "idle_hours": round(max(worked - busy, 0), 2),
                    "overtime_hours": round(max(worked - 8.0, 0), 2),
                })
        else:
            for (tid, name), items in self._by_technician(docs).items():
                starts = [d["start_time"] for d in items if d["start_time"]]
                ends = [d["end_time"] for d in items if d["end_time"]]
                busy = sum(d["elapsed_hours"] for d in items)
                pause = sum(d["pause_hours"] for d in items)
                rows.append({
                    "technician": name,
                    "login": min(starts) if starts else "",
                    "logout": max(ends) if ends else "",
                    "working_hours": round(busy, 2),
                    "busy_hours": round(busy, 2),
                    "idle_hours": round(pause, 2),
                    "overtime_hours": round(max(busy - 8.0, 0), 2),
                })
        rows.sort(key=lambda r: r["technician"])
        return {"title": "Technician Attendance Summary", "rows": rows,
                "columns": [
                    ("technician", "Technician"), ("login", "Login"),
                    ("logout", "Logout"),
                    ("working_hours", "Working (h)"),
                    ("busy_hours", "On Jobs (h)"),
                    ("idle_hours", "Idle/Break (h)"),
                    ("overtime_hours", "Overtime (h)"),
                ]}

    @api.model
    def _report_workshop(self, docs, filters):
        per_day = defaultdict(lambda: {
            "serviced": set(), "inspected": set(), "jobs": 0,
            "times": [], "prods": [], "busy": 0.0})
        for d in docs:
            key = self._period_key(d, filters.get("group_by", "day"))
            b = per_day[key]
            b["jobs"] += 1
            if d["work_type"] == "job_card" and d["vehicle_id"]:
                b["serviced"].add(d["vehicle_id"])
            if d["work_type"] == "inspection" and d["vehicle_id"]:
                b["inspected"].add(d["vehicle_id"])
            if d["status"] == "completed" and d["elapsed_hours"]:
                b["times"].append(d["elapsed_hours"])
            if d["productivity"]:
                b["prods"].append(d["productivity"])
            b["busy"] += d["elapsed_hours"]
        tech_count = len({d["technician_id"] for d in docs
                          if d["technician_id"]}) or 1
        rows = []
        for key in sorted(per_day):
            b = per_day[key]
            rows.append({
                "period": key,
                "serviced": len(b["serviced"]),
                "inspected": len(b["inspected"]),
                "jobs": b["jobs"],
                "avg_completion": round(sum(b["times"]) / len(b["times"]), 2)
                if b["times"] else 0,
                "productivity": round(sum(b["prods"]) / len(b["prods"]))
                if b["prods"] else 0,
                "utilization": round(
                    b["busy"] / (tech_count * 8.0) * 100)
                if tech_count else 0,
            })
        return {"title": "Daily Workshop Performance", "rows": rows,
                "columns": [
                    ("period", "Period"),
                    ("serviced", "Vehicles Serviced"),
                    ("inspected", "Vehicles Inspected"),
                    ("jobs", "Total Jobs"),
                    ("avg_completion", "Avg Completion (h)"),
                    ("productivity", "Productivity %"),
                    ("utilization", "Utilization %"),
                ]}
