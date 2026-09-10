# -*- coding: utf-8 -*-
import csv
import io
import json

from odoo import http, models, api
from odoo.http import request, content_disposition


class OdexOverviewExporter(models.AbstractModel):
    _name = "odex.overview.exporter"
    _description = "Odex Overview Export Service"

    @api.model
    def to_xlsx(self, data):
        import xlsxwriter  # bundled with Odoo
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet(data.get("title", "Report")[:31])
        title_fmt = workbook.add_format(
            {"bold": True, "font_size": 14, "font_color": "#4C3B92"})
        head_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#5B4BB7", "font_color": "#FFFFFF",
             "border": 1})
        cell_fmt = workbook.add_format({"border": 1})
        sheet.write(0, 0, data.get("title", "Report"), title_fmt)
        sheet.write(1, 0, "Generated: %s" % data.get("generated_at", ""))
        columns = data.get("columns", [])
        for col, (_key, label) in enumerate(columns):
            sheet.write(3, col, label, head_fmt)
            sheet.set_column(col, col, max(len(label) + 2, 14))
        for row_idx, row in enumerate(data.get("rows", []), start=4):
            for col, (key, _label) in enumerate(columns):
                sheet.write(row_idx, col, row.get(key, ""), cell_fmt)
        workbook.close()
        return output.getvalue()

    @api.model
    def to_csv(self, data):
        output = io.StringIO()
        writer = csv.writer(output)
        columns = data.get("columns", [])
        writer.writerow([label for _key, label in columns])
        for row in data.get("rows", []):
            writer.writerow([row.get(key, "") for key, _label in columns])
        return output.getvalue().encode("utf-8-sig")

    @api.model
    def to_pdf(self, data):
        html = self.env["ir.qweb"]._render(
            "odex_technician_overview.report_pdf_document",
            {"data": data})
        pdf_content, _type = self.env["ir.actions.report"]._run_wkhtmltopdf(
            [html], landscape=True,
            specific_paperformat_args={
                "data-report-margin-top": 10,
                "data-report-header-spacing": 5,
            })
        return pdf_content


class OdexOverviewController(http.Controller):

    @http.route("/odex_overview/dashboard", type="json", auth="user")
    def dashboard(self, filters=None):
        return request.env["odex.technician.overview"].get_dashboard_data(
            filters or {})

    @http.route("/odex_overview/filter_options", type="json", auth="user")
    def filter_options(self):
        return request.env["odex.technician.overview"].get_filter_options()

    @http.route("/odex_overview/report", type="json", auth="user")
    def report(self, filters=None):
        return request.env["odex.overview.report"].get_report(filters or {})

    @http.route("/odex_overview/export/<string:fmt>", type="http",
                auth="user")
    def export(self, fmt, filters="{}", **kw):
        try:
            parsed = json.loads(filters)
        except (ValueError, TypeError):
            parsed = {}
        data = request.env["odex.overview.report"].get_report(parsed)
        exporter = request.env["odex.overview.exporter"]
        report_type = parsed.get("report_type", "report")
        if fmt == "xlsx":
            content = exporter.to_xlsx(data)
            mimetype = ("application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet")
            filename = "%s.xlsx" % report_type
        elif fmt == "csv":
            content = exporter.to_csv(data)
            mimetype = "text/csv"
            filename = "%s.csv" % report_type
        elif fmt == "pdf":
            content = exporter.to_pdf(data)
            mimetype = "application/pdf"
            filename = "%s.pdf" % report_type
        else:
            return request.not_found()
        return request.make_response(content, headers=[
            ("Content-Type", mimetype),
            ("Content-Disposition", content_disposition(filename)),
            ("Content-Length", len(content)),
        ])
