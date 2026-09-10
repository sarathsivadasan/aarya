# -*- coding: utf-8 -*-
"""Scheduled report emails. Stores only the schedule configuration —
never report data."""
import base64
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class OdexOverviewReportSchedule(models.Model):
    _name = "odex.overview.report.schedule"
    _description = "Scheduled Overview Report"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    report_type = fields.Selection([
        ("productivity", "Technician Productivity"),
        ("job_card", "Job Card Report"),
        ("inspection", "Vehicle Inspection Report"),
        ("time_analysis", "Time Analysis"),
        ("attendance", "Technician Attendance"),
        ("workshop", "Daily Workshop Performance"),
    ], required=True, default="productivity")
    interval = fields.Selection([
        ("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly"),
    ], required=True, default="daily")
    period = fields.Selection([
        ("today", "Today"), ("yesterday", "Yesterday"),
        ("last_7", "Last 7 Days"), ("week", "This Week"),
        ("last_week", "Last Week"), ("month", "This Month"),
        ("last_month", "Last Month"), ("quarter", "This Quarter"),
        ("year", "This Year"),
    ], required=True, default="yesterday",
        help="Date window the generated report covers.")
    export_format = fields.Selection([
        ("xlsx", "Excel"), ("csv", "CSV"), ("pdf", "PDF"),
    ], required=True, default="xlsx")
    recipient_ids = fields.Many2many("res.partner", string="Recipients",
                                     required=True)
    last_run = fields.Datetime(readonly=True)

    # ------------------------------------------------------------------
    def _due(self, now):
        self.ensure_one()
        if not self.last_run:
            return True
        delta = now - self.last_run
        return {"daily": delta.days >= 1,
                "weekly": delta.days >= 7,
                "monthly": delta.days >= 28}.get(self.interval, False)

    @api.model
    def _cron_send_scheduled_reports(self):
        now = fields.Datetime.now()
        for schedule in self.search([("active", "=", True)]):
            try:
                if not schedule._due(now):
                    continue
                schedule._send()
                schedule.last_run = now
            except Exception:
                _logger.exception(
                    "Scheduled overview report %s failed", schedule.name)

    def _send(self):
        self.ensure_one()
        Exporter = self.env["odex.overview.exporter"]
        filters = {"report_type": self.report_type, "period": self.period}
        data = self.env["odex.overview.report"].get_report(filters)
        if self.export_format == "xlsx":
            content, mimetype, ext = (
                Exporter.to_xlsx(data),
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet", "xlsx")
        elif self.export_format == "csv":
            content, mimetype, ext = (
                Exporter.to_csv(data), "text/csv", "csv")
        else:
            content, mimetype, ext = (
                Exporter.to_pdf(data), "application/pdf", "pdf")
        filename = "%s_%s.%s" % (
            self.report_type, fields.Date.today(), ext)
        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "datas": base64.b64encode(content),
            "mimetype": mimetype,
        })
        template = self.env.ref(
            "odex_technician_overview.mail_template_scheduled_report",
            raise_if_not_found=False)
        if template:
            template.send_mail(
                self.id, force_send=True,
                email_values={"attachment_ids": [(4, attachment.id)]})
