# ODEX Vendor Portal (`odex_vendor_portal`)

Odoo 18 Community. Adds a **Vendor** portal user type and a Vendor Portal
section next to the existing Customer Portal. Nothing in the Customer Portal,
the website header/footer, the purchase workflow or the accounting workflow is
modified.

---

## 1. What is touched

| Layer | What | How |
|---|---|---|
| Models | `res.users` | new `portal_user_type` selection (`customer` / `vendor`), group sync |
| | `res.partner` | two display helpers (initials, address lines) |
| | `purchase.order` (+ `.line`) | vendor response fields + portal status helpers |
| | `account.move` | payment status helper |
| | `ir.http` | dispatch guard: vendor users hitting `/my` land on `/my/vendor` |
| Controllers | `web.Home._login_redirect` | vendor login lands on `/my/vendor` |
| | `portal.CustomerPortal` subclass | all `/my/vendor/*` routes |
| Templates | new `odex_vendor_portal.*` | dashboard, RFQ, PO, payments, activity |
| | `portal.portal_breadcrumbs` (inherit) | adds the Vendor Portal crumbs |
| Security | `group_vendor_portal` | implies `base.group_portal` |
| | 4 record rules + 6 ACL lines | read-only, scoped on the commercial partner |
| Assets | `web.assets_frontend` | one SCSS file, all classes prefixed `o_vendor_` |

No new model is created: RFQs and POs are `purchase.order`, payments are
`account.move`. The header and footer come from `portal.portal_layout` →
`portal.frontend_layout` → `website.layout`, i.e. exactly the templates the
Customer Portal already uses.

## 2. Customer vs Vendor detection

The `portal_user_type` radio on the user form is the UI. The **group** is the
source of truth at runtime:

* `portal_user_type = vendor` → `res.users.write()` adds `base.group_portal`
  and `odex_vendor_portal.group_vendor_portal`, and bumps `supplier_rank` on
  the commercial partner.
* `portal_user_type = customer` → the vendor group is removed; nothing else
  changes, so existing customer portal users keep their exact behaviour.
* Internal (`share = False`) and public users are never touched by the sync.

`res.users._is_vendor_portal_user()` returns True only for a non-internal,
non-public user carrying the group. Redirection happens twice, on purpose:

1. `Home._login_redirect()` — right after login, when no explicit `redirect`
   was requested.
2. `ir.http._dispatch()` — any later hit on `/my` or `/my/home`. Done at
   dispatch level so it does not depend on the controller MRO; another module
   overriding `/my/home` (e.g. the workshop customer portal) keeps working
   untouched for customer users.

## 3. Routes

| Route | Page |
|---|---|
| `/my/vendor` | dashboard (details, quick links, 3 tiles, recent activity) |
| `/my/vendor/rfqs` | RFQ list (paged, sortable) |
| `/my/vendor/rfq/<id>` | RFQ detail + quotation form; `?report_type=pdf&download=true` for the PDF |
| `/my/vendor/rfq/<id>/respond` | POST — writes unit prices, expected date, note |
| `/my/vendor/orders` | purchase order list |
| `/my/vendor/order/<id>` | PO detail; `?report_type=pdf&download=true` |
| `/my/vendor/payments` | bills with paid / pending / overdue filters |
| `/my/vendor/payment/<id>` | bill summary (amounts and status only) |
| `/my/vendor/activity` | full recent activity |
| `/my/account` | reused as-is for **Edit Profile** |

RFQ = `purchase.order` in state `sent`. Purchase Orders = state
`purchase` / `done` / `cancel`. Draft RFQs (not yet sent to the vendor) are
invisible at the record-rule level.

## 4. Security model

Three independent layers, all server-side:

1. **Route guard** — every route resolves the partner through
   `_vendor_partner()`; a user without the vendor group is redirected to
   `/my/home` and never reaches the query.
2. **Record rules** — read-only rules on `purchase.order`,
   `purchase.order.line`, `account.move` and `account.move.line`, all scoped
   with `('partner_id', 'child_of', [user.partner_id.commercial_partner_id.id])`.
   Lists are built with the user's own rights, so the rules do the filtering.
3. **Ownership gate** — `_vendor_owned_or_404()` runs
   `_document_check_access()` (which raises on a foreign record) and then
   asserts the commercial partner match **before** any `sudo()` read. Any
   mismatch raises 404, not 403, so URL probing does not confirm existence.

The response POST additionally re-checks ownership, re-checks `state == 'sent'`,
only accepts `price_<line_id>` keys that belong to that order, and validates
each price is a positive float. No `write` right is ever granted to the vendor
group — the price update runs in `sudo()` inside that validated path only.

Bill pages expose amount, residual, dates and payment state only. No narration,
no internal notes, no journal items, no PDF.

## 5. Install

```bash
cd /opt/odoo18/wms25ii
# copy the module into the addons path, then:
./odoo-bin -c <conf> -d <db> -u odex_vendor_portal --stop-after-init
sudo systemctl restart odoo18-wms25ii   # python changes need a full restart
```

Then: Settings → Users → open a portal user → **Portal User Type = Vendor** →
save. The user is linked to the vendor contact through `partner_id` as usual.

Run `bash tools/check_all.sh` before every deploy.

## 6. Test checklist

| # | Test | Expected |
|---|---|---|
| 1 | Vendor A logs in | lands on `/my/vendor` |
| 2 | Vendor A RFQ/PO/payment lists | only Vendor A records |
| 3 | Vendor A opens `/my/vendor/order/<Vendor B id>` | 404 |
| 4 | Vendor A opens `/my/vendor/payment/<Vendor B id>` | 404 |
| 5 | Vendor A POSTs a response to Vendor B's RFQ | 404, nothing written |
| 6 | Vendor A POSTs to a confirmed PO | 404 |
| 7 | Customer portal user logs in | existing Customer Portal, unchanged |
| 8 | Customer user opens `/my/vendor` | redirected to `/my/home` |
| 9 | Internal user | backend unchanged, `/my/vendor` redirects |
| 10 | Vendor submits a quotation | prices updated, chatter message on the PO, `vendor_response_date` set |
| 11 | PDF download on RFQ and PO | correct report, attachment |
| 12 | Mobile ≤767px | tables stack into labelled cards, tiles stack, header/footer unchanged |
| 13 | Logout | standard portal logout |
