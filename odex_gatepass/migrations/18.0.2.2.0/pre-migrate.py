# -*- coding: utf-8 -*-
"""Inspection removed from the Gate Pass.

Remap retired selection values before the ORM drops them:
- vehicle_status 'under_inspection'  -> 'in_workshop'
- vehicle_status_override 'under_inspection' -> NULL (back to Auto)
- job_type 'inspection' -> 'general_service'
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE fleet_gate_pass
           SET vehicle_status = 'in_workshop'
         WHERE vehicle_status = 'under_inspection'
    """)
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'fleet_gate_pass'
           AND column_name = 'vehicle_status_override'
    """)
    if cr.fetchone():
        cr.execute("""
            UPDATE fleet_gate_pass
               SET vehicle_status_override = NULL
             WHERE vehicle_status_override = 'under_inspection'
        """)
    cr.execute("""
        UPDATE fleet_gate_pass
           SET job_type = 'general_service'
         WHERE job_type = 'inspection'
    """)
