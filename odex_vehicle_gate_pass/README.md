# Vehicle Gate Pass (`odex_vehicle_gate_pass`)

Production Odoo 18 Community module that controls vehicle entry and exit for a
workshop, with OCR plate/Mulkiya scanning, a clickable damage map, typed photos
and an automatic workflow timeline.

## Workflow

    Gatepass In → Vehicle → Inspection → Quotation → RFQ → Jobcard → Invoice → Gatepass Out

Each step is reachable from the flow bar or the header buttons, and can only be
started once the previous one is done. The timeline updates itself on every move.

## Data sources — nothing is faked

* Customer data comes from `res.partner`.
* Vehicle data comes from `fleet.vehicle` (field names are probed at runtime, so
  a customised fleet works too).
* Payment status is computed from the linked customer invoice (`account.move`).
* Quotation (`sale.order`), RFQ (`purchase.order`) and Job Card links resolve at
  runtime, so the module installs whether or not those apps are present.

## OCR

OCR is a pluggable service (`odex.ocr.service`). Configure it under
**Gate Pass → Configuration → Settings**:

* **Disabled** — the scan buttons report that OCR is not configured.
* **Local** — uses `pytesseract` + Pillow on the server.
* **External API** — posts the image to an endpoint you configure. The API key
  is stored in a system parameter and is **never** sent to the browser.

The scan buttons sit *beside* Registration No. (plate) and Chassis No. (Mulkiya)
— they are field actions, not separate cards.

## Camera

Uses `navigator.mediaDevices.getUserMedia()` where available and falls back to a
file picker when the camera is unsupported or permission is denied.

## Gatepass-out rules

Optional, configurable in Settings: require the inspection step, require full
payment, and/or block check-out while major damage is unresolved.

## Note on overlap with `odex_gatepass`

This module ships a separate `odex.gate.pass` model and its own menu. If the
existing `odex_gatepass` module is installed in the same database, the two
coexist but cover overlapping ground — decide which one is the system of record.

## Validate before install

    ./tools/check_all.sh
