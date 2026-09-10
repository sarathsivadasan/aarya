# Odex Workshop Booking (`odex_workshop_booking`)

Standalone appointment scheduling app for the Odex Workshop Management System — Odoo 18 Community.

**Scope:** booking only. No CRM leads, inspections, job cards, quotations, sales orders, invoices, or accounting. Those processes continue manually after the customer arrives.

## Architecture

### Models
| Model | Purpose |
|---|---|
| `odex.workshop.booking` | Booking (BK000001 sequence, workflow, chatter, portal access) |
| `odex.booking.slot` | Time slot with capacity, booked count and computed status (available / limited / full / blocked) |
| `res.branch` | Reused from the existing multi-branch add-on — this module only declares it so the fields merge; it never replaces it |
| `res.company` (inherit) | **The company IS the branch** — no separate branch model. Carries booking timezone, website visibility, slot duration/capacity, booking rules (notice, window, cancel, reschedule limits), advisors, reference working hours, and the Working Schedule / Slots / Bookings stat buttons |
| `odex.booking.working.hours` | Weekday hour ranges per company (two lines per day = break time) |
| `odex.booking.holiday` | Holidays and emergency closures (per company or global); auto-blocks existing slots |
| `odex.booking.service.type` | Configurable service catalogue (seeded with 14 types) |
| `odex.booking.reschedule` | Reschedule requests; approving moves the booking, releases the old slot, updates the calendar event and emails the customer |
| `odex.booking.schedule` | **Working Schedule** — the slot-management screen: working days, hours, lunch break, slot duration, capacity, effective range, overbooking, KPIs, and the one2many slot lines |
| `odex.booking.schedule.copy` | Wizard: copy a schedule to another branch / company / date range |
| `odex.booking.block.day` | Wizard: block or unblock a date range, optionally recording a closure |
| `odex.booking.schedule.import` | Wizard: import slot lines from CSV |
| `fleet.vehicle` (inherit) | + emirate, plate code, engine number, cylinders, booking smart button, plate/VIN dedup helper |
| `res.partner` (inherit) | + Vehicles tab, booking smart button, mobile/phone/email dedup helper |

### Two-level scheduling (company + branch)
`odex.booking.schedule` carries a mandatory `company_id` and an **optional** `branch_id`:

| Schedule | company_id | branch_id | Meaning |
|---|---|---|---|
| Company default | required | empty | Governs the whole company; fallback for every branch without its own |
| Branch schedule | required | set | Overrides the default for that branch only |

`odex.booking.schedule._resolve(company, branch)` implements the priority: **branch schedule first, company schedule as fallback**, and returns an empty recordset rather than raising when neither exists. `odex.booking.slot._scope_domain(company, branch)` mirrors it for slots — a branch uses its own slots when it has any, otherwise the company-level ones — so availability, the website wizard, portal reschedule and the dashboard all follow the same fallback.

Each company may hold one default schedule plus any number of branch schedules; they coexist and never affect each other. Generate Slots stamps `branch_id` from its schedule, so slots stay in their own lane. Uniqueness of (company, branch) is enforced by a SQL constraint plus a Python `@api.constrains` — needed because Postgres treats NULL `branch_id` values as distinct, so the SQL index alone would allow two company-level schedules.

### Workflow
Draft → Requested → Confirmed → Arrived → Completed, with Cancelled and No Show exits.
Confirmation creates a `calendar.event` and sends the confirmation email. Cancellation releases the slot and removes the event.

### Deduplication (business rule: never duplicate)
- Customer matched on **mobile / phone / email** (`res.partner._find_or_create_from_booking`)
- Vehicle matched on **plate / VIN** (`fleet.vehicle._find_or_create_from_booking`), owner = customer via `driver_id` — vehicles appear on the customer's Vehicles tab automatically

### Double-booking prevention
- SQL unique constraint on (vehicle, slot)
- Python constraint: one active booking per vehicle per day
- Capacity constraint on every write; slot status recomputes instantly and full slots disappear from the website

### Public website (`/book-service`)
5-step Calendly-style wizard (Bootstrap 5, mobile-first, light theme):
1. Branch + calendar with month availability colors (available / limited / fully booked / closed / holiday); past dates and closures disabled
2. Time slots grouped Morning / Afternoon with live capacity colors
3. Customer details with **existing-customer detection on blur** (mobile/phone/email) + existing vehicle picker or new-vehicle form (UAE fields)
4. Service type, complaint (500 chars), "How did you hear about us?" (optional), notes (300 chars)
5. Summary + T&C consent → creates booking, reserves slot, calendar event, confirmation email → thank-you page with booking number

### JSON API (public, reusable by future Android/iOS apps)
| Endpoint | Payload |
|---|---|
| `POST /booking/api/month` | `branch_id, year, month` → day status map |
| `POST /booking/api/slots` | `branch_id, date` → slot list with capacity state |
| `POST /booking/api/customer_lookup` | `mobile, phone, email` → found + vehicles |
| `POST /booking/api/models` | `brand_id` → fleet models |
| `POST /booking/api/submit` | full booking payload → booking ref + redirect |
All endpoints are `type='json'` (JSON-RPC 2.0), validate slot availability server-side and only run vetted sudo operations.

