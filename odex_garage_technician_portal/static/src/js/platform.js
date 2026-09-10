/** @odoo-module **/

/**
 * Platform detection for the Technician Portal (requirement 1).
 *
 * WHY THIS EXISTS
 * ---------------
 * The portal renders correctly on Windows/Chrome but breaks on Mac. The
 * causes are all Safari/WebKit and macOS behaviours, not screen size:
 *
 *   1. FLEXBOX `gap`. Safari only supports gap in flex containers from
 *      14.1 (macOS Big Sur, April 2021). Every Mac still on Catalina or
 *      an earlier Big Sur point release renders the whole portal with
 *      zero spacing - cards, buttons, tabs and form controls all glued
 *      together. That is the single biggest visual break.
 *   2. FLEX CHILDREN THAT SCROLL. WebKit needs an explicit
 *      `min-height: 0` / `min-width: 0` on a flex child before
 *      `overflow: auto` will scroll it; without that the child grows and
 *      pushes the layout past the viewport instead of scrolling inside
 *      it. That is why the list and content panes overflow on Mac.
 *   3. `flex: 1` SHORTHAND. Safari resolves the unitless flex-basis in
 *      `flex: 1` inconsistently next to a fixed-width sibling, which
 *      collapses the detail pane beside the 340px list pane.
 *   4. OVERLAY SCROLLBARS. macOS hides scrollbars until you scroll, so
 *      scrollable panes look like truncated content.
 *   5. NATIVE FORM CONTROLS. Safari on macOS ignores height/padding on
 *      <select> and renders <button>/<input> with its own chrome, so
 *      controls in the same row end up different heights.
 *
 * The fixes live in static/src/css/technician_portal_mac.css and are ALL
 * scoped under the `.o_tp_mac` / `.o_tp_safari` classes this module adds
 * to the portal root. Nothing in that file can match on Windows, Linux or
 * Android, so those layouts are provably untouched.
 */

/** True on macOS, including iPadOS which reports itself as a Mac. */
export function isMacPlatform() {
    const nav = typeof navigator !== "undefined" ? navigator : null;
    if (!nav) {
        return false;
    }
    const uaPlatform = nav.userAgentData && nav.userAgentData.platform;
    if (uaPlatform) {
        return /mac/i.test(uaPlatform);
    }
    const platform = nav.platform || "";
    if (/mac/i.test(platform)) {
        return true;
    }
    // iPadOS 13+ reports "MacIntel" above, but some webviews only expose
    // it through the user agent string.
    return /Macintosh|Mac OS X/i.test(nav.userAgent || "");
}

/** True on Safari (desktop or iOS) - excludes Chrome/Edge/Opera on Mac,
 *  which report "Safari" in the UA string as well. */
export function isSafariBrowser() {
    const ua = (typeof navigator !== "undefined" && navigator.userAgent) || "";
    return /Safari/i.test(ua) && !/Chrome|Chromium|CriOS|Edg|OPR|FxiOS|Firefox/i.test(ua);
}

/**
 * Space-separated classes to add to the portal root. Empty string on
 * every non-Apple platform, so the Mac stylesheet is inert there.
 */
export function platformClasses() {
    const classes = [];
    if (isMacPlatform()) {
        classes.push("o_tp_mac");
    }
    if (isSafariBrowser()) {
        classes.push("o_tp_safari");
    }
    return classes.join(" ");
}
