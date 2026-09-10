# Per User Product Price Visibility (`odex_product_price_visibility`)

Odoo 18 Community Edition · ODEX

Adds a **Hide Cost & Sales Price** checkbox on the user form. For a user with
that box ticked, the cost and the sales price of products disappear from the
product views — including the Inventory product list and kanban — and the values
are blanked in the data the server sends back.

---

## 1. Installation

```bash
cp -r odex_product_price_visibility /opt/odoo18/wms25ii/custom-addons/
sudo systemctl restart odoo18-wms25ii
```

Then *Apps → Update Apps List → install "Per User Product Price Visibility"*.
Depends on `product` only. Independent from `odex_group_menu_visibility`; the
two can be installed together or separately.

## 2. Configuration

*Settings → Users & Companies → Users → open a user → **Product Visibility** tab
→ tick **Hide Cost & Sales Price** → Save.*

The user must refresh the browser (or log in again) for the change to take
effect, because the flag travels in the user context, which is fetched at page
load. The setting can only be changed by someone who can already administer
users; the user cannot switch it off for themselves.

## 3. What gets hidden

Fields masked (constant `PRICE_FIELDS` at the top of `models/product.py`, edit it
to fit your setup):

| Field | Label |
| --- | --- |
| `standard_price` | Cost |
| `list_price` | Sales Price (template) |
| `lst_price` | Sales Price (variant) |
| `price_extra` | Variant extra price |
| `price` | Pricelist computed price |
| `avg_cost`, `total_value`, `value_svl` | Inventory valuation (`stock_account`) |

On `product.template` and `product.product`, in every list, kanban, form and
search view — standard views and custom ones alike.

## 4. Technical approach

Two layers, both server side, no JavaScript, no core modification.

### 4.1 The flag

`res.users.context_odex_hide_price` is a plain Boolean. The `context_` prefix is
the supported Odoo mechanism: `res.users.context_get()` publishes every
`context_*` field into the user context, so the flag is available as
`context.get('odex_hide_price')` in the web client and in view modifiers. The
same prefix makes the field self-readable (core `res.users.read()` allows any
`context_*` key) while writing it still requires user-administration rights.
`context_get()` is ormcached per user, so `create`/`write` clear the registry
cache when the flag is involved.

### 4.2 View layer

`odex.price.mask.mixin._get_view()` walks the returned arch and injects
`invisible="context.get('odex_hide_price')"` — `column_invisible` in list views —
on every `<field>` bound to a price field, plus the matching `<label for="...">`.
In kanban views it also hides the labelled container (`<div name="product_lst_price">Price: …</div>`)
when that container holds only the price field, so the caption does not stay
behind.

The injected expression is **the same for every user**, so the arch stays
user-independent and Odoo's view caching remains valid; the client evaluates the
expression against each user's own context. This is also why it works on custom
views and on views added by other modules without listing a single XML id.

### 4.3 Data layer

Hiding a field in the arch is not enough — the value would still be in the RPC
payload. `_read_format()` (the common code path of `read`, `web_read` and
`web_search_read`) blanks the masked fields to `0.0`, and `export_data()` blanks
the corresponding columns.

`self.env.su` short-circuits the whole thing, so anything running as superuser —
valuation, invoicing, reports, crons, other modules' computations — keeps
working on real values. Direct ORM field access (`product.standard_price` in
Python) is likewise untouched, which is what keeps the feature from breaking
business logic.

## 5. Scope and limits

This is a **visibility feature, not an access right.** Users keep read access to
the product models, so:

* aggregated views (pivot/graph measures, `read_group` over a price field) can
  still expose totals;
* a determined user with RPC access can still infer a price by searching on it
  (`[('standard_price', '>', 100)]`);
* prices reachable through *other* models (a purchase order line, a valuation
  layer, a sale order) are not masked — only `product.template` and
  `product.product` are.

If the cost figure must be genuinely protected rather than merely out of sight,
remove the user's access to the models that carry it. This module is for
decluttering and discretion, not for confidentiality.

## 6. Tests

```bash
odoo-bin -c <config> -d <database> -i odex_product_price_visibility \
         --test-enable --test-tags /odex_product_price_visibility --stop-after-init
```

Covers: flag reaching the user context, masking on `read` for template and
variant, other users unaffected, superuser bypass, export masking, the modifier
being injected into list/form/kanban views, list views using `column_invisible`,
the arch staying user-independent, and access rights being unchanged.

## 7. Structure

```
odex_product_price_visibility/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── product.py           # masking mixin + product.template / product.product
│   └── res_users.py         # context_odex_hide_price flag
├── tests/
│   ├── __init__.py
│   └── test_price_visibility.py
└── views/
    └── res_users_views.xml  # Product Visibility tab on the user form
```
