# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged

from odoo.addons.purchase_rfq_online.controllers.portal import (
    VENDOR_PART_NO_MAX_LENGTH,
)


@tagged("post_install", "-at_install")
class TestVendorPartNo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create(
            {"name": "A product", "default_code": "INTERNAL-REF"}
        )
        cls.vendor_a = cls.env["res.partner"].create({"name": "Vendor A"})
        cls.vendor_b = cls.env["res.partner"].create({"name": "Vendor B"})
        cls.order_a = cls.env["purchase.order"].create(
            {"partner_id": cls.vendor_a.id, "state": "sent"}
        )
        cls.line_a = cls.env["purchase.order.line"].create(
            {"order_id": cls.order_a.id, "product_id": cls.product.id}
        )
        cls.order_b = cls.env["purchase.order"].create(
            {"partner_id": cls.vendor_b.id, "state": "sent"}
        )
        cls.line_b = cls.env["purchase.order.line"].create(
            {"order_id": cls.order_b.id, "product_id": cls.product.id}
        )

    def test_vendor_part_no_is_line_specific(self):
        """Each vendor keeps his own part number for the same product."""
        self.line_a.vendor_part_no = "BRK-OIL-001"
        self.line_b.vendor_part_no = "OIL/BRK#002"
        self.assertEqual(self.line_a.vendor_part_no, "BRK-OIL-001")
        self.assertEqual(self.line_b.vendor_part_no, "OIL/BRK#002")

    def test_product_reference_is_untouched(self):
        """Writing the vendor part number never touches the product master."""
        self.line_a.vendor_part_no = "BRK-OIL-001"
        self.assertEqual(self.product.default_code, "INTERNAL-REF")
        self.assertEqual(
            self.product.product_tmpl_id.default_code,
            "INTERNAL-REF",
        )

    def test_vendor_part_no_is_copied(self):
        """The vendor part number follows the line when the RFQ is duplicated."""
        self.line_a.vendor_part_no = "BRK-OIL-001"
        copied = self.order_a.copy()
        self.assertEqual(copied.order_line.vendor_part_no, "BRK-OIL-001")

    def test_vendor_part_no_accepts_long_and_special_values(self):
        """Long values and special characters are accepted by the field."""
        value = "ÄÖ/#-_." * 10
        self.line_a.vendor_part_no = value[:VENDOR_PART_NO_MAX_LENGTH]
        self.assertEqual(
            self.line_a.vendor_part_no, value[:VENDOR_PART_NO_MAX_LENGTH]
        )
