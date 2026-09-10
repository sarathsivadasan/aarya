# -*- coding: utf-8 -*-
"""Label driven parsing of raw Mulkiya OCR text.

Providers that return plain text (classic OCR engines such as Google Vision,
Tesseract, Azure Read) hand their output to this parser, which understands the
layout of the UAE Vehicle Registration Card in both English and Arabic.

Providers that already return structured JSON (vision LLMs) bypass it.
"""

import difflib
import re

from . import constants
from .normalization_service import strip_arabic_digits

#: label -> canonical key. Matching is done on a squashed lowercase form so
#: "Engine No.", "ENGINE NUMBER" and "Engine  #" all hit the same entry.
LABELS = {
    constants.FIELD_ENGINE_NO: [
        'engine no', 'engine number', 'engine', 'engine #', 'motor number',
        'motor no', 'eng no', 'eng number',
        'رقم المحرك', 'المحرك',
    ],
    constants.FIELD_VIN: [
        'chassis no', 'chassis number', 'chassis', 'vin',
        'vehicle identification number', 'chasis no', 'chasis number',
        'رقم الهيكل', 'الهيكل',
        'رقم القاعدة', 'القاعدة',
    ],
    constants.FIELD_PLATE: [
        'plate no', 'plate number', 'traffic plate no', 'traffic plate number',
        'رقم اللوحة', 'اللوحة',
    ],
    constants.FIELD_PLATE_CODE: [
        'plate code', 'plate class', 'plate category', 'رمز اللوحة',
    ],
    constants.FIELD_EMIRATE: [
        'place of issue', 'emirate', 'registration emirate', 'issued at',
        'الامارة', 'الإمارة', 'مكان الاصدار',
        'جهة الترخيص',
    ],
    constants.FIELD_MAKE: [
        'vehicle make', 'make', 'manufacturer', 'brand', 'الماركة',
    ],
    constants.FIELD_MODEL: [
        'model', 'vehicle model', 'الموديل', 'الطراز',
    ],
    constants.FIELD_MODEL_YEAR: [
        'model year', 'year of manufacture', 'year', 'سنة الصنع', 'الموديل سنة',
    ],
    constants.FIELD_COLOR: [
        'color', 'colour', 'vehicle color', 'vehicle colour', 'color of vehicle',
        'اللون', 'لون المركبة',
    ],
    constants.FIELD_FUEL_TYPE: [
        'fuel type', 'fuel', 'نوع الوقود', 'الوقود',
    ],
    constants.FIELD_CYLINDERS: [
        'no of cylinders', 'number of cylinders', 'cylinders', 'cyl',
        'عدد الاسطوانات', 'الاسطوانات',
    ],
}

#: Body/vehicle type. Not a canonical output field, but it carries the model
#: name on the Abu Dhabi "Vehicle License" layout, where the cell labelled
#: "Model" holds the year of manufacture instead.
KEY_VEHICLE_TYPE = '_vehicle_type'

LABELS[KEY_VEHICLE_TYPE] = [
    'veh type', 'vehicle type', 'veh. type', 'type of vehicle',
    '\u0646\u0648\u0639 \u0627\u0644\u0645\u0631\u0643\u0628\u0629', '\u0635\u0646\u0641 \u0627\u0644\u0645\u0631\u0643\u0628\u0629',
]

KEY_IGNORE = '_ignore'

#: Recognised but discarded: knowing these are labels is what stops their
#: values leaking into the neighbouring cell on a two-column row.
LABELS[KEY_IGNORE] = [
    'num of pass', 'number of passengers', 'no of pass', 'passengers',
    't c no', 'tc no', 'traffic code no', 'origin', 'country of origin',
    'g v w', 'gvw', 'gross weight', 'empty weight', 'payload',
    'seating capacity', 'standing capacity', 'reg date', 'registration date',
    'exp date', 'expiry date', 'ins exp', 'insurance expiry', 'policy no',
    'owner', 'nationality', 'mortgage by', 'licensing authority',
    '\u0639\u062f\u062f \u0627\u0644\u0631\u0643\u0627\u0628', '\u0628\u0644\u062f \u0627\u0644\u0635\u0646\u0639', '\u0627\u0644\u0631\u0645\u0632 \u0627\u0644\u0645\u0631\u0648\u0631\u064a',
    '\u0627\u0644\u0648\u0632\u0646 \u0627\u0644\u0627\u062c\u0645\u0627\u0644\u064a', '\u0627\u0644\u0648\u0632\u0646 \u0627\u0644\u0641\u0627\u0631\u063a', '\u0627\u0644\u062c\u0646\u0633\u064a\u0629', '\u0627\u0644\u0645\u0627\u0644\u0643',
    '\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u062a\u0631\u062e\u064a\u0635', '\u0627\u0646\u062a\u0647\u0627\u0621 \u0627\u0644\u062a\u0631\u062e\u064a\u0635', '\u0627\u0646\u062a\u0647\u0627\u0621 \u0627\u0644\u062a\u0623\u0645\u064a\u0646',
]

