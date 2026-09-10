# -*- coding: utf-8 -*-
"""Optional matching of normalized OCR values against Odoo master data.

The application is standalone: every target model is looked up defensively and
silently skipped when it is not installed. Master records are **never** created
automatically (section 20).
"""

import logging

from odoo.tools.safe_eval import safe_eval

from . import constants
from .normalization_service import NormalizationService

_logger = logging.getLogger(__name__)


class MatchingService:

    def __init__(self, env, normalizer=None):
        self.env = env
        self.normalizer = normalizer or NormalizationService(env)
        self._rules = None

    # ------------------------------------------------------------------
    def _rule_map(self):
        if self._rules is None:
            rules = self.env['odex.mulkiya.match.rule'].sudo().search([])
            mapping = {}
            for rule in rules:
                mapping.setdefault(rule.field_key, []).append(rule)
            self._rules = mapping
        return self._rules

    def _model_available(self, model_name):
        """True when the model exists *and* its table is present."""
        if not model_name or model_name not in self.env:
            return False
        model = self.env[model_name].sudo()
        if model._abstract or model._transient:
            return False
        try:
            self.env.cr.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (model._table,))
            return bool(self.env.cr.fetchone())
        except Exception:  # pragma: no cover - defensive
            return False

    # ------------------------------------------------------------------
    def match_field(self, field_key, value, context_matches=None):
        """Match a single normalized value.

        :return: dict with ``value``, ``matched``, ``model``, ``record_id`` and
                 ``record_name`` (section 21).
        """
        result = {
            'value': value,
            'matched': False,
            'model': False,
            'record_id': False,
            'record_name': False,
        }
        if value in (None, '', 0):
            return result

        for rule in self._rule_map().get(field_key, []):
            if not self._model_available(rule.model_name):
                continue
            result['model'] = rule.model_name
            record = self._search(rule, value, context_matches or {})
            if record:
                result.update({
                    'matched': True,
                    'record_id': record.id,
                    'record_name': self._display(record, rule),
                })
                return result
        return result

    def _display(self, record, rule):
        try:
            value = record[rule.search_field or 'name']
            return value if isinstance(value, str) else record.display_name
        except Exception:  # pragma: no cover - defensive
            return record.display_name

    def _search(self, rule, value, context_matches):
        model = self.env[rule.model_name].sudo()
        field_name = rule.search_field or 'name'
        if field_name not in model._fields:
            _logger.warning("Mulkiya matching: %s has no field %s",
                            rule.model_name, field_name)
            return model.browse()

        domain = []
        if rule.extra_domain:
            try:
                domain += safe_eval(rule.extra_domain, {'value': value})
            except Exception:  # pragma: no cover - user configuration error
                _logger.warning("Mulkiya matching: invalid domain on rule %s",
                                rule.display_name, exc_info=True)

        # Restrict by an already matched parent (model restricted by brand).
        if rule.parent_field_key and rule.parent_relation_field:
            parent = context_matches.get(rule.parent_field_key) or {}
            parent_id = parent.get('record_id')
            if parent_id and rule.parent_relation_field in model._fields:
                domain = domain + [(rule.parent_relation_field, '=', parent_id)]
            elif rule.parent_required:
                return model.browse()

        candidates = [value]
        alias = self.normalizer.apply_alias(rule.field_key, value)
        if alias and alias != value:
            candidates.append(alias)

        # 1. exact (case insensitive), 2. exact ignoring punctuation, 3. ilike
        for candidate in candidates:
            record = model.search(domain + [(field_name, '=ilike', candidate)],
                                  limit=1)
            if record:
                return record

        target_key = self.normalizer.alias_key(value)
        if target_key:
            records = model.search(domain, limit=500)
            for record in records:
                if self.normalizer.alias_key(record[field_name] or '') == target_key:
                    return record

        for candidate in candidates:
            if len(candidate) < 3:
                continue
            record = model.search(domain + [(field_name, 'ilike', candidate)],
                                  limit=1)
            if record:
                return record
        return model.browse()

    # ------------------------------------------------------------------
    def match_payload(self, payload):
        """Match a full normalized payload, honouring parent dependencies."""
        matches = {}
        ordered = sorted(
            constants.MULKIYA_FIELDS,
            key=lambda key: 1 if self._has_parent(key) else 0)
        for key in ordered:
            entry = payload.get(key) or {}
            matches[key] = self.match_field(key, entry.get('value'), matches)
        return matches

    def _has_parent(self, field_key):
        return any(rule.parent_field_key
                   for rule in self._rule_map().get(field_key, []))
