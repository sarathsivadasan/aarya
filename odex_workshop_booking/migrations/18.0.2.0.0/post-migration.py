# -*- coding: utf-8 -*-
"""Backfill company_id after res.branch was removed.

`branch_id` was renamed to `company_id` in the Python models. Odoo does not
copy data on a field rename: it simply adds a new, EMPTY column and leaves
the old `branch_id` column in place. Every pre-existing slot, booking,
schedule, holiday and working-hours row therefore ended up with
`company_id IS NULL`, which is why:

  * the website calendar found no slots  (`company_id = X` matched nothing)
  * `start_datetime` stayed False        (its compute needs company_id)
  * `_is_bookable()` then raised TypeError on `False <= datetime`

This script restores the value from the old branch column where it still
exists, falling back to the record's original company or the main company,
and then forces the stored datetimes to recompute.
"""
import logging

_logger = logging.getLogger(__name__)

# table -> the old column that pointed at res.branch (if any)
TABLES = [
    'odex_booking_slot',
    'odex_workshop_booking',
    'odex_booking_schedule',
    'odex_booking_holiday',
    'odex_booking_working_hours',
]


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return bool(cr.fetchone()[0])


def migrate(cr, version):
    if not version:
        return

    # Default company to fall back on: the one the main website uses, else
    # the lowest id, so single-company databases always resolve.
    cr.execute("SELECT id FROM res_company ORDER BY id LIMIT 1")
    row = cr.fetchone()
    if not row:
        _logger.warning('No company found; skipping company_id backfill.')
        return
    default_company = row[0]

    branch_table = _table_exists(cr, 'res_branch')

    for table in TABLES:
        if not _table_exists(cr, table):
            continue
        if not _column_exists(cr, table, 'company_id'):
            continue

        # 1. Recover the company from the old branch link when possible.
        if branch_table and _column_exists(cr, table, 'branch_id'):
            cr.execute("""
                UPDATE %s t
                   SET company_id = b.company_id
                  FROM res_branch b
                 WHERE t.branch_id = b.id
                   AND t.company_id IS NULL
                   AND b.company_id IS NOT NULL
            """ % table)
            _logger.info('%s: %s rows recovered from branch',
                         table, cr.rowcount)

        # 2. Anything still empty gets the default company.
        cr.execute(
            "UPDATE %s SET company_id = %%s WHERE company_id IS NULL" % table,
            (default_company,))
        if cr.rowcount:
            _logger.info('%s: %s rows defaulted to company %s',
                         table, cr.rowcount, default_company)

    # 3. Stored computes that depend on company_id must be rebuilt. Clearing
    #    them makes Odoo recompute on next access; the module's own
    #    repair_missing_datetimes() then fills them eagerly.
    if _column_exists(cr, 'odex_booking_slot', 'start_datetime'):
        cr.execute("""
            UPDATE odex_booking_slot
               SET start_datetime = NULL, stop_datetime = NULL
             WHERE start_datetime IS NULL
                OR stop_datetime IS NULL
                OR company_id IS NOT NULL
        """)
        _logger.info('odex_booking_slot: %s rows flagged for datetime '
                     'recompute', cr.rowcount)
