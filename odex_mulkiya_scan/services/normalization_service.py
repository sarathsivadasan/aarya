# -*- coding: utf-8 -*-
"""Normalization of raw OCR output (sections 27 and 28).

The rules here are deliberately conservative for identity fields: a VIN or an
engine number is *never* silently corrected, it is only cleaned of formatting
noise and flagged when it looks suspicious.
"""

import logging
import re
import unicodedata

from . import constants

_logger = logging.getLogger(__name__)

#: Arabic-Indic and Extended Arabic-Indic digits.
_ARABIC_DIGITS = {
    '\u0660': '0', '\u0661': '1', '\u0662': '2', '\u0663': '3', '\u0664': '4',
    '\u0665': '5', '\u0666': '6', '\u0667': '7', '\u0668': '8', '\u0669': '9',
    '\u06f0': '0', '\u06f1': '1', '\u06f2': '2', '\u06f3': '3', '\u06f4': '4',
    '\u06f5': '5', '\u06f6': '6', '\u06f7': '7', '\u06f8': '8', '\u06f9': '9',
}

#: Characters that never appear in a VIN (ISO 3779).
VIN_FORBIDDEN = set('IOQ')
VIN_RE = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$')

#: Labels that OCR sometimes glues to the value.
_LABEL_NOISE = re.compile(
    r'^(?:chassis|engine|motor|plate|vin|no|number|#|:|\.|\-|/|\s)+',
    re.IGNORECASE)


def strip_arabic_digits(value):
    return ''.join(_ARABIC_DIGITS.get(ch, ch) for ch in value)


def basic_clean(value):
    """Trim, collapse whitespace, drop control characters and BiDi marks."""
    if value is None:
        return ''
    value = str(value)
    value = ''.join(
        ch for ch in value
        if unicodedata.category(ch) not in ('Cc', 'Cf') or ch in ('\n', '\t')
    )
    value = value.replace('\u00a0', ' ').replace('\t', ' ').replace('\n', ' ')
    value = re.sub(r'\s+', ' ', value).strip()
    value = value.strip(' :;,|')
    return value


def titlecase(value):
    """Title-case a value while preserving intentional internal capitals."""
    if not value:
        return value
    parts = []
    for word in value.split(' '):
        if not word:
            continue
        if word.isupper() and len(word) <= 4 and any(c.isdigit() for c in word):
            parts.append(word)          # e.g. NV350, GT-R trims
        elif re.search(r'\d', word):
            parts.append(word.upper())
        elif '-' in word:
            parts.append('-'.join(p.capitalize() for p in word.split('-')))
        else:
            parts.append(word.capitalize())
    return ' '.join(parts)


