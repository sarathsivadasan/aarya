# -*- coding: utf-8 -*-
"""Convert the flat schedule configuration into day and break lines.

Before this version a schedule carried `day_mon`..`day_sun`, one `hour_from`/
`hour_to` pair and one `lunch_from`/`lunch_to` pair. Those columns are gone
from the model, so without this script an upgraded database would end up with
schedules that have no working days at all and Generate Slots would refuse to
run.

The old columns are still physically present at post-migration time (Odoo
does not drop unknown columns), so we read them directly with SQL and rebuild
the equivalent `odex.booking.schedule.day` and `odex.booking.break` rows.
"""
import logging

_logger = logging.getLogger(__name__)

DAY_COLUMNS = ['day_mon', 'day_tue', 'day_wed', 'day_thu', 'day_fri',
               'day_sat', 'day_sun']


def _columns(cr, table):
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
    """, (table,))
    return {row[0] for row in cr.fetchall()}


def migrate(cr, version):
    if not version:
        return

    columns = _columns(cr, 'odex_booking_schedule')
    if not set(DAY_COLUMNS) & columns:
        _logger.info('No legacy schedule columns found; nothing to convert.')
        return

    select = ['id'] + [c for c in DAY_COLUMNS if c in columns]
    for extra in ('hour_from', 'hour_to', 'lunch_from', 'lunch_to'):
        if extra in columns:
            select.append(extra)
    cr.execute('SELECT %s FROM odex_booking_schedule' % ', '.join(select))
    rows = cr.dictfetchall()
    if not rows:
        return

    converted = 0
    for row in rows:
        schedule_id = row['id']

        # Skip schedules that already have day lines (re-run safety).
        cr.execute("""
            SELECT 1 FROM odex_booking_schedule_day
            WHERE schedule_id = %s LIMIT 1
        """, (schedule_id,))
        if cr.fetchone():
            continue

        hour_from = row.get('hour_from') or 9.0
        hour_to = row.get('hour_to') or 18.0
        for index, column in enumerate(DAY_COLUMNS):
            is_working = bool(row.get(column)) if column in row else index < 5
            cr.execute("""
                INSERT INTO odex_booking_schedule_day
                    (schedule_id, dayofweek, is_working, hour_from, hour_to,
                     capacity)
                VALUES (%s, %s, %s, %s, %s, 0)
            """, (schedule_id, str(index), is_working, hour_from, hour_to))

        lunch_from = row.get('lunch_from')
        lunch_to = row.get('lunch_to')
        if lunch_from is not None and lunch_to is not None \
                and lunch_to > lunch_from:
            cr.execute("""
                INSERT INTO odex_booking_break
                    (name, schedule_id, hour_from, hour_to, show_in_grid)
                VALUES (%s, %s, %s, %s, TRUE)
            """, ('Lunch', schedule_id, lunch_from, lunch_to))
        converted += 1

    _logger.info('Converted %s schedules to day/break lines.', converted)