### Customer portal
Dashboard at **/my/workshop** (the portal home card links here): customer details with Edit Profile, a Drop Location picker (company + optional branch, saved on the partner as `booking_drop_company_id` / `booking_drop_branch_id`), a responsive tile grid (4 / 2 / 1 columns), and My Vehicles at a Glance — a table on desktop that becomes cards on mobile.

Pages: `/my/vehicles` (list + add), `/my/vehicles/<id>` (full spec sheet, recent bookings, Book Appointment / Service History / Invoices actions), `/my/bookings` (+ detail, reschedule, cancel), `/my/service-history` (posted invoices expanded to line level: description, qty, unit price, discount, taxes, total), `/my/workshop/support` (company details, working hours, ticket / call / maps), `/my/workshop/documents` (vehicle attachments, view + download).

Tiles for Job Cards and Quotations only appear when those models exist on the database — `_sibling_model()` probes a candidate list at runtime, and `_optional()` reads vehicle fields (mulkiya, insurance, registration expiry, next service, warranty...) only when another Odex module has defined them. Nothing here declares a field it does not own, so the portal renders identically with or without the wider WMS suite.

**New Booking** always redirects to the existing `/book-service` wizard — no second booking flow. When a portal user is signed in, that wizard now prefills name / mobile / email from their partner and lists their own vehicles for one-click selection (auto-selected when they own exactly one), with "Book for another vehicle" falling back to the normal new-vehicle form.

### Customer portal (base)
`/my/bookings` (upcoming / history / all), booking detail with **reschedule modal** (live slot picker) and **cancel** (both gated by branch hour limits), `/my/vehicles` list + add-vehicle modal.

### Internal app (Booking menu)
- **Dashboard** — OWL client action rebuilt to the admin mockup:
  - KPI row: Total Bookings (this month), Confirmed, Pending, Arrived, Cancelled — each with its percentage share; clicking a card filters the bookings table
  - **Calendar Overview** with Month / Week / Day scales, month navigation and per-day availability dots; clicking a day drives the slot panel
  - **Slot Management panel** for the selected day: time slot, capacity, booked, status, and a kebab menu with Edit Slot · Set Capacity · Block Slot · Mark as Closed · Delete Slot, plus Add Slot and a Total Bookings x / y footer. Lunch breaks render as a coffee divider row
  - **Booking Status donut** (SVG) with counts and percentages, clickable legend
  - **Quick Actions**: New Booking · Block Time Slot · View Calendar
  - **All Bookings** table: server-side search (ref, customer, plate, mobile), pagination, and per-row View
  - **Booking Details** side panel: full record summary plus Confirm · Mark as Arrived · Complete · Cancel Booking · Reschedule, all running the real workflow methods
  - Secondary analytics below: 14-day bar chart, advisor utilization, most requested services
  - Branch selector scopes every widget
- **Bookings** — list / kanban (grouped by status) / calendar (drag-drop + resize native) / graph / pivot / activity, full search/filters/group-by
- **Calendar** — day/week/month, colored by advisor, branch + advisor filters, double-booking prevented by model constraints
- **Slot Management → Working Schedules** — schedule configuration page, not per-slot data entry:
  - Header config only: company, branch (defaults to the user's branch), working-day pills, working hours, lunch break, slot duration (15/20/30/45/60), default capacity, effective from/to, allow overbooking, active
  - Buttons: Generate Slots · Copy Schedule · Block Day · Import · Export · Calendar
  - KPI cards: total / available / limited / fully booked / blocked slots + total bookings
  - Editable slot lines: #, date, start, end, capacity, booked, available, status badge, block toggle — status is always computed (available > 1 free, limited = 1 free, fully booked = 0, blocked = manually blocked); it is never selectable
  - Clicking the Bookings button on a line opens a popup with booking number, customer, vehicle, service type and status — booking records are never embedded in the form
  - Bulk actions: Block All / Unblock All / Delete Empty Slots; multi-record block, unblock and delete also available from All Slots
  - Generate Slots derives every slot from working hours minus the lunch break and skips holidays/closures and slots that already exist
- **All Slots / Slot Calendar** — flat views over generated slots for spot checks; every generated slot appears in the slot calendar automatically, and Full or Blocked slots disappear from the website immediately
- **Reschedule Requests** — pending queue with approve (moves booking) / reject
- **Reports** — graph/pivot analysis: daily/weekly/monthly volumes, advisor utilization, peak hours (group by time), branch performance, top services, cancellations, no-shows
- **Configuration** — Branches (working hours, rules, team), Service Types, Holidays & Closures, Settings (auto-confirm, T&C URL, help phone)

### Security
| Group | Rights |
|---|---|
| Public | Website booking via controlled JSON endpoints only |
| Portal customer | Read own bookings (record rule), reschedule/cancel via gated controllers |
| Service Advisor | Manage bookings + reschedules, read config |
| Workshop Manager | Everything incl. slots, branches, holidays, settings |
Multi-company record rules on bookings, slots and branches.

### Emails
Confirmation, reminder (hourly cron, day-before), rescheduled, cancelled — responsive HTML templates. `_send_template()` is the single notification funnel: plug WhatsApp/SMS there later.

### Crons
- Reminder emails (hourly)
- Auto no-show for confirmed bookings 12h past their slot (6-hourly)
