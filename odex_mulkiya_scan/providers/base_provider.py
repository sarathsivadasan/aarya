# -*- coding: utf-8 -*-
"""OCR provider abstraction (section 15).

A provider receives two already validated and compressed images and returns a
payload in the canonical shape::

    {
        "engine_no": {"value": "YD25 123456T", "confidence": 96},
        "vin_sn":    {"value": "JN6BE6DSXF9008830", "confidence": 98},
        ...
    }

Anything else the provider wants to keep for the audit trail goes into
``self.raw_response``. Providers must never write to the database and must
never be given the user's session: all credentials stay server side.
"""

import logging

_logger = logging.getLogger(__name__)

#: code -> provider class
PROVIDER_REGISTRY = {}


def register_provider(cls):
    """Class decorator registering a provider under ``cls.code``."""
    if not getattr(cls, 'code', None):
        raise ValueError("An OCR provider must define a 'code'.")
    PROVIDER_REGISTRY[cls.code] = cls
    return cls


def get_provider_class(code):
    return PROVIDER_REGISTRY.get(code)


def provider_selection():
    """Selection list for the configuration screen."""
    return [(code, cls.label) for code, cls in sorted(
        PROVIDER_REGISTRY.items(), key=lambda item: item[1].sequence)]


class MulkiyaOCRError(Exception):
    """Base error raised by providers. Carries a user friendly message."""

    def __init__(self, message, technical=None):
        super().__init__(message)
        self.message = message
        self.technical = technical or message


class MulkiyaOCRTimeout(MulkiyaOCRError):
    """The provider did not answer in time."""


class MulkiyaOCRQuality(MulkiyaOCRError):
    """The provider answered but the document could not be read."""


class MulkiyaOCRProvider:
    """Interface every OCR provider must implement."""

    code = None
    label = None
    sequence = 100
    #: True when the provider returns per-field confidence scores.
    supports_confidence = True
    #: True when the provider needs an API key.
    requires_credentials = True
    #: True when the provider returns fabricated data instead of reading the
    #: document. Surfaced in the UI so a demo can never be mistaken for a scan.
    is_simulation = False

    def __init__(self, env, config):
        """:param config: read-only dict produced by ``ocr_service``."""
        self.env = env
        self.config = config
        self.raw_response = {}

    # ------------------------------------------------------------------
    def extract(self, front_image, back_image):
        """Extract the Mulkiya fields from both sides.

        :param front_image: tuple ``(base64_str, mimetype)``
        :param back_image: tuple ``(base64_str, mimetype)``
        :return: canonical payload dict
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Helpers shared by concrete providers
    # ------------------------------------------------------------------
    @property
    def timeout(self):
        return self.config.get('timeout') or 90

    @property
    def api_key(self):
        return self.config.get('api_key') or ''

    @property
    def api_secret(self):
        return self.config.get('api_secret') or ''

    @property
    def api_url(self):
        return self.config.get('api_url') or self.default_url

    @property
    def api_model(self):
        return self.config.get('api_model') or self.default_model

    default_url = ''
    default_model = ''

    def check_credentials(self):
        if self.requires_credentials and not self.api_key:
            raise MulkiyaOCRError(
                "The OCR service is not configured. "
                "Please ask your administrator to set the API credentials.",
                technical="Missing API key for provider %s" % self.code)

    @staticmethod
    def data_url(image):
        base64_str, mimetype = image
        return "data:%s;base64,%s" % (mimetype, base64_str)
