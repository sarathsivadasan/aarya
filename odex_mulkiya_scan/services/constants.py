# -*- coding: utf-8 -*-
"""Canonical vocabulary of the Odex Mulkiya Scan application.

Everything that other Odex applications are allowed to rely on is declared here.
Providers, services, models and integration modules all speak these keys.
"""

# --------------------------------------------------------------------------
# Canonical output keys (section 5 of the specification)
# --------------------------------------------------------------------------
FIELD_ENGINE_NO = 'engine_no'
FIELD_VIN = 'vin_sn'
FIELD_PLATE = 'license_plate'
FIELD_PLATE_CODE = 'plate_code'
FIELD_EMIRATE = 'registration_emirate'
FIELD_MAKE = 'make'
FIELD_MODEL = 'model'
FIELD_MODEL_YEAR = 'model_year'
FIELD_COLOR = 'color'
FIELD_FUEL_TYPE = 'fuel_type'
FIELD_CYLINDERS = 'cylinder_count'

MULKIYA_FIELDS = [
    FIELD_ENGINE_NO,
    FIELD_VIN,
    FIELD_PLATE,
    FIELD_PLATE_CODE,
    FIELD_EMIRATE,
    FIELD_MAKE,
    FIELD_MODEL,
    FIELD_MODEL_YEAR,
    FIELD_COLOR,
    FIELD_FUEL_TYPE,
    FIELD_CYLINDERS,
]

#: Human readable labels, used for error messages and API documentation.
FIELD_LABELS = {
    FIELD_ENGINE_NO: 'Engine Number',
    FIELD_VIN: 'Chassis Number / VIN',
    FIELD_PLATE: 'Plate Number',
    FIELD_PLATE_CODE: 'Plate Code',
    FIELD_EMIRATE: 'Registration Emirate',
    FIELD_MAKE: 'Make',
    FIELD_MODEL: 'Model',
    FIELD_MODEL_YEAR: 'Model Year',
    FIELD_COLOR: 'Colour',
    FIELD_FUEL_TYPE: 'Fuel Type',
    FIELD_CYLINDERS: 'Number of Cylinders',
}

#: Mapping between the canonical key and the ORM column on ``odex.mulkiya.scan``.
#: ``model`` cannot be used as a column name safely, so it is stored as
#: ``vehicle_model`` but always exposed as ``model`` in the structured result.
FIELD_TO_COLUMN = {
    FIELD_ENGINE_NO: 'engine_no',
    FIELD_VIN: 'vin_sn',
    FIELD_PLATE: 'license_plate',
    FIELD_PLATE_CODE: 'plate_code',
    FIELD_EMIRATE: 'registration_emirate',
    FIELD_MAKE: 'make',
    FIELD_MODEL: 'vehicle_model',
    FIELD_MODEL_YEAR: 'model_year',
    FIELD_COLOR: 'color',
    FIELD_FUEL_TYPE: 'fuel_type',
    FIELD_CYLINDERS: 'cylinder_count',
}

COLUMN_TO_FIELD = {v: k for k, v in FIELD_TO_COLUMN.items()}

#: Confidence columns follow the ``<column>_conf`` convention.
CONFIDENCE_SUFFIX = '_conf'

#: Fields whose values are integers in the structured output.
INTEGER_FIELDS = {FIELD_CYLINDERS}

#: Fields that are never auto-corrected (section 28).
PROTECTED_FIELDS = {FIELD_VIN, FIELD_ENGINE_NO}

# --------------------------------------------------------------------------
# Scan workflow (section 8)
# --------------------------------------------------------------------------
STATE_DRAFT = 'draft'
STATE_UPLOADED = 'uploaded'
STATE_PROCESSING = 'processing'
STATE_EXTRACTED = 'extracted'
STATE_VERIFIED = 'verified'
STATE_APPLIED = 'applied'
STATE_FAILED = 'failed'

SCAN_STATES = [
    (STATE_DRAFT, 'Draft'),
    (STATE_UPLOADED, 'Images Uploaded'),
    (STATE_PROCESSING, 'Processing'),
    (STATE_EXTRACTED, 'Extracted'),
    (STATE_VERIFIED, 'Verified'),
    (STATE_APPLIED, 'Applied'),
    (STATE_FAILED, 'Failed'),
]

# --------------------------------------------------------------------------
# Configuration (ir.config_parameter keys) - section 16
# --------------------------------------------------------------------------
PARAM_PREFIX = 'odex_mulkiya_scan.'
PARAM_ENABLED = PARAM_PREFIX + 'enabled'
PARAM_PROVIDER = PARAM_PREFIX + 'provider'
PARAM_API_URL = PARAM_PREFIX + 'api_url'
PARAM_API_KEY = PARAM_PREFIX + 'api_key'
PARAM_API_SECRET = PARAM_PREFIX + 'api_secret'
PARAM_API_MODEL = PARAM_PREFIX + 'api_model'
PARAM_THRESHOLD = PARAM_PREFIX + 'confidence_threshold'
PARAM_TIMEOUT = PARAM_PREFIX + 'timeout'
PARAM_MAX_DIMENSION = PARAM_PREFIX + 'max_dimension'
PARAM_MAX_FILE_MB = PARAM_PREFIX + 'max_file_mb'
PARAM_API_ENABLED = PARAM_PREFIX + 'api_enabled'

