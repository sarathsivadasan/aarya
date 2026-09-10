# -*- coding: utf-8 -*-
"""Google Cloud Vision provider (classic OCR + label parsing).

Vision returns text and per-word confidence, not structured fields, so the raw
text of each side goes through ``services.document_parser`` and the field
confidence is derived from the confidence of the words that produced it.
"""

import logging

from ..services import document_parser
from .base_provider import (
    MulkiyaOCRError,
    MulkiyaOCRProvider,
    MulkiyaOCRQuality,
    MulkiyaOCRTimeout,
    register_provider,
)

_logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


@register_provider
class GoogleVisionMulkiyaProvider(MulkiyaOCRProvider):

    code = 'google_vision'
    label = 'Google Cloud Vision'
    sequence = 30
    default_url = 'https://vision.googleapis.com/v1/images:annotate'

    def extract(self, front_image, back_image):
        if requests is None:  # pragma: no cover
            raise MulkiyaOCRError("The 'requests' python library is not installed.")
        self.check_credentials()

        requests_payload = {
            'requests': [
                self._image_request(front_image),
                self._image_request(back_image),
            ]
        }
        url = '%s?key=%s' % (self.api_url, self.api_key)

        try:
            response = requests.post(url, json=requests_payload, timeout=self.timeout)
        except requests.Timeout as exc:
            raise MulkiyaOCRTimeout(
                "The OCR service did not respond in time. Please try again.",
                technical=str(exc)) from exc
        except requests.RequestException as exc:
            raise MulkiyaOCRError(
                "The OCR service is currently unavailable. Please try again.",
                technical=str(exc)) from exc

        if response.status_code >= 400:
            raise MulkiyaOCRError(
                "Unable to process the Mulkiya. Please try again.",
                technical="HTTP %s: %s" % (response.status_code, response.text[:500]))

        body = response.json()
        self.raw_response = body
        responses = body.get('responses') or []
        if len(responses) < 2:
            raise MulkiyaOCRQuality(
                "Unable to process the Mulkiya. "
                "Please verify the image quality and try again.",
                technical=str(body)[:500])

        front_text, front_conf = self._read(responses[0])
        back_text, back_conf = self._read(responses[1])
        if not front_text and not back_text:
            raise MulkiyaOCRQuality(
                "No text could be read from the images. "
                "Please upload clearer pictures of the Mulkiya.")

        merged = document_parser.merge_sides(
            document_parser.parse_text(front_text, side='front'),
            document_parser.parse_text(back_text, side='back'),
        )
        page_confidence = int(round(max(front_conf, back_conf) * 100))
        for entry in merged.values():
            entry.setdefault('confidence', page_confidence)
        return merged

    def _image_request(self, image):
        base64_str, _mimetype = image
        return {
            'image': {'content': base64_str},
            'features': [{'type': 'DOCUMENT_TEXT_DETECTION'}],
            'imageContext': {'languageHints': ['en', 'ar']},
        }

    @staticmethod
    def _read(response):
        if response.get('error'):
            raise MulkiyaOCRError(
                "Unable to process the Mulkiya. Please try again.",
                technical=str(response['error'])[:500])
        annotation = response.get('fullTextAnnotation') or {}
        text = annotation.get('text') or ''
        pages = annotation.get('pages') or []
        confidences = [page.get('confidence') for page in pages
                       if page.get('confidence')]
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return text, confidence
