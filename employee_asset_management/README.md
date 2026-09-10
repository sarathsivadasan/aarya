# Employee Asset Management (Odoo 18 Community)

Adds an **Assets** tab on the Employee form so HR can record every company asset
handed over to an employee, with full assignment history.

## Features

* **Assets tab** on `hr.employee` (added after the *Settings* tab) with an
  *Assigned Assets* list and an **Add Asset** button.
* **Assets smart button** in the employee button box showing the number of
  currently assigned assets.
* Asset picked from the existing **product catalogue** (`product.product`) —
  no duplicate asset master data.
* **Serial Number / Barcode** char field (scanner friendly: a keyboard-wedge
  scanner fills it directly), unique across *active* assignments per company.
* **Assign Date** (defaults to today), **Asset Return Date**,
  **Note for Health Condition**, **Notes**, **Status** (Assigned / Returned).
* **Return Asset** button on the list row and in the form header — sets the
  return date and status, and keeps the record as history.
* Standalone menu **Employees ▸ Assets ▸ Employee Assets** with search,
  filters and group by (employee, department, asset, status, assign date).
* Chatter / tracking on employee, asset, serial, dates and status.

## Business rules enforced

| Rule | Where |
|---|---|
| Asset (product) is mandatory | `asset_id` required |
| Return date cannot be before assign date | `_check_dates` |
| Returned assignment must have a return date | `_check_state_dates` |
| Assigned assignment must not have a return date | `_check_state_dates` |
| The same barcode cannot be assigned to two employees at once | `_check_unique_active_serial` → *"This asset is already assigned to another employee."* |
| History is never overwritten or auto-deleted | new record per assignment; only HR Administrator may delete |

Entering a return date automatically switches the status to *Returned*;
clearing it switches back to *Assigned* (handled in onchange, `create` and
`write`, so it also holds for imports and API calls).

## Security

| Group | Read | Write | Create | Delete |
|---|---|---|---|---|
| Internal user (`base.group_user`) | own assignments only | – | – | – |
| HR Officer (`hr.group_hr_user`) | all | yes | yes | – |
| HR Administrator (`hr.group_hr_manager`) | all | yes | yes | yes |

A global multi-company record rule restricts records to the allowed companies.
The Assets tab and menus are visible to `hr.group_hr_user` and above only.

## Installation

```bash
# 1. copy the module into your addons path
cp -r employee_asset_management /opt/odoo18/wms25ii/custom_addons/

# 2. restart the Odoo service (Python models need a full restart)
sudo systemctl restart odoo18-wms25ii

# 3. Apps ▸ Update Apps List ▸ search "Employee Asset Management" ▸ Install
```

Or from the command line:

```bash
./odoo-bin -c /etc/odoo18-wms25ii.conf -d <database> -u employee_asset_management --stop-after-init
```

## Usage

1. **Employees ▸ Employees ▸** open an employee **▸ Assets** tab.
2. Click **Add Asset**, pick the product, scan the barcode into
   *Serial Number / Barcode*, check the assign date, write the condition note,
   save.
3. When the asset comes back, click the ↩ button on the row (or **Return Asset**
   in the form) — the return date is filled with today and the status becomes
   *Returned*. The row stays in the tab as history.
4. **Employees ▸ Assets ▸ Employee Assets** gives HR the cross-employee view
   with filters and group by.

### Optional: camera barcode scanning

Hardware (keyboard-wedge) scanners work out of the box. If you also want the
mobile camera scan icon, install Odoo's `barcodes` module and add
`widget="barcode_scanner"` to the `serial_number` field in
`views/employee_asset_views.xml` and `views/hr_employee_views.xml`.

## Odoo 18 compatibility notes

* `<list>` instead of `<tree>`, `invisible="..."` instead of `attrs`,
  `<chatter/>` instead of the old chatter div.
* `_compute_display_name` instead of `name_get`.
* `_read_group` with the 18.0 signature (`aggregates=['__count']`).
* `@api.model_create_multi` on `create`.
* No deprecated APIs, no custom JavaScript.
