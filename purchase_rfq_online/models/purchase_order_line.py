from functools import partial

from odoo import fields, models
from odoo.tools import formatLang


class PurchaseLine(models.Model):
    _inherit = "purchase.order.line"

    vendor_part_no = fields.Char(
        string="VPart No.",
        copy=True,
        index="btree_not_null",
        help="Part number used by the vendor for this product. "
        "It can be filled in by the vendor from the RFQ portal and is "
        "specific to this order line: it never changes the internal "
        "reference of the product itself.",
    )

    def formatted_price(self):
        """
        Return unit price in decimal accuracy formatted
        """
        self.ensure_one()
        format_price = partial(
            formatLang, self.env, digits=self.order_id.currency_id.decimal_places
        )
        price = self.price_unit
        return format_price(price)
