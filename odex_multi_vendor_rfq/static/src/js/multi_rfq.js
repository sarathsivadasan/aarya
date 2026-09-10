/** @odoo-module **/
/**
 * odex_multi_vendor_rfq — backend JS
 * Adds live subtotal calculation in the comparison list.
 */
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

// No heavy OWL component needed for v1 — CSS classes drive the colour
// coding; Python computes comparison data for the PDF report.
// This file is a placeholder for future JS widgets (e.g. an inline
// comparison widget rendered via OWL).

console.debug("[odex_multi_vendor_rfq] JS loaded");