#: Labels that must not be swallowed as a value of the previous label.
ALL_LABEL_TOKENS = sorted(
    {lbl for labels in LABELS.values() for lbl in labels},
    key=len, reverse=True)

_SQUASH_RE = re.compile(r'[^0-9a-z\u0600-\u06ff]+')
_VIN_STRICT_RE = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$')
_VIN_LOOSE_RE = re.compile(r'^[A-Z0-9]{16,18}$')


def squash(text):
    return _SQUASH_RE.sub(' ', (text or '').lower()).strip()


_ALNUM_RE = re.compile(r'[0-9A-Za-z\u0600-\u06ff]')


def _is_separator(char):
    return not _ALNUM_RE.match(char)


def _consume_label(fragment, token):
    """Strip ``token`` from the start of ``fragment``, ignoring separators.

    Returns the remainder of the fragment, or None when the fragment does not
    start with that label.
    """
    ti = fi = 0
    while ti < len(token) and fi < len(fragment):
        expected = token[ti]
        char = fragment[fi]
        if expected == ' ':
            if _is_separator(char):
                fi += 1
                continue
            ti += 1
            continue
        if _is_separator(char):
            fi += 1
            continue
        if char.lower() == expected:
            ti += 1
            fi += 1
            continue
        return None
    if token[ti:].strip():
        return None
    return fragment[fi:]


def _label_for(fragment):
    """Return ``(canonical_key, remainder)`` when a fragment starts with a label."""
    if not squash(fragment):
        return None, fragment
    best_key = None
    best_len = 0
    best_remainder = fragment
    for key, labels in LABELS.items():
        for label in labels:
            token = squash(label)
            if not token:
                continue
            remainder = _consume_label(fragment, token)
            if remainder is None:
                continue
            # The label must be followed by a separator or the end of the
            # fragment, otherwise "Model" would match inside "Modello".
            if remainder and not _is_separator(remainder[0]):
                continue
            if len(token) > best_len:
                best_key, best_len, best_remainder = key, len(token), remainder
    if not best_key:
        return _fuzzy_label_for(fragment)
    return best_key, best_remainder.lstrip(' :.\u061b\u060c-|/')


#: squashed label -> canonical key, built once for fuzzy lookups.
_SQUASHED_LABELS = {}


def _squashed_labels():
    if not _SQUASHED_LABELS:
        for key, labels in LABELS.items():
            for label in labels:
                token = squash(label)
                if token:
                    _SQUASHED_LABELS.setdefault(token, key)
    return _SQUASHED_LABELS


def _fuzzy_label_for(fragment):
    """Recognise a label that OCR misread, e.g. "Chasis Ne." for "Chassis No.".

    Only applied to short fragments: a long fragment is a value, and mistaking
    a value for a label would silently discard data.
    """
    squashed = squash(fragment)
    if not squashed or len(squashed) > 24:
        return None, fragment
    labels = _squashed_labels()
    # Compare against the leading words only, so "chasis ne LVVDC..." still
    # matches on its label part.
    for width in (4, 3, 2, 1):
        head = ' '.join(squashed.split(' ')[:width])
        if len(head) < 4:
            continue
        matches = difflib.get_close_matches(head, list(labels), n=1, cutoff=0.82)
        if matches:
            key = labels[matches[0]]
            consumed = _consume_label(fragment, head)
            remainder = consumed if consumed is not None else ''
            return key, remainder.lstrip(' :.\u061b\u060c-|/')
    return None, fragment


_ARABIC_RE = re.compile(r'[\u0600-\u06ff]')
_LATIN_RE = re.compile(r'[A-Za-z0-9]')


