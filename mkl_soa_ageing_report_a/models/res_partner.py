from odoo import models, api
from datetime import datetime

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_soa_a_report_base_filename(self):
        """Generates a filename in the format 'Lastname_Fullname_soa_YYYY-MM-DD'."""
        self.ensure_one()
        today_date = datetime.today().strftime('%Y-%m-%d')
        full_name = self.name or ''
        filename = f"{full_name}_SOA_{today_date}"
        return filename
