# -*- coding: utf-8 -*-
import base64
import io

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..services import constants, document_parser, image_service
from ..services.ocr_service import MulkiyaOcrService

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def sample_image(width=600, height=400, fmt='JPEG'):
    """Return a small valid base64 image."""
    if Image is None:  # pragma: no cover
        return base64.b64encode(b'\xff\xd8\xff' + b'\x00' * 1024)
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), (240, 235, 220)).save(buffer, format=fmt)
    return base64.b64encode(buffer.getvalue())


@tagged('post_install', '-at_install', 'mulkiya')
class TestOcrService(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            constants.PARAM_PROVIDER, 'demo')
        cls.env['ir.config_parameter'].sudo().set_param(
            constants.PARAM_ENABLED, 'True')
        cls.service = MulkiyaOcrService(cls.env)

    # -- image handling ------------------------------------------------
    def test_rejects_non_image(self):
        with self.assertRaises(UserError):
            image_service.validate(base64.b64encode(b'not an image at all'),
                                   'front')

    def test_detects_mimetype_from_content(self):
        raw = base64.b64decode(sample_image())
        self.assertEqual(image_service.detect_mimetype(raw), 'image/jpeg')

    def test_large_image_is_downscaled(self):
        if Image is None:  # pragma: no cover
            self.skipTest('Pillow is not available')
        big = sample_image(width=4000, height=3000)
        prepared, mimetype = image_service.prepare(big, 'front', max_dimension=1000)
        self.assertEqual(mimetype, 'image/jpeg')
        with Image.open(io.BytesIO(base64.b64decode(prepared))) as img:
            self.assertLessEqual(max(img.size), 1000)

    # -- provider ------------------------------------------------------
    def test_provider_registry(self):
        from ..providers.base_provider import PROVIDER_REGISTRY
        for code in ('demo', 'anthropic', 'openai', 'google_vision'):
            self.assertIn(code, PROVIDER_REGISTRY)

    def test_full_scan_with_demo_provider(self):
        result = self.service.scan(sample_image(), sample_image())
        fields = result['fields']
        self.assertEqual(fields[constants.FIELD_VIN]['value'],
                         'JN6BE6DSXF9008830')
        self.assertEqual(fields[constants.FIELD_MAKE]['value'], 'Nissan')
        self.assertEqual(fields[constants.FIELD_EMIRATE]['value'], 'Abu Dhabi')
        self.assertEqual(fields[constants.FIELD_CYLINDERS]['value'], 4)
        self.assertEqual(fields[constants.FIELD_PLATE]['value'], '8830')
        self.assertTrue(result['confidence'] > 0)

    def test_scan_requires_both_sides(self):
        with self.assertRaises(UserError):
            self.service.scan(sample_image(), False)

    def test_disabled_ocr(self):
        self.env['ir.config_parameter'].sudo().set_param(
            constants.PARAM_ENABLED, 'False')
        try:
            with self.assertRaises(UserError):
                self.service.scan(sample_image(), sample_image())
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                constants.PARAM_ENABLED, 'True')

    def test_low_confidence_is_flagged(self):
        normalized = {
            constants.FIELD_COLOR: {'value': 'White', 'confidence': 40},
        }
        warnings = self.service.build_warnings(normalized, {}, 90)
        self.assertIn('Colour', warnings['confidence'])


