/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useNarrowScreen } from "./narrow_screen";
import { platformClasses } from "./platform";

import { DashboardPage } from "./components/dashboard_page";
import { JobWorkspace } from "./components/job_workspace";
import { PerformancePage } from "./components/performance_page";
import { ProfilePage } from "./components/profile_page";
import { AdminJobsPage } from "./components/admin_jobs_page";

/**
 * Odex Garage Technician Portal - root client action.
 *
 * Reproduces the reference layout: left sidebar with the menu
 * entries, a top bar, and a routed main content area. State (current
 * page, selected task) lives here and is passed down as props so every
 * sub-page/tab talks to the same source of truth.
 *
 * On small screens (ui.isSmall - Odoo's own breakpoint service, same one
 * the core backend uses) the sidebar becomes a slide-in drawer opened via
 * the hamburger icon in the top bar, instead of a permanent 220px column.
 */
export class TechnicianPortalAction extends Component {
    static template = "odex_garage_technician_portal.TechnicianPortalAction";
    static components = { DashboardPage, JobWorkspace, PerformancePage, ProfilePage, AdminJobsPage };
    static props = ["*"];

    setup() {
        this.ui = useService("ui");
        // reactive; covers tablet portrait, which ui.isSmall misses
        this.narrow = useNarrowScreen();
        this.state = useState({
            // dashboard | job_card | parts | performance | profile |
            // admin_jobs
            page: "dashboard",
            selectedLineId: null,
            statusFilter: null,
            userName: user.name,
            sidebarOpen: false,
            isAdmin: false,
        });

        // Mac/Safari class hooks - computed once, they cannot change for
        // the life of the session.
        this.platformClass = platformClasses();

        onWillStart(async () => {
            const info = await rpc("/technician_portal/access_info", {});
            this.state.isAdmin = Boolean(info && info.is_admin);
        });
    }

    get isSmall() {
        return this.narrow.isNarrow;
    }

    /** Root classes: narrow-screen layout plus the macOS/Safari hooks the
     *  Mac stylesheet is scoped under. Empty on every other platform. */
    get rootClass() {
        const classes = [];
        if (this.isSmall) {
            classes.push("o_tp_is_mobile");
        }
        if (this.platformClass) {
            classes.push(this.platformClass);
        }
        return classes.join(" ");
    }

    setPage(page, lineId = null) {
        this.state.page = page;
        this.state.selectedLineId = lineId;
        this.state.statusFilter = null;
        this.state.sidebarOpen = false; // auto-close the drawer after navigating on mobile
    }

    /** lineId is an account.analytic.line id on a Job Card. */
    openJob(lineId) {
        this.state.page = "job_card";
        this.state.selectedLineId = lineId;
    }

    /** Called from the Dashboard's "View All" links. status may be null
     *  (show everything); page lets "View Timesheet" jump to Performance. */
    viewAll(status, page = "job_card") {
        this.state.page = page;
        this.state.statusFilter = status;
        this.state.selectedLineId = null;
    }

    toggleSidebar() {
        this.state.sidebarOpen = !this.state.sidebarOpen;
    }
}

registry.category("actions").add("odex_technician_portal", TechnicianPortalAction);
