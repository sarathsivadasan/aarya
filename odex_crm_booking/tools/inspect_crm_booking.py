# Run on the server BEFORE and AFTER installing/upgrading:
#   cd /opt/odoo18/wms25ii && ./odoo-bin shell -c <conf> -d <db> < odex_crm_booking/tools/inspect_crm_booking.py
# Prints the real model / field names this connector resolves, so nothing is assumed.
B = env["odex.crm.booking.bridge"] if "odex.crm.booking.bridge" in env else None

def custom_fields(model, limit_types=None):
    out = []
    for name, f in sorted(env[model]._fields.items()):
        mod = getattr(f, "_module", None)
        if mod in (None, "base", "mail", "crm", "fleet", "sales_team", "utm", "phone_validation",
                   "web", "rating", "portal", "calendar", "resource", "iap", "sale_crm", "website_crm"):
            continue
        rel = getattr(f, "comodel_name", "") or ""
        out.append("   %-32s %-10s %-28s [%s]" % (name, f.type, rel, mod))
    return out

print("=" * 78)
print("crm.lead fields added by custom modules:")
print("\n".join(custom_fields("crm.lead")) or "   (none)")
print("\nfleet.vehicle fields added by custom modules:")
print("\n".join(custom_fields("fleet.vehicle")) or "   (none)")

mods = env["ir.module.module"].search([("name", "ilike", "book"), ("state", "=", "installed")])
print("\nInstalled booking-related modules:", mods.mapped("name"))
imd = env["ir.model.data"].search([("module", "in", mods.mapped("name")), ("model", "=", "ir.model")])
for m in env["ir.model"].browse(imd.mapped("res_id")).exists():
    if m.model not in env:
        continue
    flds = env[m.model]._fields
    rels = sorted("%s->%s" % (n, f.comodel_name) for n, f in flds.items()
                  if f.type == "many2one" and f.comodel_name in ("res.partner", "fleet.vehicle", "crm.lead"))
    print("   %-36s abstract=%s %s" % (m.model, env[m.model]._abstract, rels))

if B:
    print("\nConnector resolution:")
    bm = B._booking_model()
    print("   booking model        :", bm)
    print("   booking lead field   :", bm and B._booking_lead_field(bm))
    print("   vehicle owner field  :", B._vehicle_owner_field())
    if bm:
        from odoo.addons.odex_crm_booking.models.booking_bridge import BOOKING_DEFAULT_MAP
        for key, cands in BOOKING_DEFAULT_MAP.items():
            print("   booking.%-12s -> %s" % (key, B._pick_field(bm, cands)))
    from odoo.addons.odex_crm_booking.models.crm_lead import VEHICLE_INFO
    for crm, (key, cands) in VEHICLE_INFO.items():
        print("   fleet.%-14s -> %s" % (key, next((c for c in cands if c in env["fleet.vehicle"]._fields), None)))
print("=" * 78)
