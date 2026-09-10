# -*- coding: utf-8 -*-
"""Ollama provider - a vision model running on your own machine.

Same idea as the cloud vision providers, except the model runs on your
hardware and the images never leave the network. No API key, no per-scan cost.

Setup on the server::

    curl -fsSL https://ollama.com/install.sh | sh
    ollama pull qwen2.5vl:7b        # good Arabic + English document reading
    # or: ollama pull llama3.2-vision:11b

Then set the provider to Ollama and, if the model differs, put its name in
Model / Engine. A GPU is strongly recommended; on CPU a scan takes a while.
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
class OllamaMulkiyaProvider(MulkiyaOCRProvider):

    code = 'ollama'
    label = 'Ollama (Local Vision Model, No API)'
    sequence = 35
    requires_credentials = False
    default_url = 'http://localhost:11434/api/chat'
    default_model = 'qwen2.5vl:7b'

    def extract(self, front_image, back_image):
        if requests is None:  # pragma: no cover
            raise MulkiyaOCRError("The 'requests' python library is not installed.")

        payload = {
            'model': self.api_model,
            'stream': False,
            'format': 'json',
            'options': {'temperature': 0},
            'messages': [
                {'role': 'system', 'content': prompt.SYSTEM_PROMPT},
                {
                    'role': 'user',
                    'content': prompt.USER_PROMPT,
                    'images': [front_image[0], back_image[0]],
                },
            ],
        }

        try:
            response = requests.post(self.api_url, json=payload,
                                     timeout=self.timeout)
        except requests.Timeout as exc:
            raise MulkiyaOCRTimeout(
                "The local OCR model did not answer in time. A vision model on "
                "CPU can be slow: raise the timeout in the settings or use a "
                "smaller model.", technical=str(exc)) from exc
        except requests.RequestException as exc:
            raise MulkiyaOCRError(
                "The local OCR service is not reachable. Please check that "
                "Ollama is running on this server.",
                technical=str(exc)) from exc

        if response.status_code == 404:
            raise MulkiyaOCRError(
                "The model '%s' is not installed in Ollama. Please pull it "
                "first." % self.api_model,
                technical=response.text[:500])
        if response.status_code >= 400:
            raise MulkiyaOCRError(
                "Unable to process the Mulkiya. Please try again.",
                technical="HTTP %s: %s" % (response.status_code,
                                           response.text[:500]))

        body = response.json()
        self.raw_response = body
        text = ((body.get('message') or {}).get('content')
                or body.get('response') or '')
        data = prompt.parse_json_response(text)
        if not data:
            raise MulkiyaOCRQuality(
                "The local model could not read the Mulkiya.\n\n"
                "Please upload a clearer image, or try a larger vision model.",
                technical="Unparseable answer: %s" % str(text)[:500])
        return prompt.coerce_payload(data)
