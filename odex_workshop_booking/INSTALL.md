# Installation Guide

## 1. Deploy
```bash
scp -r odex_workshop_booking user@wms25ii.odex.in:/opt/odoo18/wms25ii/custom_addons/
```
Ensure the addons path includes the target directory, then restart:
```bash
sudo systemctl restart odoo18   # or your service name
```
(Python model changes always require a full process restart on this server.)

## 2. Install
Apps → update apps list → search **Booking** → Install.
Dependencies (auto-installed): website, fleet, calendar, portal, mail, contacts.

## 3. Configure (in order)
1. **Booking → Configuration → Workshop Locations** (or Settings → Users & Companies → Companies) — open each company and use the **Workshop Booking** tab: booking timezone, *Visible on Website*, slot duration, capacity, notice/window/cancel/reschedule rules, and advisors. There is no separate branch model — the company is the branch.
2. **Booking → Configuration → Holidays & Closures** — add holiday list.
3. **Booking → Slot Management → Working Schedules** — create the **company default** schedule first (Company set, Branch empty). Add branch schedules only where a branch works different hours; any branch without one falls back to the default. Create one schedule per company (or open the company and click the *Working Schedule* button). Set working days, working hours, lunch break, slot duration, default capacity and the effective date range, then click **Generate Slots**. Re-run or extend *Effective To* later — existing slots are never duplicated. Holidays and closures are skipped.
4. **Booking → Configuration → Service Types** — 14 types are seeded; adjust visibility.
5. **Booking → Configuration → Settings** — auto-confirm toggle, T&C URL, help phone.
6. **Settings → Users** — assign *Booking / Service Advisor* or *Workshop Manager* groups.
7. Configure an outgoing mail server (Settings → Technical → Outgoing Mail Servers). Notification emails are **queued**, not sent inline, so a missing mail server no longer breaks a booking — the messages simply sit in Settings → Technical → Email → Emails until a server exists and the *Mail: Email Queue Manager* cron runs.

### Upgrading from a build that used `odex.booking.branch`
That model is gone — `res.company` replaced it, and every `branch_id` became `company_id`. Odoo will not migrate existing branch records automatically. On a database that already had bookings, map them before upgrading:

```sql
-- inspect what existed
SELECT id, name, company_id FROM odex_booking_branch;
```
Then, after the upgrade, set `company_id` on `odex_workshop_booking` and `odex_booking_slot` to the matching company, and re-run Generate Slots. On a fresh/test database no action is needed.

### Upgrading from an earlier build of this module
The redesigned Slot Management adds models and drops the old bulk-generate wizard, so upgrade rather than just restart:
```bash
/opt/odoo18/wms25ii/odoo-bin -c <conf> -d <db> -u odex_workshop_booking --stop-after-init
sudo systemctl restart odoo18
```
Existing slots are preserved. Create a schedule per branch and click **Generate Slots** once — slots created before the upgrade are auto-linked to their branch schedule when touched, and you can also link them in bulk from *All Slots* by setting the Working Schedule field.

## 4. Verify
- Open `/book-service` in an incognito window → complete a test booking.
- Booking appears in Booking → Bookings as **Requested** (or **Confirmed** if auto-confirm on), slot booked count increments, calendar event exists, email queued.
- Portal user: `/my/bookings` → reschedule + cancel.
- If the wizard shows "Online booking is not available yet", no company has **Visible on Website** ticked in its Workshop Booking tab.

## 5. Assets note
After updating SCSS/JS on this server, hard-refresh or regenerate assets (Settings → Technical → Regenerate Asset Bundles) — asset bundle caching applies.