@tagged('post_install', '-at_install', 'mulkiya')
class TestDocumentParser(TransactionCase):

    SAMPLE_BACK = """
Chassis No.        JN6BE6DSXF9008830
Engine No.         YD25 123456T
No. of Cylinders   4
Gross Weight       3500
"""

    SAMPLE_FRONT = """
UNITED ARAB EMIRATES
Plate No.      8830      AUH      1
Reg. Date      22/05/2014
Vehicle Make   NISSAN
Model          NV350
Model Year     2014
Color          WHITE
Fuel Type      DIESEL
Place of Issue Abu Dhabi
"""

    def test_parse_back_side(self):
        parsed = document_parser.parse_text(self.SAMPLE_BACK)
        self.assertEqual(parsed[constants.FIELD_VIN]['value'],
                         'JN6BE6DSXF9008830')
        self.assertEqual(parsed[constants.FIELD_ENGINE_NO]['value'],
                         'YD25 123456T')
        self.assertEqual(parsed[constants.FIELD_CYLINDERS]['value'], '4')

    def test_parse_front_side(self):
        parsed = document_parser.parse_text(self.SAMPLE_FRONT)
        self.assertEqual(parsed[constants.FIELD_MAKE]['value'], 'NISSAN')
        self.assertEqual(parsed[constants.FIELD_MODEL_YEAR]['value'], '2014')
        self.assertEqual(parsed[constants.FIELD_COLOR]['value'], 'WHITE')
        self.assertEqual(parsed[constants.FIELD_FUEL_TYPE]['value'], 'DIESEL')
        self.assertEqual(parsed[constants.FIELD_EMIRATE]['value'], 'Abu Dhabi')

    def test_plate_and_code_are_split(self):
        parsed = document_parser.parse_text(self.SAMPLE_FRONT)
        self.assertEqual(parsed[constants.FIELD_PLATE]['value'], '8830')
        self.assertIn(constants.FIELD_PLATE_CODE, parsed)

    def test_merge_prefers_front(self):
        merged = document_parser.merge_sides(
            {'make': {'value': 'NISSAN'}},
            {'make': {'value': 'TOYOTA'}, 'vin_sn': {'value': 'X'}})
        self.assertEqual(merged['make']['value'], 'NISSAN')
        self.assertEqual(merged['vin_sn']['value'], 'X')


@tagged('post_install', '-at_install', 'mulkiya')
class TestAbuDhabiLayout(TransactionCase):
    """The Abu Dhabi 'Vehicle License' card labels its cells differently."""

    FRONT = (
        "Traffic Plate No.   17/70452        \u0631\u0642\u0645 \u0627\u0644\u0644\u0648\u062d\u0629\n"
        "Place of Issue      ABU DHABI       \u0623\u0628\u0648\u0638\u0628\u064a\n"
        "T. C. No.           1150014531      \u0627\u0644\u0631\u0645\u0632 \u0627\u0644\u0645\u0631\u0648\u0631\u064a\n"
        "Nationality         INDIA           \u0627\u0644\u062c\u0646\u0633\u064a\u0629\n"
    )
    BACK = (
        "Model       2016        Num. of Pass.   5\n"
        "Origin      CHINA       \u0628\u0644\u062f \u0627\u0644\u0635\u0646\u0639\n"
        "Veh. Type   ARRIZO 7    \u0627\u0631\u064a\u0632\u0648 7\n"
        "Color       BLACK       \u0644\u0648\u0646 \u0627\u0644\u0645\u0631\u0643\u0628\u0629\n"
        "Eng. No.    SQRE4G16AAFM54611       \u0631\u0642\u0645 \u0627\u0644\u0645\u062d\u0631\u0643\n"
        "Chassis No. LVVDC21B8GD024477       \u0631\u0642\u0645 \u0627\u0644\u0642\u0627\u0639\u062f\u0629\n"
    )

    def _parse(self):
        return document_parser.merge_sides(
            document_parser.parse_text(self.FRONT),
            document_parser.parse_text(self.BACK))

    def test_identifiers(self):
        parsed = self._parse()
        self.assertEqual(parsed[constants.FIELD_ENGINE_NO]['value'],
                         'SQRE4G16AAFM54611')
        self.assertEqual(parsed[constants.FIELD_VIN]['value'],
                         'LVVDC21B8GD024477')

    def test_plate_code_split_on_slash(self):
        parsed = self._parse()
        self.assertEqual(parsed[constants.FIELD_PLATE]['value'], '70452')
        self.assertEqual(parsed[constants.FIELD_PLATE_CODE]['value'], '17')

    def test_model_cell_holding_a_year_becomes_the_year(self):
        parsed = self._parse()
        self.assertEqual(parsed[constants.FIELD_MODEL_YEAR]['value'], '2016')
        self.assertEqual(parsed[constants.FIELD_MODEL]['value'], 'ARRIZO 7')

    def test_origin_is_not_the_make(self):
        parsed = self._parse()
        self.assertNotEqual(
            parsed.get(constants.FIELD_MAKE, {}).get('value'), 'CHINA')

    def test_passenger_count_is_not_cylinders(self):
        parsed = self._parse()
        self.assertNotIn(constants.FIELD_CYLINDERS, parsed)

    def test_arabic_label_is_stripped_from_latin_value(self):
        parsed = self._parse()
        self.assertEqual(parsed[constants.FIELD_EMIRATE]['value'], 'ABU DHABI')
        self.assertEqual(parsed[constants.FIELD_COLOR]['value'], 'BLACK')

    def test_traffic_code_is_not_the_plate_code(self):
        parsed = document_parser.parse_text(self.FRONT)
        self.assertNotEqual(
            parsed.get(constants.FIELD_PLATE_CODE, {}).get('value'),
            '1150014531')


