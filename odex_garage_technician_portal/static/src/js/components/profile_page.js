/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart } from "@odoo/owl";

export class ProfilePage extends Component {
    static template = "odex_garage_technician_portal.ProfilePage";
    static props = {};

    setup() {
        this.state = useState({ profile: null });
        onWillStart(async () => {
            this.state.profile = await rpc("/technician_portal/profile", {});
        });
    }
}