def _drop_arabic_tail(value):
    """Remove the Arabic label printed to the right of a Latin value.

    These cards repeat every label in Arabic on the right-hand edge of the row.
    When the value itself is Latin, any Arabic tail is that label, not data.
    Values that are Arabic throughout are left untouched.
    """
    words = [word for word in value.split(' ') if word]
    if not any(_LATIN_RE.search(word) for word in words):
        return value

    def _is_arabic(word):
        return bool(_ARABIC_RE.search(word)) and not _LATIN_RE.search(word)

    arabic_positions = [i for i, word in enumerate(words) if _is_arabic(word)]
    if not arabic_positions:
        return value
    cut = arabic_positions[0]
    # A trailing Arabic label may carry its own digits, as in "ARRIZO 7 <ar> 7".
    tail = words[cut:]
    if not all(_is_arabic(word) or word.isdigit() for word in tail):
        return value
    head = ' '.join(words[:cut]).strip()
    return head if _LATIN_RE.search(head) else value


def _clean_value(value):
    """Trim a value and cut it where the next label starts."""
    value = (value or '').strip().strip(':.-|/ []{}()*#~\u2014\u2013_')
    value = _drop_arabic_tail(value)
    words = [word for word in value.split(' ') if word]
    for index in range(1, len(words)):
        key, _remainder = _label_for(' '.join(words[index:]))
        if key:
            value = ' '.join(words[:index])
            break
    return value.strip().strip(':.-|/ []{}()*#~\u2014\u2013_')


def _strip_leading_labels(remainder):
    """Drop repeated labels, e.g. the Arabic label followed by the English one."""
    for _attempt in range(4):
        key, stripped = _label_for(remainder)
        if not key or stripped == remainder:
            break
        remainder = stripped
    return remainder


def parse_text(text, side=None):
    """Parse a raw OCR text block into ``{field_key: {'value':..}}``.

    The parser is row oriented: on a Mulkiya each row is ``label | value``,
    frequently with the Arabic label repeated on the right hand side and
    sometimes with several cells on the same row (plate number, emirate, code).
    """
    result = {}
    if not text:
        return result

    lines = [ln.strip() for ln in re.split(r'[\r\n]+', text) if ln.strip()]
    pending_key = None

    for line in lines:
        fragments = [f for f in re.split(r'\s{2,}|\||\t', line) if f.strip()] or [line]
        current_key = pending_key
        buffer = []
        pending_key = None
        stored_on_line = False

        for index, fragment in enumerate(fragments):
            key, remainder = _label_for(fragment)
            if key:
                remainder = _strip_leading_labels(remainder)
                is_last = index == len(fragments) - 1
                if is_last and not remainder.strip() and stored_on_line:
                    # Right-hand mirror of a label already handled on this row.
                    continue
                if _store(result, current_key, buffer):
                    stored_on_line = True
                current_key = key
                buffer = [remainder] if remainder.strip() else []
            elif current_key:
                buffer.append(fragment)

        if current_key and buffer:
            _store(result, current_key, buffer)
        elif current_key:
            # Label alone on its row: its value is on the next row.
            pending_key = current_key

    _post_process(result, text)
    _reconcile(result)
    return result


def _store(result, key, buffer):
    """Store one label/value pair. Returns True when something was kept."""
    if not key or not buffer:
        return False
    value = _clean_value(' '.join(part.strip() for part in buffer if part.strip()))
    if not value:
        return False
    if key == KEY_IGNORE:
        return True
    result.setdefault(key, {'value': value})
    return True


def _find_vin(text):
    """Find a chassis number among the OCR tokens.

    A strict ISO 3779 match wins. Failing that a looser 16-18 character block
    mixing letters and digits is accepted, because a single misread character
    should not lose the whole value: it is flagged for verification later
    rather than silently dropped.
    """
    tokens = re.split(r'[^0-9A-Za-z]+', text.upper())
    loose = None
    for token in tokens:
        if _VIN_STRICT_RE.match(token):
            return token
        if loose is None and _VIN_LOOSE_RE.match(token) and \
                any(char.isdigit() for char in token) and \
                any(char.isalpha() for char in token):
            loose = token
    return loose


def _best_identifier(value):
    """Pick the real identifier out of a cell polluted by OCR noise.

    A row like ``Eng. No.  SQRE4G16AAFM54611  Soult aa,`` leaves the garbled
    remains of the Arabic label glued to the value. The identifier is the
    longest token mixing letters and digits, which is unambiguous here.
    """
    tokens = [token for token in re.split(r'[^0-9A-Za-z]+', value or '') if token]
    if len(tokens) <= 1:
        return value
    scored = [token for token in tokens
              if any(char.isdigit() for char in token) and len(token) >= 5]
    if not scored:
        return value
    return max(scored, key=len)


