# Change Log — Portal & Booking Rework

## Modified Python files
| File | Change |
|---|---|
| `models/__init__.py` | registers `booking_location` |
| `models/booking_location.py` | **new** — `odex.booking.location` pickup/drop model |
| `models/booking_booking.py` | `pickup_location_id`, `drop_location_id`, `service_status`, `payment_status`; `referral_source` indexed + tracked; dashboard now returns `acquisition` instead of `advisors`; booking rows return referral/service-status labels; detail payload returns pickup/drop/service status |
| `models/res_partner.py` | `booking_pickup_location_id`, `booking_drop_location_id` replace the branch-based drop fields |
| `models/fleet_vehicle.py` | **removed** `emirate`, `plate_code` |
| `models/booking_slot.py` | `_` import fix (dashboard `NameError`) |
| `controllers/portal.py` | `/my` + `/my/home` + `/my/workshop` dashboard landing; `/my/workshop/locations`; `/my/quotations`; `_booking_related()`; location-based support page; `_optional()` now reads `fleet_emirate_id` / `fleet_code_id` |
| `controllers/website_booking.py` | pickup/drop in page context and submit; emirates/plate codes from `fleet.emirates` / `fleet.characters`; writes native fleet fields when present |

## Modified XML files
`views/portal_templates.xml` (bookings table, vehicles list, quotations, booking detail), `views/portal_workshop_templates.xml` (pickup+drop card, tiles), `views/website_templates.xml` (location selects, native plate lookups), `views/booking_views.xml` (new fields, group-bys, acquisition pie), `views/config_views.xml` (location views/action), `views/menus.xml` (Locations, Customer Acquisition), `views/fleet_partner_views.xml` (duplicate fields removed), `security/booking_security.xml` (portal record rules), `static/src/dashboard/dashboard.xml` (acquisition donut, service status column).

## Security changes
**New ACLs:** `odex.booking.location` (user read / manager full / portal + public read), `fleet.vehicle`, `fleet.vehicle.model`, `fleet.vehicle.model.brand` — **read only** for `base.group_portal`.

**New record rules:**
- `rule_vehicle_portal` — portal users read only vehicles where `driver_id` is their partner or a child of their commercial partner. No write/create/unlink.
- `rule_vehicle_model_portal` — read-only access to models/brands (needed to render names).
- `rule_location_portal` — portal users see only published locations.

No `sudo()` was added to widen access on customer-owned records; `sudo()` appears only for reference data (locations, emirates, plate codes) and for reads already filtered by the customer's own partner.

## New fields
| Model | Field |
|---|---|
| `odex.workshop.booking` | `pickup_location_id`, `drop_location_id`, `service_status`, `payment_status` |
| `res.partner` | `booking_pickup_location_id`, `booking_drop_location_id` |
| `odex.booking.location` | all (new model) |

## Removed fields
| Model | Field | Replacement |
|---|---|---|
| `fleet.vehicle` | `emirate` | `fleet_emirate_id` (`fleet.emirates`) |
| `fleet.vehicle` | `plate_code` | `fleet_code_id` (`fleet.characters`) |
| `res.partner` | `booking_drop_company_id`, `booking_drop_branch_id` | `booking_drop_location_id` |

## Migration notes
1. **Before upgrading**, capture the duplicated plate data if any was entered through the portal:
   ```sql
   SELECT id, license_plate, emirate, plate_code FROM fleet_vehicle
   WHERE emirate IS NOT NULL OR plate_code IS NOT NULL;
   ```
   Map those to `fleet_emirate_id` / `fleet_code_id` after the upgrade. Odoo drops the columns only when you run with `--update` and the fields are gone from the model; existing data in them is not migrated automatically.
2. `res.partner.booking_drop_branch_id` / `booking_drop_company_id` are removed. They only held a UI preference, so no data migration is required.
3. Create at least one **Booking → Configuration → Pickup & Drop Locations** record, otherwise the location selectors stay hidden (by design — they are optional).
4. `service_status` is computed+stored from `state` on first upgrade; existing bookings backfill automatically.

## Manifest changes
No new dependencies. `views/portal_workshop_templates.xml` and `static/src/website/portal_workshop.scss` were already registered in the previous build; nothing added this round.

