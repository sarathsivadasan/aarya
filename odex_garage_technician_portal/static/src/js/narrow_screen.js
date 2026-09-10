/** @odoo-module **/

import { useState, onWillDestroy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Why this exists instead of just using ui.isSmall:
 *
 * 1. THRESHOLD. Odoo's ui.isSmall flips below ~768px (Bootstrap's md
 *    breakpoint). Every current tablet is WIDER than that in portrait -
 *    iPad Mini 744, iPad 10.2" 810, iPad Air 820, iPad Pro 11" 834,
 *    iPad Pro 12.9" 1024 - so isSmall stays false and the portal kept
 *    its desktop two-pane layout (220px sidebar + 340px list + detail),
 *    squeezing the detail pane to a couple hundred pixels. That is the
 *    squashed portrait layout being reported.
 *
 * 2. REACTIVITY. `this.ui.isSmall` is read once at render time. Rotating
 *    the device doesn't re-render the component on its own, so even a
 *    correct threshold wouldn't fix the layout until something else
 *    triggered a re-render. The useState() object below is reactive, so
 *    assigning to it on resize/rotation re-renders immediately.
 *
 * Landscape tablets (1080-1194px wide) stay above the threshold and keep
 * the two-pane layout, which is what the user reported already works.
 */
export const NARROW_MAX_WIDTH = 1024;

function currentWidth() {
    return window.innerWidth || document.documentElement.clientWidth || 0;
}

function computeIsNarrow(ui) {
    // ui.isSmall still counts - it catches phones and any host that
    // reports a small size for reasons other than raw pixel width.
    return Boolean(ui && ui.isSmall) || currentWidth() <= NARROW_MAX_WIDTH;
}

export function useNarrowScreen() {
    const ui = useService("ui");
    const state = useState({ isNarrow: computeIsNarrow(ui) });

    const update = () => {
        const next = computeIsNarrow(ui);
        if (next !== state.isNarrow) {
            state.isNarrow = next;
        }
    };

    // iOS reports stale dimensions if read synchronously inside
    // orientationchange, so re-check on the next frame and once more
    // shortly after the rotation animation settles.
    const onOrientationChange = () => {
        requestAnimationFrame(update);
        setTimeout(update, 300);
    };

    window.addEventListener("resize", update);
    window.addEventListener("orientationchange", onOrientationChange);
    onWillDestroy(() => {
        window.removeEventListener("resize", update);
        window.removeEventListener("orientationchange", onOrientationChange);
    });

    return state;
}
