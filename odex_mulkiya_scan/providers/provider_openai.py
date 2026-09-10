# -*- coding: utf-8 -*-
"""OpenAI compatible vision provider.

Works with the OpenAI chat completions API and with any gateway exposing the
same contract (Azure OpenAI, OpenRouter, Groq vision models, local vLLM),
which only requires changing the API URL and the model name in the settings.
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
class OpenAIMulkiyaProvider(MulkiyaOCRProvider):

    code = 'openai'
    label = 'OpenAI Compatible (Vision)'
    sequence = 20
    default_url = 'https://api.openai.com/v1/chat/completions'
    default_model = 'gpt-4o'

    def extract(self, front_image, back_image):
        if requests is None:  # pragma: no cover
            raise MulkiyaOCRError("The 'requests' python library is not installed.")
        self.check_credentials()

        content = [{'type': 'text', 'text': prompt.USER_PROMPT}]
        for label, image in (('Front side', front_image), ('Back side', back_image)):
            content.append({'type': 'text', 'text': label})
            content.append({
                'type': 'image_url',
                'image_url': {'url': self.data_url(image), 'detail': 'high'},
            })

        payload = {
            'model': self.api_model,
            'temperature': 0,
            'max_tokens': 2000,
            'response_format': {'type': 'json_object'},
            'messages': [
                {'role': 'system', 'content': prompt.SYSTEM_PROMPT},
                {'role': 'user', 'content': content},
            ],
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self.api_key,
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

        if response.status_code >= 400:
            raise MulkiyaOCRError(
                "Unable to process the Mulkiya. Please try again.",
                technical="HTTP %s: %s" % (response.status_code, response.text[:500]))

        body = response.json()
        self.raw_response = body
        try:
            text = body['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError) as exc:
            raise MulkiyaOCRError(
                "The OCR service returned an unexpected answer.",
                technical=str(body)[:500]) from exc

        data = prompt.parse_json_response(text)
        if not data:
            raise MulkiyaOCRQuality(
                "The image quality is insufficient. "
                "Please upload a clearer image of the Mulkiya.",
                technical="Unparseable model answer: %s" % str(text)[:500])
        return prompt.coerce_payload(data)
