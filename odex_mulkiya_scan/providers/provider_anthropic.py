# -*- coding: utf-8 -*-
"""Anthropic Claude vision provider.

Handles bilingual Arabic/English cards natively and returns per-field
confidence, which makes it the default recommendation for the Mulkiya.
"""

import logging

from . import _vision_prompt as prompt
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
class AnthropicMulkiyaProvider(MulkiyaOCRProvider):

    code = 'anthropic'
    label = 'Anthropic Claude (Vision)'
    sequence = 10
    default_url = 'https://api.anthropic.com/v1/messages'
    default_model = 'claude-sonnet-4-5'

    def extract(self, front_image, back_image):
        if requests is None:  # pragma: no cover
            raise MulkiyaOCRError("The 'requests' python library is not installed.")
        self.check_credentials()

        content = []
        for label, image in (('Front side', front_image), ('Back side', back_image)):
            base64_str, mimetype = image
            content.append({'type': 'text', 'text': label})
            content.append({
                'type': 'image',
                'source': {
                    'type': 'base64',
                    'media_type': mimetype,
                    'data': base64_str,
                },
            })
        content.append({'type': 'text', 'text': prompt.USER_PROMPT})

        payload = {
            'model': self.api_model,
            'max_tokens': 2000,
            'temperature': 0,
            'system': prompt.SYSTEM_PROMPT,
            'messages': [{'role': 'user', 'content': content}],
        }
        headers = {
            'content-type': 'application/json',
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload,
                                     timeout=self.timeout)
        except requests.Timeout as exc:
            raise MulkiyaOCRTimeout(
                "The OCR service did not respond in time. Please try again.",
                technical=str(exc)) from exc
        except requests.RequestException as exc:
            raise MulkiyaOCRError(
                "The OCR service is currently unavailable. Please try again.",
                technical=str(exc)) from exc

        if response.status_code == 401:
            raise MulkiyaOCRError(
                "The OCR service rejected the credentials. "
                "Please ask your administrator to check the configuration.",
                technical=response.text[:500])
        if response.status_code == 429:
            raise MulkiyaOCRError(
                "The OCR service is busy. Please try again in a moment.",
                technical=response.text[:500])
        if response.status_code >= 400:
            raise MulkiyaOCRError(
                "Unable to process the Mulkiya. Please try again.",
                technical="HTTP %s: %s" % (response.status_code, response.text[:500]))

        body = response.json()
        self.raw_response = body

        text = ''.join(
            block.get('text', '')
            for block in body.get('content', [])
            if block.get('type') == 'text'
        )
        data = prompt.parse_json_response(text)
        if not data:
            raise MulkiyaOCRQuality(
                "The image quality is insufficient. "
                "Please upload a clearer image of the Mulkiya.",
                technical="Unparseable model answer: %s" % text[:500])
        return prompt.coerce_payload(data)
