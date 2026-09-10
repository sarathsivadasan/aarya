# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..providers.base_provider import provider_selection
from ..services import constants


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mulkiya_ocr_enabled = fields.Boolean(
        string='Enable Mulkiya OCR',
        config_parameter=constants.PARAM_ENABLED, default=True)
    mulkiya_ocr_provider = fields.Selection(
        selection=lambda self: provider_selection(),
        string='OCR Provider', config_parameter=constants.PARAM_PROVIDER,
        default='demo')
    mulkiya_api_url = fields.Char(
        string='API URL', config_parameter=constants.PARAM_API_URL,
        help="Leave empty to use the provider default endpoint.")
    mulkiya_api_key = fields.Char(
        string='API Key', config_parameter=constants.PARAM_API_KEY)
    mulkiya_api_secret = fields.Char(
        string='API Secret', config_parameter=constants.PARAM_API_SECRET)
    mulkiya_api_model = fields.Char(
        string='Model / Engine', config_parameter=constants.PARAM_API_MODEL,
        help="Provider specific model name, e.g. claude-sonnet-4-5 or gpt-4o. "
             "Leave empty to use the provider default.")
    mulkiya_confidence_threshold = fields.Integer(
        string='Confidence Threshold (%)',
        config_parameter=constants.PARAM_THRESHOLD,
        default=constants.DEFAULT_THRESHOLD,
        help="Fields extracted below this confidence are highlighted for "
             "manual verification.")
    mulkiya_timeout = fields.Integer(
        string='Timeout (seconds)', config_parameter=constants.PARAM_TIMEOUT,
        default=constants.DEFAULT_TIMEOUT)
    mulkiya_max_dimension = fields.Integer(
        string='Max Image Dimension (px)',
        config_parameter=constants.PARAM_MAX_DIMENSION,
        default=constants.DEFAULT_MAX_DIMENSION,
        help="Images larger than this are downscaled before being sent to the "
             "OCR provider.")
    mulkiya_max_file_mb = fields.Integer(
        string='Max Upload Size (MB)',
        config_parameter=constants.PARAM_MAX_FILE_MB,
        default=constants.DEFAULT_MAX_FILE_MB)
    mulkiya_api_enabled = fields.Boolean(
        string='Expose Scan Endpoint',
        config_parameter=constants.PARAM_API_ENABLED, default=False,
        help="Enable the /api/mulkiya/scan JSON endpoint for authenticated "
             "integration users.")

    @api.constrains('mulkiya_confidence_threshold')
    def _check_threshold(self):
        for record in self:
            if record.mulkiya_confidence_threshold and not \
                    0 <= record.mulkiya_confidence_threshold <= 100:
                raise UserError(_("The confidence threshold must be between "
                                  "0 and 100."))

    def action_mulkiya_test_connection(self):
        """Run a lightweight provider check with the current configuration."""
        self.ensure_one()
        from ..services.ocr_service import MulkiyaOcrService

        service = MulkiyaOcrService(self.env)
        provider = service.get_provider()
        try:
            provider.check_credentials()
        except Exception as exc:
            raise UserError(_("Configuration problem: %s", exc)) from exc
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Mulkiya OCR"),
                'message': _("Provider '%s' is configured.", provider.label),
                'type': 'success',
            },
        }