def _clean_designation(value):
    """Keep only the printed designation from a noisy cell.

    Values are printed in capitals; the debris OCR adds around them is mixed
    case. "= ARRIZOT Soe 7oyd Ras4 y" keeps "ARRIZOT", which the user can
    correct in one keystroke instead of retyping the row.
    """
    tokens = [token for token in re.split(r'[^0-9A-Za-z]+', value or '') if token]
    if len(tokens) <= 2:
        return value
    kept = [token for token in tokens
            if (token.isupper() and len(token) >= 3) or token.isdigit()]
    return ' '.join(kept) if kept else value


def _recover_from_vocabulary(result, text, key, vocabulary):
    """Find a value whose label OCR destroyed, using a closed word list."""
    if key in result:
        return
    upper = text.upper()
    for word in vocabulary:
        if re.search(r'(?<![A-Z])%s(?![A-Z])' % re.escape(word), upper):
            result[key] = {'value': word}
            return


def _looks_like_identifier(token):
    """True for VIN/engine style blocks, which are never a model name."""
    return (len(token) >= 10 and any(c.isdigit() for c in token)
            and any(c.isalpha() for c in token))


def _recover_model(result, text):
    """Recover a model designation from a row whose label was unreadable.

    Scoped tightly: short line, mostly capitals, not a colour, country or any
    of the card's own furniture. Anything found this way is still presented
    for verification like every other field.
    """
    if constants.FIELD_MODEL in result:
        return
    excluded = set(constants.COLOR_VOCABULARY) | set(constants.COUNTRY_VOCABULARY) \
        | set(constants.NOISE_VOCABULARY) | set(constants.FUEL_VOCABULARY)
    best = None
    for line in re.split(r'[\r\n]+', text):
        tokens = [token for token in re.split(r'[^0-9A-Za-z]+', line) if token]
        # Drop leading OCR noise such as "nee" or "i" before the value.
        while tokens and (len(tokens[0]) < 3 or tokens[0].islower()):
            tokens.pop(0)
        if not tokens or len(tokens) > 3:
            continue
        if any(token.upper() in excluded for token in tokens):
            continue
        if any(_looks_like_identifier(token) for token in tokens):
            # The chassis and engine rows are not model designations.
            continue
        taken = {str((result.get(key) or {}).get('value', '')).upper()
                 for key in (constants.FIELD_VIN, constants.FIELD_ENGINE_NO,
                             constants.FIELD_PLATE)}
        if any(token.upper() in taken for token in tokens):
            continue
        letters = [token for token in tokens if any(c.isalpha() for c in token)]
        if not letters or max(len(token) for token in letters) < 4:
            # Short fragments like "SSI" are OCR debris, not a designation.
            continue
        candidate = ' '.join(tokens)
        if not 3 <= len(candidate) <= 20:
            continue
        # Values on the card are printed in capitals.
        capitals = sum(1 for char in candidate if char.isupper())
        if capitals < max(2, len([c for c in candidate if c.isalpha()]) * 0.7):
            continue
        if best is None or len(candidate) > len(best):
            best = candidate
    if best:
        result[constants.FIELD_MODEL] = {'value': best}


#: The one word that identifies each emirate unambiguously.
EMIRATE_KEYWORDS = {
    'dhabi': 'Abu Dhabi',
    'dubai': 'Dubai',
    'sharjah': 'Sharjah',
    'ajman': 'Ajman',
    'quwain': 'Umm Al Quwain',
    'qaiwain': 'Umm Al Quwain',
    'khaimah': 'Ras Al Khaimah',
    'khaima': 'Ras Al Khaimah',
    'fujairah': 'Fujairah',
    'fujaira': 'Fujairah',
}


def _resolve_emirate(value):
    """Return the canonical emirate name found inside a noisy cell."""
    squashed = squash(value)
    for known in constants.EMIRATES:
        if squash(known) in squashed:
            return known
    for keyword, name in EMIRATE_KEYWORDS.items():
        if keyword in squashed:
            return name
    return None


