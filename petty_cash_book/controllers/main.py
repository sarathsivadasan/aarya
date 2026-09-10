# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import date, datetime
import json
import logging

_logger = logging.getLogger(__name__)


class PettyCashController(http.Controller):

    @http.route('/petty_cash/dashboard_data', type='json', auth='user', methods=['POST'])
    def get_dashboard_data(self, date_from=None, date_to=None, account_id=None, journal_id=None):
        """Return dashboard data as JSON for the frontend dashboard widget."""
        try:
            today = date.today()

            if date_from:
                if isinstance(date_from, str):
                    date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            else:
                date_from = today.replace(day=1)

            if date_to:
                if isinstance(date_to, str):
                    date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            else:
                date_to = today

            dashboard_model = request.env['petty.cash.dashboard']
            data = dashboard_model.sudo().get_dashboard_data(
                date_from=date_from,
                date_to=date_to,
                account_id=int(account_id) if account_id else None,
                journal_id=int(journal_id) if journal_id else None,
            )
            return {'status': 'ok', 'data': data}

        except Exception as e:
            _logger.error("Petty Cash Dashboard Error: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/petty_cash/accounts', type='json', auth='user', methods=['POST'])
    def get_cash_accounts(self):
        """Return list of cash accounts for the account selector."""
        try:
            company = request.env.company
            accounts = request.env['account.account'].sudo().search([
                ('company_id', '=', company.id),
                ('account_type', 'in', ['asset_cash', 'asset_current']),
                ('deprecated', '=', False),
            ])
            return {
                'status': 'ok',
                'accounts': [{'id': a.id, 'name': a.name, 'code': a.code} for a in accounts]
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/petty_cash/journals', type='json', auth='user', methods=['POST'])
    def get_cash_journals(self):
        """Return list of cash/bank journals."""
        try:
            company = request.env.company
            journals = request.env['account.journal'].sudo().search([
                ('company_id', '=', company.id),
                ('type', 'in', ['cash', 'bank']),
            ])
            return {
                'status': 'ok',
                'journals': [{'id': j.id, 'name': j.name} for j in journals]
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
