# odex_crm_booking 18.0.2.0.0

CRM Lead -> Vehicle -> Booking connector. Nothing about the booking module is
hardcoded: the booking model, its CRM-lead field and the fleet owner field are
detected at install and stored in System Parameters (override if needed):

| Parameter | Meaning |
|---|---|
| `odex_crm_booking.booking_model` | booking model `_name` |
| `odex_crm_booking.booking_lead_field` | m2o crm.lead on the booking |
| `odex_crm_booking.vehicle_owner_field` | m2o res.partner on fleet.vehicle |

After changing a parameter: CRM > Configuration > Vehicle Service > Booking Integration.

Inspect the live database (before and after install):

    ./odoo-bin shell -c <conf> -d <db> < odex_crm_booking/tools/inspect_crm_booking.py

Static checks before deploy: `tools/check_all.sh`