def _post_process(result, text):
    """Recover values that the label pass could not attribute."""
    # VIN: a 17 character alphanumeric block is unmistakable. Scan token by
    # token - collapsing the whole page into one string destroys the word
    # boundaries and finds nothing.
    if constants.FIELD_VIN not in result:
        candidate = _find_vin(text)
        if candidate:
            result[constants.FIELD_VIN] = {'value': candidate}

    # Plate: "17/70452" style cells survive even when the label was mangled.
    if constants.FIELD_PLATE not in result:
        match = re.search(r'\b(\d{1,2})\s*/\s*(\d{3,6})\b',
                          strip_arabic_digits(text))
        if match:
            result[constants.FIELD_PLATE] = {'value': match.group(2)}
            result.setdefault(constants.FIELD_PLATE_CODE,
                              {'value': match.group(1)})

    # Emirate: reduce a noisy cell such as "DHABI saat Peewee" to the real
    # name. Each emirate has one word that belongs to no other.
    emirate = (result.get(constants.FIELD_EMIRATE) or {}).get('value')
    if emirate:
        resolved = _resolve_emirate(emirate)
        if resolved:
            result[constants.FIELD_EMIRATE]['value'] = resolved

    # Emirate: match against the known list anywhere in the document.
    if constants.FIELD_EMIRATE not in result:
        resolved = _resolve_emirate(text)
        if resolved:
            result[constants.FIELD_EMIRATE] = {'value': resolved}

    # Model year: a bare 4 digit year on the model year row.
    if constants.FIELD_MODEL_YEAR in result:
        raw = strip_arabic_digits(result[constants.FIELD_MODEL_YEAR]['value'])
        match = re.search(r'(19|20)\d{2}', raw)
        if match:
            result[constants.FIELD_MODEL_YEAR]['value'] = match.group(0)

    # Identifier cells often keep the wreckage of the Arabic label.
    for key in (constants.FIELD_VIN, constants.FIELD_ENGINE_NO):
        if key in result:
            result[key]['value'] = _best_identifier(result[key]['value'])

    if constants.FIELD_MODEL in result:
        result[constants.FIELD_MODEL]['value'] = _clean_designation(
            result[constants.FIELD_MODEL]['value'])

    # Closed vocabularies rescue values whose label OCR destroyed.
    _recover_from_vocabulary(result, text, constants.FIELD_COLOR,
                             constants.COLOR_VOCABULARY)
    if constants.FIELD_COLOR not in result:
        # Some cards carry the colour in Arabic only.
        for arabic, english in constants.ARABIC_COLOR_MAP.items():
            if arabic in text:
                result[constants.FIELD_COLOR] = {'value': english}
                break
    _recover_from_vocabulary(result, text, constants.FIELD_FUEL_TYPE,
                             constants.FUEL_VOCABULARY)

    # Plate number and plate code frequently share a row: "8830  AUH  1".
    plate = result.get(constants.FIELD_PLATE, {}).get('value', '')
    if plate:
        tokens = [t for t in re.split(r'[^0-9A-Za-z\u0600-\u06ff]+',
                                      strip_arabic_digits(plate)) if t]
        digits = [t for t in tokens if t.isdigit()]
        if digits:
            number = max(digits, key=len)
            result[constants.FIELD_PLATE]['value'] = number
            leftovers = [t for t in tokens if t != number]
            if leftovers and constants.FIELD_PLATE_CODE not in result:
                # The shortest leftover token is the code (1, 13, A, ...).
                result[constants.FIELD_PLATE_CODE] = {
                    'value': min(leftovers, key=len)}


def _reconcile(result):
    """Resolve layout differences between the two Mulkiya generations.

    On the Abu Dhabi "Vehicle License" card the cell labelled *Model* holds the
    year of manufacture and the model name sits under *Veh. Type*, the opposite
    of the older card. Detecting a bare year is unambiguous, so the two are
    swapped rather than guessed.
    """
    model = (result.get(constants.FIELD_MODEL) or {}).get('value', '')
    vehicle_type = (result.get(KEY_VEHICLE_TYPE) or {}).get('value', '')
    # The cell may carry OCR debris after the year, e.g. "2016 pie ALL".
    leading_year = re.match(r'^[^0-9A-Za-z]*((?:19|20)\d{2})(?![0-9])',
                            strip_arabic_digits(model).strip())
    if model and leading_year:
        result.setdefault(constants.FIELD_MODEL_YEAR,
                          {'value': leading_year.group(1)})
        if vehicle_type and not re.fullmatch(
                r'(19|20)\d{2}', strip_arabic_digits(vehicle_type).strip()):
            result[constants.FIELD_MODEL] = {'value': vehicle_type}
        else:
            result.pop(constants.FIELD_MODEL, None)
    elif not model and vehicle_type:
        # Older layout: only fall back to the type when no model was read.
        result[constants.FIELD_MODEL] = {'value': vehicle_type}

    if constants.FIELD_MODEL in result:
        result[constants.FIELD_MODEL]['value'] = _clean_designation(
            result[constants.FIELD_MODEL]['value'])
    return result


