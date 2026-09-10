/** @odoo-module **/

import { download } from "@web/core/network/download";
import { registry } from "@web/core/registry";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { patch } from "@web/core/utils/patch";
import { DROPDOWN } from "@web/core/dropdown/dropdown";

const actionRegistry = registry.category("actions");

async function ks_executexlsxReportDownloadAction(parent, action) {


    await download({
        url: "/ks_dynamic_financial_report",
        data: action.data,
    });
};
actionRegistry.add("ks_executexlsxReportDownloadAction", ks_executexlsxReportDownloadAction);

