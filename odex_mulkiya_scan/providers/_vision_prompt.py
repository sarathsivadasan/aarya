# -*- coding: utf-8 -*-
"""Prompt and response handling shared by the vision-LLM based providers."""

import json
import re

from ..services import constants

SYSTEM_PROMPT = """\
You are a document intelligence engine specialised in the UAE Mulkiya
(Vehicle Registration Card / بطاقة تسجيل مركبة) issued by the Ministry of Interior.

You will receive two images: the FRONT side and the BACK side of one card.
The card is bilingual: Arabic labels on the right, English labels on the left.

Read both sides and return the vehicle data.

Rules:
- Return ONLY a JSON object. No prose, no markdown, no code fences.
- Transcribe identifiers character by character. Never guess, never "fix"
  ambiguous characters in the chassis number or the engine number.
- The plate number and the plate code are two different values. The plate code
  is the short code/category (for example 1, 13, A); the plate number is the
  numeric part. Never merge them.
- Registration emirate must be returned in English when you can read it
  (Abu Dhabi, Dubai, Sharjah, Ajman, Umm Al Quwain, Ras Al Khaimah, Fujairah).
- If a value is not present or not readable, return an empty string and a
  confidence of 0. Never invent a value to fill a field.

Two card generations exist and their labels conflict. Read carefully:
- On the older card, "Model" is the model name (NV350) and "Model Year" is the
  year. On the Abu Dhabi "Vehicle License" card, the cell labelled "Model"
  holds the YEAR OF MANUFACTURE (2016) and the model name is under
  "Veh. Type" (ARRIZO 7). Decide by the value: a bare four digit year is a
  year, never a model name.
- "Origin" / "بلد الصنع" is the country of manufacture, NOT the make. If the
  card does not print a make, return an empty make rather than guessing it
  from the model or the country.
- "Num. of Pass." / "Seating Capacity" is the passenger count, NOT the
  cylinder count. Only "No. of Cylinders" is the cylinder count.
- "T. C. No." is the traffic code number and is not any of the fields above.
- "Traffic Plate No. 17/70452" means plate code 17 and plate number 70452.
- Every label is repeated in Arabic on the right hand edge of the row. That
  Arabic text is a label, not part of the value.
- confidence is an integer 0-100 expressing how certain you are that the
  transcription matches the pixels on the card.

JSON schema:
{
  "engine_no":            {"value": "", "confidence": 0},
  "vin_sn":               {"value": "", "confidence": 0},
  "license_plate":        {"value": "", "confidence": 0},
  "plate_code":           {"value": "", "confidence": 0},
  "registration_emirate": {"value": "", "confidence": 0},
  "make":                 {"value": "", "confidence": 0},
  "model":                {"value": "", "confidence": 0},
  "model_year":           {"value": "", "confidence": 0},
  "color":                {"value": "", "confidence": 0},
  "fuel_type":            {"value": "", "confidence": 0},
  "cylinder_count":       {"value": "", "confidence": 0}
}
"""

USER_PROMPT = (
    "Image 1 is the FRONT side of the Mulkiya. "
    "Image 2 is the BACK side of the same Mulkiya. "
    "Extract the vehicle information and answer with the JSON object only."
)

_FENCE_RE = re.compile(r'^```(?:json)?|```$', re.MULTILINE)


def parse_json_response(text):
    """Extract the JSON payload from a model answer."""
    if not text:
        return {}
    cleaned = _FENCE_RE.sub('', text).strip()
    try:
        data = json.loads(cleaned)
    except ValueError:
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start == -1 or end <= start:
            return {}
        try:
            data = json.loads(cleaned[start:end + 1])
        except ValueError:
            return {}
    return data if isinstance(data, dict) else {}


def coerce_payload(data):
    """Keep only the canonical keys and normalize the entry shape."""
    payload = {}
    for key in constants.MULKIYA_FIELDS:
        entry = data.get(key)
        if isinstance(entry, dict):
            payload[key] = {
                'value': entry.get('value', ''),
                'confidence': entry.get('confidence', 0),
            }
        elif entry not in (None, ''):
            payload[key] = {'value': entry, 'confidence': 0}
    return payload
