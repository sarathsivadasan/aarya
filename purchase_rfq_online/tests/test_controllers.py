# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
from uuid import uuid4

from werkzeug import urls

from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from odoo.addons.base.tests.common import BaseUsersCommon


@tagged("post_install", "-at_install")
class TestAccessRightsControllers(BaseUsersCommon, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        portal_user_partner = cls.env["res.partner"].create(
            {
                "name": "partner_a",
                "company_id": False,
            }
        )
        # create a SO to be signed
        cls.purchase_order = cls.env["purchase.order"].create(
            {
                "name": "test PO",
                "partner_id": portal_user_partner.id,
                "state": "sent",
            }
        )
        cls.env["purchase.order.line"].create(
            {
                "order_id": cls.purchase_order.id,
                "product_id": cls.env["product.product"]
                .create({"name": "A product"})
                .id,
            }
        )

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_access_controller(self):
        private_po = self.purchase_order
        portal_po = self.purchase_order.copy()
        portal_po.message_subscribe(self.user_portal.partner_id.ids)

        portal_po._portal_ensure_token()
        token = portal_po.access_token

        self.authenticate(None, None)

        # Test public user can't print an order without a token
        req = self.url_open(
            url=f"/my/purchase/{portal_po.id}?report_type=pdf",
            allow_redirects=False,
        )
        self.assertEqual(req.status_code, 303)

        # or with a random token
        req = self.url_open(
            url=f"/my/purchase/{portal_po.id}?access_token={'foo'}&report_type=pdf",
            allow_redirects=False,
        )
        self.assertEqual(req.status_code, 303)

        # but works fine with the right token
        req = self.url_open(
            url=f"/my/purchase/{portal_po.id}?access_token={token}&report_type=pdf",
            allow_redirects=False,
        )
        self.assertEqual(req.status_code, 200)

        self.authenticate(self.user_portal.login, self.user_portal.login)

        # do not need the token when logged in
        req = self.url_open(
            url=f"/my/purchase/{portal_po.id}?report_type=pdf",
            allow_redirects=False,
        )
        self.assertEqual(req.status_code, 200)

        # but still can't access another order
        req = self.url_open(
            url=f"/my/purchase/{private_po.id}?report_type=pdf",
            allow_redirects=False,
        )
        self.assertEqual(req.status_code, 303)

    def _make_json_rpc_request(self, url, data=None):
        """Make a JSON-RPC request to the provided URL.

        :param str url: The URL to make the request to
        :param dict data: The data to be send in the request body in JSON-RPC 2.0 format
        :return dict: The result of the JSON-RPC request
        """
        rpc_request = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": str(uuid4()),
            "params": data,
        }
        result = self.url_open(
            url,
            data=json.dumps(rpc_request).encode(),
            headers={"Content-Type": "application/json"},
        )

        if not result.ok:
            return {}

        return result.json().get("result", {})

    def test_update_price(self):
        portal_po = self.purchase_order.copy()
        portal_po.message_subscribe(self.user_portal.partner_id.ids)

        portal_po._portal_ensure_token()
        token = portal_po.access_token

        self.authenticate(None, None)
        params = {
            "line_id": portal_po.order_line[0].id,
            "remove": False,
            "unlink": False,
            "input_price": 100,
            "access_token": token,
        }
        url = "/my/purchase/" + str(portal_po.id) + "/update_line_dict"
        url = urls.url_join(self.base_url(), url)
        self._make_json_rpc_request(url, params)
        self.assertEqual(portal_po.order_line[0].price_unit, 100)
