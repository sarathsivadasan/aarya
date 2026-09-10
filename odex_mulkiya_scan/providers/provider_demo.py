# -*- coding: utf-8 -*-
"""Offline demo provider.

Returns a deterministic Mulkiya payload without contacting any external
service. It exists so that the workflow, the views and the automated tests can
run on a machine that has no OCR credentials, and so a demo can be given
without spending API calls. It is never selected automatically in production
unless an administrator explicitly configures it.
"""

from .base_provider import MulkiyaOCRProvider, register_provider


@register_provider
class DemoMulkiyaProvider(MulkiyaOCRProvider):

    code = 'demo'
    label = 'Demo / Offline Simulation'
    sequence = 90
    requires_credentials = False
    is_simulation = True

    #: Overridable by tests through the provider config.
    SAMPLE = {
        'engine_no': {'value': 'YD25 123456T', 'confidence': 96},
        'vin_sn': {'value': 'JN6BE6DSXF9008830', 'confidence': 98},
        'license_plate': {'value': '8830', 'confidence': 99},
        'plate_code': {'value': '1', 'confidence': 99},
        'registration_emirate': {'value': 'ABU DHABI', 'confidence': 99},
        'make': {'value': 'NISSAN', 'confidence': 96},
        'model': {'value': 'NV350', 'confidence': 94},
        'model_year': {'value': '2014', 'confidence': 95},
        'color': {'value': 'WHITE', 'confidence': 91},
        'fuel_type': {'value': 'DIESEL', 'confidence': 98},
        'cylinder_count': {'value': '4', 'confidence': 97},
    }

    def extract(self, front_image, back_image):
        payload = self.config.get('demo_payload') or self.SAMPLE
        self.raw_response = {
            'provider': self.code,
            'note': 'Simulated response, no external call was made.',
            'payload': payload,
        }
        return {key: dict(entry) for key, entry in payload.items()}
