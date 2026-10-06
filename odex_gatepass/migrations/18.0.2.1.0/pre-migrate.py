# -*- coding: utf-8 -*-
"""Payment status reduced to Paid / Not Paid.

Remap the retired values before the ORM drops them from the selection
(otherwise Odoo would null them out on upgrade).
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE fleet_gate_pass
           SET payment_status = 'not_paid'
         WHERE payment_status IS NULL
            OR payment_status IN ('nothing', 'partial')
    """)