def merge_sides(front, back):
    """Merge the two parsed sides. Non-empty values win, front takes priority."""
    merged = {}
    for source in (front or {}, back or {}):
        for key, entry in source.items():
            value = (entry or {}).get('value')
            if value in (None, '', 0):
                continue
            if key not in merged:
                merged[key] = dict(entry)
    _reconcile(merged)
    merged.pop(KEY_VEHICLE_TYPE, None)
    merged.pop(KEY_IGNORE, None)
    return merged


# --------------------------------------------------------------------------
# Consensus between OCR passes
# --------------------------------------------------------------------------
def plausibility(key, value):
    """How much a value looks like a real reading of that field, 0-3.

    Different OCR passes disagree, and the disagreement is informative: a
    chassis number of exactly 17 characters beats a 12 character one, and a
    colour from the known vocabulary beats an unrecognised word. This is what
    lets several mediocre passes add up to one good answer.
    """
    value = str(value or '').strip()
    if not value:
        return -1
    upper = value.upper()
    compact = re.sub(r'[^0-9A-Za-z]', '', upper)

    if key == constants.FIELD_VIN:
        if len(compact) == 17 and not set('IOQ') & set(compact):
            return 3
        if len(compact) == 17:
            return 2
        return 1 if 15 <= len(compact) <= 18 else 0
    if key == constants.FIELD_ENGINE_NO:
        if 6 <= len(compact) <= 20 and any(c.isdigit() for c in compact) \
                and any(c.isalpha() for c in compact):
            return 2
        return 1 if len(compact) >= 5 else 0
    if key == constants.FIELD_PLATE:
        return 3 if compact.isdigit() and 3 <= len(compact) <= 6 else 0
    if key == constants.FIELD_PLATE_CODE:
        if compact.isdigit() and 1 <= len(compact) <= 2:
            return 3
        # Some emirates use a single letter code.
        return 2 if len(compact) == 1 and compact.isalpha() else 0
    if key == constants.FIELD_EMIRATE:
        return 3 if _resolve_emirate(value) else 0
    if key == constants.FIELD_COLOR:
        return 3 if upper in constants.COLOR_VOCABULARY else 1
    if key == constants.FIELD_FUEL_TYPE:
        return 3 if upper in constants.FUEL_VOCABULARY else 1
    if key == constants.FIELD_MODEL_YEAR:
        digits = re.sub(r'\D', '', value)
        return 3 if len(digits) == 4 and 1970 <= int(digits) <= 2035 else 0
    if key == constants.FIELD_CYLINDERS:
        digits = re.sub(r'\D', '', value)
        return 2 if digits and 1 <= int(digits) <= 16 else 0
    if key in (constants.FIELD_MODEL, constants.FIELD_MAKE):
        if _looks_like_identifier(compact):
            return 0
        tokens = [token for token in re.split(r'[^0-9A-Za-z]+', value) if token]
        if not tokens:
            return 0
        excluded = set(constants.NOISE_VOCABULARY) | \
            set(constants.COUNTRY_VOCABULARY) | set(constants.COLOR_VOCABULARY)
        if any(token.upper() in excluded for token in tokens):
            return 0
        letters = sum(1 for char in value if char.isalpha())
        if letters < 3 or not 3 <= len(value) <= 22:
            return 0
        # Card values are printed in capitals; mixed case is OCR debris.
        capitals = sum(1 for char in value if char.isupper())
        return 2 if capitals >= letters * 0.6 else 0
    return 1


def vote(key, candidates):
    """Pick the best reading of one field from several OCR passes.

    ``candidates`` is a list of ``(value, pass_confidence)``. Plausibility
    dominates, agreement between passes breaks ties, and the engine's own
    confidence is the final tiebreak.
    """
    tally = {}
    for value, confidence in candidates:
        value = str(value or '').strip()
        if not value:
            continue
        entry = tally.setdefault(value, {'count': 0, 'confidence': 0.0})
        entry['count'] += 1
        entry['confidence'] = max(entry['confidence'], confidence or 0.0)
    if not tally:
        return None, 0.0

    def rank(item):
        value, entry = item
        return (plausibility(key, value), entry['count'], entry['confidence'])

    best_value, best_entry = max(tally.items(), key=rank)
    if plausibility(key, best_value) <= 0:
        # Every pass produced something implausible. An empty field the user
        # fills in beats a confident-looking wrong value they might not check.
        return None, 0.0
    return best_value, best_entry['confidence']