@tagged('post_install', '-at_install', 'mulkiya')
class TestLocalProviders(TransactionCase):
    """The application must be usable with no external service at all."""

    def test_local_providers_are_registered(self):
        from ..providers.base_provider import PROVIDER_REGISTRY
        for code in ('tesseract', 'ollama'):
            self.assertIn(code, PROVIDER_REGISTRY)

    def test_local_providers_need_no_credentials(self):
        from ..providers.base_provider import PROVIDER_REGISTRY
        for code in ('tesseract', 'ollama', 'demo'):
            provider = PROVIDER_REGISTRY[code](self.env, {})
            self.assertFalse(provider.requires_credentials)
            # Must not raise: there is nothing to configure.
            provider.check_credentials()

    def test_cloud_providers_still_require_credentials(self):
        from ..providers.base_provider import PROVIDER_REGISTRY, MulkiyaOCRError
        for code in ('anthropic', 'openai', 'google_vision'):
            provider = PROVIDER_REGISTRY[code](self.env, {})
            with self.assertRaises(MulkiyaOCRError):
                provider.check_credentials()

    def test_tesseract_is_offered_in_the_settings(self):
        from ..providers.base_provider import provider_selection
        codes = dict(provider_selection())
        self.assertIn('tesseract', codes)
        self.assertIn('No API', codes['tesseract'])

    def test_tesseract_reports_a_clear_error_when_missing(self):
        """A server without the engine must say so, not crash."""
        from ..providers import provider_tesseract
        from ..providers.base_provider import MulkiyaOCRError
        original = provider_tesseract.pytesseract
        provider_tesseract.pytesseract = None
        try:
            provider = provider_tesseract.TesseractMulkiyaProvider(self.env, {})
            with self.assertRaises(MulkiyaOCRError) as caught:
                provider.extract((b'', 'image/png'), (b'', 'image/png'))
            self.assertIn('tesseract', str(caught.exception).lower())
        finally:
            provider_tesseract.pytesseract = original


@tagged('post_install', '-at_install', 'mulkiya')
class TestNoisyOcrRecovery(TransactionCase):
    """Real OCR output is dirty. Values must survive mangled labels."""

    def test_vin_found_among_tokens(self):
        """The scan is token by token: gluing the page together finds nothing."""
        text = "Chassis No.   LVVDC21B8GD024477   \u0631\u0642\u0645 \u0627\u0644\u0642\u0627\u0639\u062f\u0629\nwww.adpolice.gov.ae"
        self.assertEqual(document_parser._find_vin(text), 'LVVDC21B8GD024477')

    def test_vin_with_a_misread_character_is_still_recovered(self):
        """A single bad character must not lose the whole value."""
        # 'O' never appears in a real VIN, so the strict pattern rejects it.
        text = "Chassis No. LVVDC21B8GDO24477"
        found = document_parser._find_vin(text)
        self.assertEqual(found, 'LVVDC21B8GDO24477')
        # ...and it is flagged rather than silently accepted.
        from ..services.normalization_service import NormalizationService
        warnings = NormalizationService(self.env).check_vin(found)
        self.assertTrue(warnings)

    def test_vin_ignores_ordinary_words(self):
        self.assertIsNone(document_parser._find_vin(
            "Vehicle Information Licensing Authority Abu Dhabi Police"))

    def test_plate_recovered_from_pattern_when_label_is_lost(self):
        parsed = document_parser.parse_text("Traffc Piate Ne.   17/70452")
        self.assertEqual(parsed[constants.FIELD_PLATE]['value'], '70452')
        self.assertEqual(parsed[constants.FIELD_PLATE_CODE]['value'], '17')

    def test_misread_label_is_matched_fuzzily(self):
        parsed = document_parser.parse_text("Chasis Ne.   LVVDC21B8GD024477")
        self.assertEqual(parsed[constants.FIELD_VIN]['value'],
                         'LVVDC21B8GD024477')

    def test_fuzzy_matching_does_not_eat_long_values(self):
        """A long fragment is data, never a label."""
        key, _remainder = document_parser._label_for(
            'MOHAMED ABDUL HATHE JABBAR HIDHAYATHULLA')
        self.assertIsNone(key)

    def test_local_provider_gets_the_original_image(self):
        from ..providers.provider_tesseract import TesseractMulkiyaProvider
        self.assertEqual(TesseractMulkiyaProvider.image_max_dimension, 0)