## Migration 18.0.1.0.0 → 18.0.2.0.0 (branch removal data fix)

`migrations/18.0.2.0.0/post-migration.py`.

**Why it is needed.** Renaming `branch_id` to `company_id` in the Python
models does not move data. Odoo adds a new, empty `company_id` column and
leaves `branch_id` in place, so every pre-existing row ended with
`company_id IS NULL`. Consequences:

| Symptom | Mechanism |
|---|---|
| Website calendar entirely grey | `_scope_domain` filters `company_id = X`, which matched no rows |
| `start_datetime` empty | its compute needs `company_id` |
| `/booking/api/month` 500 | `_is_bookable` did `False <= datetime` → TypeError |

**What it does**, on `odex_booking_slot`, `odex_workshop_booking`,
`odex_booking_schedule`, `odex_booking_holiday`,
`odex_booking_working_hours`:

1. Recovers `company_id` from the old `branch_id` via `res_branch.company_id`
   when that table and column still exist.
2. Falls back to the lowest-id company for anything still empty.
3. Clears the stored slot datetimes so they recompute; the module's
   `repair_missing_datetimes()` (run from `data/cron_data.xml` on every
   upgrade) then fills them eagerly.

Every step checks that the table/column exists first, so the script is safe
on a fresh install and safe to re-run.

**Verification after upgrading:**

```sql
SELECT count(*) FROM odex_booking_slot WHERE company_id IS NULL;      -- 0
SELECT count(*) FROM odex_booking_slot WHERE start_datetime IS NULL;  -- 0
```

## Scheduling engine refactor (18.0.3.0.0)

The flat schedule (one working window, one lunch, seven booleans) is replaced
by three configuration models. **Migration `18.0.3.0.0/post-migration.py`
converts existing schedules** — it reads the old columns, which Odoo leaves in
place, and rebuilds equivalent day and break rows. Without it an upgraded
schedule would have no working days and Generate Slots would refuse to run.

| Model | Purpose |
|---|---|
| `odex.booking.schedule.day` | One row per weekday: open/closed, its own hours, its own capacity override, its own breaks |
| `odex.booking.break` | Any number of breaks. Attached to one day, or left dayless to apply to every working day |
| `odex.booking.offday` | Specific dates that are skipped. Independent of weekday; blocks slots already generated |

### What this fixes
- **Per-day hours** — Mon 09:00-18:00, Sat 08:00-14:00, Sun closed all coexist
- **Manual off days** — any date, via the row list or the *Add Off Days* wizard (single date / range / every occurrence of a weekday)
- **Multiple breaks** — tea, lunch, prayer; generation skips all of them
- **Configurable Limited threshold** — `limited_threshold` on the schedule
- **Expired** — computed live from `start_datetime`, never stored, because it changes with the clock

### Deliberately not stored
`booked_count`, `remaining` and `state` remain computed with `@api.depends` on
`booking_ids.state`, so cancelling or moving a booking recalculates capacity
immediately with no cron and no manual refresh.

## Apply Changes (schedule → slot sync)

**The bug.** `Generate Slots` only ever ADDED missing slots. Opening Saturday
or moving the start from 09:00 to 08:00 therefore appeared to do nothing: the
new slots were created only if you re-ran generation, and the *old* slots were
never removed. Narrowing a day left orphaned slots that customers could still
book.

**The fix.** `action_sync_slots()` ("Apply Changes") makes the generated slots
match the configuration exactly:

1. `_expected_slots()` builds the (date, time) set the configuration implies —
   one definition read by both halves, so they cannot disagree.
2. Missing slots are created.
3. Slots the configuration no longer implies are **deleted when free** and
   **blocked when they already have bookings**, never silently cancelled. The
   count of blocked slots is reported so staff can follow up.
4. Capacity is realigned per day, but never below what is already booked.

`config_dirty` is set whenever days, breaks, off days, duration, capacity or
the effective dates change, which drives a warning banner on the form. Slots
are deliberately NOT regenerated implicitly, because applying can delete
records — it stays an explicit, confirmable action.

`Generate Only (add missing)` remains available for the additive case.
