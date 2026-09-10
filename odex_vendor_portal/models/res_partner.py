# -*- coding: utf-8 -*-
from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def vendor_portal_initials(self):
        """Two letter avatar used by the Vendor Details card."""
        self.ensure_one()
        name = (self.name or '').strip()
        if not name:
            return '?'
        parts = [p for p in name.split() if p]
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return name[:2].upper()

    def vendor_portal_address_lines(self):
        """Printable address lines, skipping the empty ones."""
        self.ensure_one()
        street = ' '.join([p for p in [self.street, self.street2] if p])
        city_line = ' '.join([p for p in [
            self.city,
            self.state_id.name if self.state_id else '',
            self.zip,
        ] if p])
        lines = [street, city_line, self.country_id.name if self.country_id else '']
        return [line for line in lines if line]