class NormalizationService:
    """Turn raw provider values into normalized, comparable values."""

    def __init__(self, env):
        self.env = env
        self._alias_cache = None

    # ------------------------------------------------------------------
    # Alias table
    # ------------------------------------------------------------------
    def _aliases(self):
        """Return ``{(field_key, normalized_source): target}``."""
        if self._alias_cache is None:
            cache = {}
            aliases = self.env['odex.mulkiya.alias'].sudo().search([])
            for alias in aliases:
                key = self.alias_key(alias.source_value)
                if not key:
                    continue
                cache[(alias.field_key or False, key)] = alias.target_value
            self._alias_cache = cache
        return self._alias_cache

    @staticmethod
    def alias_key(value):
        """Comparison key: lowercase, no punctuation, no diacritics."""
        value = basic_clean(value or '')
        value = strip_arabic_digits(value)
        value = unicodedata.normalize('NFKD', value)
        value = ''.join(ch for ch in value if not unicodedata.combining(ch))
        value = re.sub(r'[^0-9A-Za-z\u0600-\u06ff]+', '', value)
        return value.lower()

    def apply_alias(self, field_key, value):
        """Resolve an alias for ``value``; falls back to the value itself."""
        key = self.alias_key(value)
        if not key:
            return value
        aliases = self._aliases()
        return aliases.get((field_key, key)) or aliases.get((False, key)) or value

    # ------------------------------------------------------------------
    # Field level normalization
    # ------------------------------------------------------------------
    def normalize_identifier(self, value):
        """Engine number / VIN: uppercase, no separators, no label noise."""
        value = basic_clean(value)
        value = _LABEL_NOISE.sub('', value)
        value = strip_arabic_digits(value)
        value = re.sub(r'[^0-9A-Za-z ]+', '', value)
        value = re.sub(r'\s+', ' ', value).strip()
        return value.upper()

    def normalize_vin(self, value):
        value = self.normalize_identifier(value).replace(' ', '')
        return value

    def normalize_plate(self, value):
        """Plate *number* only. The plate code is a separate field."""
        value = basic_clean(value)
        value = strip_arabic_digits(value)
        value = re.sub(r'[^0-9A-Za-z]+', '', value)
        value = value.upper()
        # A Mulkiya plate number is numeric; drop a leading code if OCR glued
        # something like "1 08830" together is handled by the parser, not here.
        if value.isdigit():
            value = value.lstrip('0') or '0'
        return value

    def normalize_plate_code(self, value):
        value = basic_clean(value)
        value = strip_arabic_digits(value)
        value = re.sub(r'[^0-9A-Za-z]+', '', value).upper()
        return value

    def normalize_year(self, value):
        value = strip_arabic_digits(basic_clean(value))
        match = re.search(r'(19|20)\d{2}', value)
        return match.group(0) if match else ''

    def normalize_integer(self, value):
        value = strip_arabic_digits(basic_clean(value))
        match = re.search(r'\d+', value)
        return int(match.group(0)) if match else 0

    def normalize_name(self, field_key, value):
        """Make / model / colour / emirate / fuel type."""
        value = basic_clean(value)
        value = strip_arabic_digits(value)
        value = re.sub(r'\s*[/|]\s*', ' / ', value)
        value = self.apply_alias(field_key, value)
        if re.search(r'[\u0600-\u06ff]', value):
            # Still Arabic: no alias found, keep the raw value for the user.
            return value
        return titlecase(value)

    # ------------------------------------------------------------------
    # VIN sanity checking (section 28) - flag, never auto-correct
    # ------------------------------------------------------------------
    def check_vin(self, vin):
        """Return a list of human readable warnings for a VIN value."""
        warnings = []
        if not vin:
            return ['The chassis number could not be read. Please enter it manually.']
        if len(vin) != 17:
            warnings.append(
                'The chassis number has %s characters instead of 17. '
                'Please verify it against the document.' % len(vin))
        forbidden = sorted(VIN_FORBIDDEN & set(vin))
        if forbidden:
            warnings.append(
                'The chassis number contains %s, which never appears in a VIN and '
                'is usually confused with 1, 0 or 9. Please verify it.'
                % ', '.join(forbidden))
        if len(vin) == 17 and not VIN_RE.match(vin):
            warnings.append('The chassis number contains unexpected characters. '
                            'Please verify it.')
        return warnings

    def check_engine_no(self, engine_no):
        if not engine_no:
            return ['The engine number could not be read. Please enter it manually.']
        if len(engine_no.replace(' ', '')) < 5:
            return ['The engine number looks too short. Please verify it.']
        return []

    # ------------------------------------------------------------------
    # Whole payload
    # ------------------------------------------------------------------
    def normalize_payload(self, payload):
        """Normalize a ``{field_key: {'value':.., 'confidence':..}}`` payload."""
        result = {}
        for key in constants.MULKIYA_FIELDS:
            entry = payload.get(key) or {}
            if not isinstance(entry, dict):
                entry = {'value': entry}
            raw = entry.get('value')
            confidence = entry.get('confidence')
            value = self.normalize_field(key, raw)
            result[key] = {
                'value': value,
                'raw_value': basic_clean(raw),
                'confidence': self._clamp_confidence(confidence),
            }
        return result

    def normalize_field(self, key, raw):
        if key == constants.FIELD_VIN:
            return self.normalize_vin(raw)
        if key == constants.FIELD_ENGINE_NO:
            return self.normalize_identifier(raw)
        if key == constants.FIELD_PLATE:
            return self.normalize_plate(raw)
        if key == constants.FIELD_PLATE_CODE:
            return self.normalize_plate_code(raw)
        if key == constants.FIELD_MODEL_YEAR:
            return self.normalize_year(raw)
        if key == constants.FIELD_CYLINDERS:
            return self.normalize_integer(raw)
        return self.normalize_name(key, raw)

    @staticmethod
    def _clamp_confidence(confidence):
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            return 0
        if confidence <= 1.0:
            confidence *= 100.0
        return int(max(0, min(100, round(confidence))))