@tagged('post_install', '-at_install', 'mulkiya')
class TestDirtyOcrRecovery(TransactionCase):
    """Recovery paths for rows whose label OCR destroyed."""

    def test_identifier_stripped_of_label_wreckage(self):
        parsed = document_parser.parse_text(
            "Eng. No.   SQRE4G16AAFM54611   Soult aa, |")
        self.assertEqual(parsed[constants.FIELD_ENGINE_NO]['value'],
                         'SQRE4G16AAFM54611')

    def test_vin_stripped_of_label_wreckage(self):
        parsed = document_parser.parse_text(
            "Chassis No,   | LVVDC21B8GD024477   aslall ns; |")
        self.assertEqual(parsed[constants.FIELD_VIN]['value'],
                         'LVVDC21B8GD024477')

    def test_colour_recovered_without_a_label(self):
        """The colour row is labelled in Arabic only on some cards."""
        parsed = document_parser.parse_text("Vehicle Information\nBLACK\n")
        self.assertEqual(parsed[constants.FIELD_COLOR]['value'], 'BLACK')

    def test_colour_vocabulary_does_not_match_inside_words(self):
        parsed = document_parser.parse_text("BLACKSMITH ROAD TRADING")
        self.assertNotIn(constants.FIELD_COLOR, parsed)

    def test_model_recovered_from_a_mangled_label(self):
        result = {}
        document_parser._recover_model(result, "nee   ARRIZO 7\nBLACK\n")
        self.assertEqual(result[constants.FIELD_MODEL]['value'], 'ARRIZO 7')

    def test_model_recovery_rejects_countries_and_furniture(self):
        for noise in ("Origin   CHINA", "Nationality   INDIA",
                      "Vehicle Information", "Empty Weight   1520"):
            result = {}
            document_parser._recover_model(result, noise)
            self.assertNotIn(constants.FIELD_MODEL, result, noise)

    def test_model_recovery_rejects_short_debris(self):
        result = {}
        document_parser._recover_model(result, ": |\ni\nSSI\n")
        self.assertNotIn(constants.FIELD_MODEL, result)

    def test_model_recovery_never_overrides_a_read_model(self):
        result = {constants.FIELD_MODEL: {'value': 'NV350'}}
        document_parser._recover_model(result, "nee   ARRIZO 7")
        self.assertEqual(result[constants.FIELD_MODEL]['value'], 'NV350')

    def test_fuel_recovered_from_vocabulary(self):
        parsed = document_parser.parse_text("Vehicle Information\nDIESEL\n")
        self.assertEqual(parsed[constants.FIELD_FUEL_TYPE]['value'], 'DIESEL')


@tagged('post_install', '-at_install', 'mulkiya')
class TestRealCardRegressions(TransactionCase):
    """Fixtures taken from a real Abu Dhabi card scanned at low resolution."""

    def test_emirate_cell_reduced_to_the_real_name(self):
        parsed = document_parser.parse_text("Place of Issue   ABU DHABI nbs   :")
        self.assertEqual(parsed[constants.FIELD_EMIRATE]['value'], 'Abu Dhabi')

    def test_chassis_row_is_never_taken_for_the_model(self):
        text = ("Vehicle Information\n"
                "! Chassis No.   ivvoc21B8GD024477.2\u00ab2=~\u2014~S~S*\u00ab~CS kes sd\n")
        result = document_parser.parse_text(text)
        document_parser._recover_model(result, text)
        self.assertNotEqual(
            (result.get(constants.FIELD_MODEL) or {}).get('value'),
            result[constants.FIELD_VIN]['value'])

    def test_model_cell_leading_with_a_year(self):
        parsed = document_parser.parse_text("| Model   2016   | pie ALL|Num of Pass |   5")
        self.assertEqual(parsed[constants.FIELD_MODEL_YEAR]['value'], '2016')

    def test_designation_cleaned_of_debris(self):
        self.assertEqual(
            document_parser._clean_designation('= ARRIZOT Soe 7oyd Ras4 y'),
            'ARRIZOT')

    def test_designation_left_alone_when_already_clean(self):
        self.assertEqual(document_parser._clean_designation('Land Cruiser'),
                         'Land Cruiser')

    def test_small_images_raise_a_quality_warning(self):
        from ..services import image_service
        small = sample_image(width=550, height=310)
        self.assertTrue(image_service.resolution_warning(small, small))

    def test_large_images_raise_no_quality_warning(self):
        from ..services import image_service
        large = sample_image(width=2400, height=1500)
        self.assertFalse(image_service.resolution_warning(large, large))


