# -*- coding: utf-8 -*-
"""Orchestration of a Mulkiya scan.

    images -> validation/compression -> provider -> normalization -> matching

Credentials are read here, server side, and handed to the provider as a plain
dict. They never travel to the browser (section 35).
"""

import logging
import time

from odoo import _
from odoo.exceptions import UserError

from . import constants, image_service
from .matching_service import MatchingService
from .normalization_service import NormalizationService

_logger = logging.getLogger(__name__)


class MulkiyaOcrService:

    def __init__(self, env):
        self.env = env
        self.normalizer = NormalizationService(env)
        self.matcher = MatchingService(env, normalizer=self.normalizer)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def get_config(self):
        params = self.env['ir.config_parameter'].sudo()

        def _int(key, default):
            try:
                return int(params.get_param(key, default) or default)
            except (TypeError, ValueError):
                return default

        return {
            'enabled': params.get_param(constants.PARAM_ENABLED, 'True') in
                       ('True', 'true', '1', True),
            'provider': params.get_param(constants.PARAM_PROVIDER, 'demo'),
            'api_url': params.get_param(constants.PARAM_API_URL, ''),
            'api_key': params.get_param(constants.PARAM_API_KEY, ''),
            'api_secret': params.get_param(constants.PARAM_API_SECRET, ''),
            'api_model': params.get_param(constants.PARAM_API_MODEL, ''),
            'timeout': _int(constants.PARAM_TIMEOUT, constants.DEFAULT_TIMEOUT),
            'threshold': _int(constants.PARAM_THRESHOLD, constants.DEFAULT_THRESHOLD),
            'max_dimension': _int(constants.PARAM_MAX_DIMENSION,
                                  constants.DEFAULT_MAX_DIMENSION),
            'max_file_mb': _int(constants.PARAM_MAX_FILE_MB,
                                constants.DEFAULT_MAX_FILE_MB),
        }

    def get_threshold(self):
        return self.get_config()['threshold']

    def get_provider(self, config=None):
        from ..providers.base_provider import get_provider_class

        config = config or self.get_config()
        code = config.get('provider') or 'demo'
        provider_cls = get_provider_class(code)
        if not provider_cls:
            raise UserError(_(
                "The configured OCR provider '%s' is not available. "
                "Please check the Mulkiya OCR configuration.", code))
        return provider_cls(self.env, config)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def scan(self, front_image, back_image):
        """Run a full scan.

        :param front_image: base64 value of the front side
        :param back_image: base64 value of the back side
        :return: dict with ``fields``, ``matches``, ``raw``, ``provider``,
                 ``confidence``, ``warnings`` and ``duration``
        """
        from ..providers.base_provider import MulkiyaOCRError

        config = self.get_config()
        if not config['enabled']:
            raise UserError(_(
                "Mulkiya OCR is disabled. "
                "Please ask your administrator to enable it in the settings."))

        if not front_image:
            raise UserError(_("Please upload the front side of the Mulkiya."))
        if not back_image:
            raise UserError(_("Please upload the back side of the Mulkiya."))

        provider = self.get_provider(config)
        # A local engine works on the original pixels; a remote one gets a
        # compressed copy so the upload stays small.
        max_dimension = config['max_dimension']
        if getattr(provider, 'image_max_dimension', None) is not None:
            max_dimension = provider.image_max_dimension

        front = image_service.prepare(
            front_image, _("front"),
            max_dimension=max_dimension,
            max_file_mb=config['max_file_mb'])
        back = image_service.prepare(
            back_image, _("back"),
            max_dimension=max_dimension,
            max_file_mb=config['max_file_mb'])
        started = time.time()
        try:
            payload = provider.extract(front, back)
        except MulkiyaOCRError as exc:
            _logger.warning("Mulkiya OCR failed (provider=%s): %s",
                            provider.code, exc.technical)
            raise UserError(exc.message) from exc
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("Mulkiya OCR crashed (provider=%s)", provider.code)
            raise UserError(_(
                "Unable to process the Mulkiya.\n\n"
                "Please verify the image quality and try again.")) from exc
        duration = time.time() - started

        if not payload:
            raise UserError(_(
                "Unable to process the Mulkiya.\n\n"
                "Please verify the image quality and try again."))

        normalized = self.normalizer.normalize_payload(payload)
        matches = self.matcher.match_payload(normalized)
        warnings = self.build_warnings(normalized, matches, config['threshold'])
        warnings['quality'] = image_service.resolution_warning(
            front_image, back_image)

        return {
            'fields': normalized,
            'matches': matches,
            'raw': provider.raw_response,
            'provider': provider.code,
            'simulated': getattr(provider, 'is_simulation', False),
            'threshold': config['threshold'],
            'confidence': self.average_confidence(normalized),
            'warnings': warnings,
            'duration': round(duration, 2),
        }

    # ------------------------------------------------------------------
    @staticmethod
    def average_confidence(normalized):
        scores = [entry.get('confidence') or 0 for entry in normalized.values()
                  if entry.get('value') not in (None, '', 0)]
        return int(round(sum(scores) / len(scores))) if scores else 0

    def build_warnings(self, normalized, matches, threshold):
        warnings = {'vin': [], 'confidence': [], 'unmatched': [], 'quality': None}

        vin = (normalized.get(constants.FIELD_VIN) or {}).get('value')
        warnings['vin'] += self.normalizer.check_vin(vin)
        engine_no = (normalized.get(constants.FIELD_ENGINE_NO) or {}).get('value')
        warnings['vin'] += self.normalizer.check_engine_no(engine_no)

        for key, entry in normalized.items():
            if entry.get('value') in (None, '', 0):
                continue
            confidence = entry.get('confidence') or 0
            if confidence and confidence < threshold:
                warnings['confidence'].append(constants.FIELD_LABELS.get(key, key))

        for key, match in (matches or {}).items():
            if match.get('model') and not match.get('matched') and \
                    (normalized.get(key) or {}).get('value'):
                warnings['unmatched'].append(constants.FIELD_LABELS.get(key, key))
        return warnings
