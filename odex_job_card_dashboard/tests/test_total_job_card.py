# -*- coding: utf-8 -*-
"""Total Job Card - run with:
    odoo-bin -c <conf> -d <test_db> -u odex_job_card_dashboard \
        --test-tags /odex_job_card_dashboard --stop-after-init
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTotalJobCard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dash = cls.env['job.card.dashboard']
        cls.Stage = cls.env['job.card.stage']
        cls.stage_field = cls.Dash._f('stage')
        cls.closed = cls.Stage._dashboard_closed_stages()[:1]
        cls.open_stages = cls.Stage.search([('id', 'not in', cls.closed.ids)], limit=3)
        cls.project = cls.env['project.project'].create({'name': 'JCD Total test'})
        cls.env['job.card.dashboard.card']._ensure_cards()

    def setUp(self):
        super().setUp()
        if not (self.stage_field and self.closed and len(self.open_stages) >= 3):
            self.skipTest('Needs cc_stage_id, a Closed status and 3 open statuses')
        # Isolate from existing data: only our project's tasks count.
        self.filters = {'date_filter': 'all'}
        base = self.Dash._filter_domain
        self.patch(type(self.Dash), '_filter_domain', lambda s, f: base(f) + [
            ('project_id', '=', self.project.id)])

    def _new(self, stage):
        vals = {'name': 'JCD test', 'project_id': self.project.id,
                self.stage_field: stage.id}
        flag = self.Dash._f('job_card_flag')
        if flag:
            vals[flag] = True
        try:
            with self.env.cr.savepoint():
                return self.env['project.task'].create(vals)
        except Exception as error:  # schema needs more required fields
            self.skipTest('Cannot create a job card here: %s' % error)

    def _card(self, name='total_job_card', filters=None):
        cards = self.Dash.get_dashboard_data(filters or self.filters)['statuses']
        return next(c for c in cards if c['id'] == name)

    def _total(self, filters=None):
        return self._card(filters=filters)['count']

    def _closed(self):
        return self._card(self.closed.id)['count']

    def test_open_close_reopen(self):
        vi, wip, wfp = self.open_stages
        jobs = [self._new(vi) for _ in range(5)]
        self.assertEqual(self._total(), 5)                         # T1
        jobs[0][self.stage_field] = self.closed
        self.assertEqual((self._total(), self._closed()), (4, 1))  # T2
        jobs[0][self.stage_field] = wip
        self.assertEqual((self._total(), self._closed()), (5, 0))  # T3
        jobs[1][self.stage_field] = wip
        self.assertEqual(self._total(), 5)                         # T4
        jobs[1][self.stage_field] = wfp
        self.assertEqual(self._total(), 5)                         # T5
        jobs[1][self.stage_field] = self.closed
        self.assertEqual(self._total(), 4)                         # T6
        for _ in range(10):                                        # T14
            jobs[1][self.stage_field] = wip
            self.assertEqual(self._total(), 5)
            jobs[1][self.stage_field] = self.closed
            self.assertEqual(self._total(), 4)

    def test_matches_search_count_and_drilldown(self):
        vi = self.open_stages[0]
        for stage in (vi, vi, self.closed):
            self._new(stage)
        domain = self.Dash._filter_domain(self.filters) + self.Dash._active_domain()
        self.assertEqual(self._total(), self.env['project.task'].search_count(domain))
        rows = self.Dash.get_stage_details('total_job_card', self.filters, 50)['rows']
        self.assertEqual(len(rows), 2)
        action = self.Dash.get_status_action('total_job_card', self.filters)
        self.assertEqual(self.env['project.task'].search_count(action['domain']), 2)

    def test_date_filters_follow_dashboard(self):
        self._new(self.open_stages[0])
        for mode in ('today', 'week', 'month', 'all'):             # T7-T10
            self.assertEqual(self._total({'date_filter': mode}), 1, mode)
        today = fields.Date.context_today(self.Dash)
        past = {'date_filter': 'custom',                           # T11
                'date_from': fields.Date.to_string(today - timedelta(days=30)),
                'date_to': fields.Date.to_string(today - timedelta(days=20))}
        self.assertEqual(self._total(past), 0)

    def test_reserved_status_name(self):
        with self.assertRaises(ValidationError):
            self.Stage.search([], limit=1).name = 'Total Job Card'