@tagged('post_install', '-at_install', 'mulkiya')
class TestPassConsensus(TransactionCase):
    """Several imperfect OCR passes must add up to one good answer."""

    def test_full_length_vin_beats_a_truncated_one(self):
        value, _confidence = document_parser.vote('vin_sn', [
            ('LVVDC21B8GD0244', 80.0),
            ('LVVDC21B8GD024477', 60.0),
        ])
        self.assertEqual(value, 'LVVDC21B8GD024477')

    def test_vin_without_forbidden_letters_wins(self):
        value, _confidence = document_parser.vote('vin_sn', [
            ('LVVDC21B8GDO24477', 90.0),
            ('LVVDC21B8GD024477', 50.0),
        ])
        self.assertEqual(value, 'LVVDC21B8GD024477')

    def test_known_colour_beats_noise(self):
        value, _confidence = document_parser.vote('color', [
            ('JES 51 od', 90.0), ('BLACK', 40.0)])
        self.assertEqual(value, 'BLACK')

    def test_plausible_year_beats_debris(self):
        value, _confidence = document_parser.vote('model_year', [
            ('giwalli', 90.0), ('2008', 30.0)])
        self.assertEqual(value, '2008')

    def test_numeric_plate_beats_letters(self):
        value, _confidence = document_parser.vote('license_plate', [
            ('EE', 90.0), ('31260', 40.0)])
        self.assertEqual(value, '31260')

    def test_agreement_breaks_ties(self):
        value, _confidence = document_parser.vote('engine_no', [
            ('6G75TG9618', 50.0), ('6G75TG9618', 55.0), ('6G75TG9619', 90.0)])
        self.assertEqual(value, '6G75TG9618')

    def test_empty_ballot_returns_nothing(self):
        value, _confidence = document_parser.vote('color', [('', 90.0)])
        self.assertIsNone(value)

    def test_identifier_is_never_voted_in_as_a_model(self):
        self.assertEqual(document_parser.plausibility(
            'model', 'JMYMYV87W8J708179'), 0)


@tagged('post_install', '-at_install', 'mulkiya')
class TestFoilCardHandling(TransactionCase):
    """A Mulkiya is printed on patterned gold foil, which OCR hates."""

    def test_adaptive_threshold_is_the_first_rendering(self):
        """Measured on a real card: 2/5 key values without it, 5/5 with it."""
        from ..providers.provider_tesseract import TesseractMulkiyaProvider
        self.assertEqual(TesseractMulkiyaProvider.ADAPTIVE_RADIUS, 40)
        self.assertEqual(TesseractMulkiyaProvider.ADAPTIVE_OFFSET, 18)

    def test_implausible_values_are_dropped_not_shown(self):
        """An empty field beats a confident-looking wrong one."""
        value, _confidence = document_parser.vote('license_plate', [
            ('\u0646\u0645', 90.0), ('eee ere', 80.0)])
        self.assertIsNone(value)

    def test_arabic_only_colour_is_recovered(self):
        parsed = document_parser.parse_text(
            "Vehicle Information\n\u0644\u0648\u0646 \u0627\u0644\u0645\u0631\u0643\u0628\u0629 \u0627\u0633\u0648\u062f\n")
        self.assertEqual(parsed[constants.FIELD_COLOR]['value'], 'Black')

    def test_plate_code_must_look_like_a_code(self):
        self.assertEqual(document_parser.plausibility('plate_code', 'ATS'), 0)
        self.assertEqual(document_parser.plausibility('plate_code', '21'), 3)

    def test_page_furniture_is_never_a_model(self):
        self.assertEqual(document_parser.plausibility(
            'model', 'j See to vehicle or'), 0)
        self.assertEqual(document_parser.plausibility(
            'model', 'MITSUBISHI PAJERO'), 2)