DEFAULT_THRESHOLD = 90
DEFAULT_TIMEOUT = 90
DEFAULT_MAX_DIMENSION = 2000
DEFAULT_MAX_FILE_MB = 12

# --------------------------------------------------------------------------
# Images (section 39)
# --------------------------------------------------------------------------
SUPPORTED_MIMETYPES = ('image/jpeg', 'image/png', 'image/webp')

#: Magic byte signatures used to validate uploads server side.
IMAGE_SIGNATURES = (
    (b'\xff\xd8\xff', 'image/jpeg'),
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
    (b'RIFF', 'image/webp'),  # refined by the WEBP marker at offset 8
)

# --------------------------------------------------------------------------
# Emirates (section 6) - used for normalization only, never as a hard-coded
# selection on the model.
# --------------------------------------------------------------------------
EMIRATES = [
    'Abu Dhabi',
    'Dubai',
    'Sharjah',
    'Ajman',
    'Umm Al Quwain',
    'Ras Al Khaimah',
    'Fujairah',
]

# --------------------------------------------------------------------------
# Small closed vocabularies used to recover values whose label was destroyed
# by OCR. Only words that are unambiguous on a registration card.
# --------------------------------------------------------------------------
COLOR_VOCABULARY = [
    'WHITE', 'BLACK', 'SILVER', 'GREY', 'GRAY', 'BLUE', 'RED', 'GREEN',
    'BROWN', 'GOLD', 'GOLDEN', 'BEIGE', 'YELLOW', 'ORANGE', 'MAROON',
    'PEARL', 'BRONZE', 'PURPLE', 'PINK', 'CHAMPAGNE', 'NAVY', 'CREAM',
]

FUEL_VOCABULARY = [
    'PETROL', 'GASOLINE', 'DIESEL', 'ELECTRIC', 'HYBRID', 'LPG', 'CNG',
]

#: Never a make or a model: these appear in the Origin / Nationality cells.
COUNTRY_VOCABULARY = [
    'CHINA', 'INDIA', 'JAPAN', 'KOREA', 'GERMANY', 'USA', 'UAE', 'UK',
    'FRANCE', 'ITALY', 'SPAIN', 'THAILAND', 'TURKEY', 'PAKISTAN', 'EGYPT',
    'PHILIPPINES', 'BANGLADESH', 'SUDAN', 'JORDAN', 'SYRIA', 'LEBANON',
    'UNITED ARAB EMIRATES', 'SAUDI ARABIA', 'CZECH', 'MEXICO', 'BRAZIL',
]

#: Card furniture that must never be mistaken for vehicle data.
NOISE_VOCABULARY = [
    'VEHICLE', 'INFORMATION', 'LICENSE', 'LICENCE', 'REGISTRATION',
    'MINISTRY', 'INTERIOR', 'UNITED', 'ARAB', 'EMIRATES', 'POLICE',
    'AUTHORITY', 'LICENSING', 'PRIVATE', 'PUBLIC', 'WEIGHT', 'EMPTY',
    'GROSS', 'PAYLOAD', 'CAPACITY', 'SEATING', 'STANDING', 'OWNER',
    'NATIONALITY', 'POLICY', 'MORTGAGE', 'EXP', 'INS', 'DATE', 'NO',
    'NUM', 'PASS', 'ORIGIN', 'TYPE', 'MODEL', 'YEAR', 'CHASSIS', 'ENGINE',
]

#: Some cards print the colour in Arabic only, with no English equivalent.
ARABIC_COLOR_MAP = {
    '\u0627\u0633\u0648\u062f': 'Black',
    '\u0623\u0633\u0648\u062f': 'Black',
    '\u0627\u0628\u064a\u0636': 'White',
    '\u0623\u0628\u064a\u0636': 'White',
    '\u0641\u0636\u064a': 'Silver',
    '\u0631\u0645\u0627\u062f\u064a': 'Grey',
    '\u0627\u0632\u0631\u0642': 'Blue',
    '\u0623\u0632\u0631\u0642': 'Blue',
    '\u0627\u062d\u0645\u0631': 'Red',
    '\u0623\u062d\u0645\u0631': 'Red',
    '\u0627\u062e\u0636\u0631': 'Green',
    '\u0628\u0646\u064a': 'Brown',
    '\u0630\u0647\u0628\u064a': 'Gold',
    '\u0628\u064a\u062c': 'Beige',
}
