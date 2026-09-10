# -*- coding: utf-8 -*-
"""JSON integration endpoint (section 42).

Disabled by default. An administrator enables it in the Mulkiya OCR settings,
and it is always restricted to authenticated Odoo users belonging to the
Mulkiya Scan User group, so no API credential ever leaves the server.
"""

import logging

from odoo import http
from odoo.http import request

from ..services import constants

_logger = logging.getLogger(__name__)


class MulkiyaScanController(http.Controller):

    def _check_enabled(self):
        params = request.env['ir.config_parameter'].sudo()
        enabled = params.get_param(constants.PARAM_API_ENABLED, 'False')
        if enabled not in ('True', 'true', '1'):
            return {'success': False, 'error': 'endpoint_disabled',
                    'message': 'The Mulkiya scan endpoint is not enabled.'}
        if not request.env.user.has_group('odex_mulkiya_scan.group_mulkiya_user'):
            return {'success': False, 'error': 'access_denied',
                    'message': 'You are not allowed to use the Mulkiya scan API.'}
        return None

    @http.route('/api/mulkiya/scan', type='json', auth='user', methods=['POST'],
                csrf=False)
    def scan(self, front_image=None, back_image=None, source_reference=None,
             auto_verify=False, **kwargs):
        """Create a scan from two base64 images and return the structured result."""
        error = self._check_enabled()
        if error:
            return error
        if not front_image or not back_image:
            return {'success': False, 'error': 'missing_image',
                    'message': 'Both front_image and back_image are required.'}

        Scan = request.env['odex.mulkiya.scan']
        scan = Scan.create({
            'front_image': front_image,
            'back_image': back_image,
            'source_reference': source_reference or 'api',
        })
        try:
            scan.action_scan()
        except Exception as exc:
            _logger.warning("Mulkiya API scan failed: %s", exc)
            return {'success': False, 'error': 'ocr_failed',
                    'message': str(exc), 'scan_id': scan.id}

        if scan.state == constants.STATE_FAILED:
            return {'success': False, 'error': 'ocr_failed',
                    'message': scan.ocr_error, 'scan_id': scan.id,
                    'scan_number': scan.name}

        if auto_verify and not scan._missing_required_fields():
            scan.action_confirm()
        return scan.get_structured_result()

    @http.route('/api/mulkiya/scan/<int:scan_id>', type='json', auth='user',
                methods=['POST'], csrf=False)
    def read_scan(self, scan_id, **kwargs):
        """Return the structured result of an existing scan."""
        error = self._check_enabled()
        if error:
            return error
        scan = request.env['odex.mulkiya.scan'].browse(scan_id)
        if not scan.exists():
            return {'success': False, 'error': 'not_found',
                    'message': 'Scan %s does not exist.' % scan_id}
        scan.check_access('read')
        return scan.get_structured_result()
