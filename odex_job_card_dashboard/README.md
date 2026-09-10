# ODEX Job Card Dashboard (v18.0.1.2.0)

A brand-new OWL dashboard for the Workshop Management System. It does not touch
the existing `job_card_dashboard` module — install both side by side and retire
the old one when you are happy.

## Install

```bash
cp -r odex_job_card_dashboard /opt/odoo18/wms25ii/addons/
sudo systemctl restart odoo18-wms25ii          # Python model changes need a restart
./odoo-bin -c <conf> -d <db> -i odex_job_card_dashboard --stop-after-init
```

Then clear the asset cache and hard-refresh the browser:

```sql
DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';
```

The footer prints `Job Card Dashboard build 1.2.0`. If you don't see it, the
browser is still serving an old bundle.

Menu: **Workshop Dashboard → Dashboard**.

## Dependencies

`web`, `project`, `job_card`, `job_card_extension`.

`vehicle_inspection_report` is a *soft* dependency — the inspection breakdown
appears automatically if `project.task` has an `inspection_state` field. Add it
to `depends` in `__manifest__.py` if you want a hard link.

## How it reads your data

Nothing is duplicated. Job cards are `project.task` records flagged with
`is_jobcard`; statuses are `job.card.stage` records read through `cc_stage_id`;
bays are `job.card.bay` read through `bay_id`.

Every field name is resolved at runtime from a candidate list
(`FIELD_CANDIDATES` in `models/job_card_dashboard.py`). If your database names a
field differently, add it to the list — no other change is needed. Widgets whose
fields are missing are skipped and reported in a banner instead of breaking the
page.

Counters use `read_group` only, so 10 000+ job cards cost the same as 100.
Drill-down rows are loaded on demand when a card is expanded.

## Configuration

**Workshop Dashboard → Configuration**

* **Dashboard Settings** — refresh interval, default period, which date field
  the filter applies to, rows per table, overdue thresholds (warning /
  critical / severe), efficiency target, and a toggle per widget.
* **Status Cards** — colour, icon, visibility and drag-and-drop order for every
  job status, plus whether the status appears in the vehicle pipeline. Colours
  are never hardcoded in the front end; the "Suggest style" button fills in a
  sensible default.

## Live updates

The dashboard polls on the configured interval and also listens on the
`job_card_dashboard` bus channel. Writing a status, technician, promise date,
inspection state, bay or priority on a job card pushes a refresh to every open
dashboard — no page reload.

## Security

No `sudo()` anywhere in the aggregation path, so your existing record rules
decide what each user counts and sees. Two groups ship with the module:
*Dashboard User* (read) and *Dashboard Manager* (configuration).


## 1.1.0

* Removed **Job Status Overview** and **Job Status Summary** entirely — component,
  template, styles, config fields and the Chart.js bundle load are all gone.
* **Vehicle Pipeline** is now the main section, full width, directly under the
  status cards. Stages stretch to fill the row and stay clickable.
* Fixed the zero counts: the base domain no longer trusts `is_jobcard` blindly.
  If that flag is not populated in your database, a workshop stage
  (`cc_stage_id`) is used as the job card marker instead. When the selected
  period is empty but records exist, the dashboard says so and offers a
  one-click switch to All Time instead of silently showing zeros.
* Technician Performance: added Open jobs, Average Completion time and a
  current-jobs count, still in four bounded queries.
* Customer Waiting: added Waiting Time and Status; only open job cards with a
  customer are listed.
* Status cards show their share of the total alongside the trend.
* Navbar and dashboard title text forced to white.


## 1.2.0

Removed, with their Python, JS, templates, SCSS and config fields:

* the dashboard title bar (title, date, refresh button, global search)
* the advisor / technician / status / priority / company filter row
* the "no job cards for this period" notice
* Vehicle Pipeline (`pipeline.js`, `show_pipeline`, `show_in_pipeline`)
* Technician Performance (`tech_performance.js`, `show_technicians`)
* the `get_filter_options` and `search_job_cards` endpoints, now unused

Changed:

* Default period is **All Time** (config + data record).
* Layout: status cards -> Bay Occupancy (full width) -> Today's Job Cards +
  Quick Actions -> Overdue Jobs + Customer Waiting on one line -> alerts.
* **Bay occupancy** no longer looks at job cards only. A bay holds one record
  at a time, job card *or* vehicle inspection, and the tile names which it is
  plus that record's number. One query for all bays instead of one per bay.
* **Customer Waiting** is driven by the `customer_waiting` field on the job
  card (resolved at runtime, boolean or otherwise), not by "everything open".
* **High Priority** alert reads from the status: an explicit boolean on
  `job.card.stage` if your module defines one (`is_high_priority`,
  `is_urgent`, ...), otherwise statuses named Urgent / High Priority / Redo.
  The task `priority` field is only a last resort.
* **Appointments** opens the booking module and **Technician Board** opens the
  technician overview module. Both are resolved at runtime by client-action tag
  or by model prefix, so no hard dependency and no hardcoded XML id - if the
  module is absent the tile falls back to its generic action.
