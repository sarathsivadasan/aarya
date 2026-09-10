# -*- coding: utf-8 -*-
"""Local Tesseract provider - fully offline, no API, no credentials.

Nothing leaves the server: the images are read by the Tesseract engine
installed next to Odoo and parsed by ``services.document_parser``.

Requirements on the server::

    sudo apt-get install tesseract-ocr tesseract-ocr-ara
    pip3 install pytesseract

Accuracy is lower than a vision model on a photographed bilingual card,
especially on the chassis number. Every value stays editable and low scores
are flagged, which is exactly what the verification step is for.
"""

import base64
import io
import logging
import statistics

from ..services import document_parser
from .base_provider import (
    MulkiyaOCRError,
    MulkiyaOCRProvider,
    MulkiyaOCRQuality,
    register_provider,
)

_logger = logging.getLogger(__name__)


class _EnoughRead(Exception):
    """Internal signal: the union already covers the card."""


try:
    import pytesseract
    from pytesseract import Output
except ImportError:  # pragma: no cover - optional dependency
    pytesseract = None
    Output = None

try:
    from PIL import Image, ImageFilter, ImageOps
except ImportError:  # pragma: no cover
    Image = None

try:
    import numpy
except ImportError:  # pragma: no cover - numpy ships with Odoo
    numpy = None


@register_provider
class TesseractMulkiyaProvider(MulkiyaOCRProvider):

    code = 'tesseract'
    label = 'Tesseract (Local, No API)'
    sequence = 40
    requires_credentials = False
    #: Tesseract reports per-word confidence, aggregated per field below.
    supports_confidence = True
    #: Resolution is the single biggest factor for local OCR, so the service
    #: hands this provider the original image instead of a downscaled copy.
    image_max_dimension = 0

    #: Languages passed to Tesseract. Override in Model / Engine.
    default_model = 'eng+ara'

    #: Below this the document is considered unreadable.
    MIN_WORDS = 6

    #: Page segmentation modes tried in order. A Mulkiya is a bordered table,
    #: and the mode that copes with it varies with how the photo was framed:
    #: 6 (uniform block) silently returns almost nothing on a ruled card,
    #: while 4 and 3 handle the columns. The best result wins.
    PSM_CANDIDATES = ('6', '4', '3', '11')

    #: Tried in order. English first: the Arabic pack frequently turns a clean
    #: English row into mojibake, while English alone treats the Arabic label
    #: as noise and leaves the value readable.
    LANGUAGE_CANDIDATES = ('eng', None)

    #: Stop once the vote covers this many cells: the card holds 11.
    ENOUGH_FIELDS = 9
    #: Coverage from the untouched image that makes cropping unnecessary.
    ENOUGH_RAW_FIELDS = 7
    #: Coverage after the adaptive rendering that makes the others unnecessary.
    ENOUGH_RENDER_FIELDS = 3

    #: Cropping to the card and straightening it were measured across five
    #: cards: they rescue some photos and mislead the engine on others, for no
    #: net gain and a quarter more runtime. Kept, but off by default - set it
    #: on a subclass if your photos routinely include a lot of background.
    USE_TREATMENTS = False

    #: Resolving disagreements between passes by plausibility was worth three
    #: extra fields across the same five cards, at no cost in time.
    USE_VOTING = True

    #: Glyph box height Tesseract is happiest with. Scaling is derived from
    #: the image rather than fixed: blindly upscaling a small picture to a
    #: fixed width blurs the strokes and reads *worse* than a gentler factor.
    TARGET_GLYPH_HEIGHT = 30
    MIN_SCALE = 1.0
    MAX_SCALE = 4.0
    #: Never hand Tesseract more than this many pixels on the long edge.
    MAX_LONG_EDGE = 3600

    def extract(self, front_image, back_image):
        if pytesseract is None or Image is None:  # pragma: no cover
            raise MulkiyaOCRError(
                "Local OCR is not available on this server. Please install "
                "tesseract-ocr, tesseract-ocr-ara and the pytesseract library.",
                technical="pytesseract or Pillow missing")
        self._check_engine()

        front_parsed, front_text, front_conf = self._read_side(front_image, 'front')
        back_parsed, back_text, back_conf = self._read_side(back_image, 'back')
        self.raw_response = {
            'provider': self.code,
            'languages': self.api_model,
            'front_text': front_text,
            'back_text': back_text,
            'front_confidence': front_conf,
            'back_confidence': back_conf,
        }

        if not front_text.strip() and not back_text.strip():
            raise MulkiyaOCRQuality(
                "No text could be read from the images.\n\n"
                "Please upload a sharper, well lit picture of the Mulkiya, "
                "filling the frame and avoiding glare.")

        merged = document_parser.merge_sides(front_parsed, back_parsed)
        if not merged:
            raise MulkiyaOCRQuality(
                "The image quality is insufficient to read the Mulkiya.\n\n"
                "Please upload a clearer image.")

        # Tesseract gives word level confidence; attribute the page score to
        # every field it produced rather than inventing per-field precision.
        page_confidence = int(round(max(front_conf, back_conf)))
        for entry in merged.values():
            entry.setdefault('confidence', page_confidence)
        return merged

    # ------------------------------------------------------------------
    def _check_engine(self):
        try:
            pytesseract.get_tesseract_version()
        except Exception as exc:
            raise MulkiyaOCRError(
                "The Tesseract engine is not installed on this server. "
                "Please ask your administrator to install it.",
                technical=str(exc)) from exc

    def _read_side(self, image, side):
        """OCR one side several ways and union what each pass understood.

        No single configuration reads a whole card: the language pack changes
        which rows survive, the segmentation mode changes which cells are
        found, and cropping or straightening helps some photos while hurting
        others. Every treatment is therefore a *candidate*, never a
        replacement, and the parsed fields are merged. A pass that rescues one
        cell still earns its place.
        """
        base64_str, _mimetype = image
        raw = base64.b64decode(base64_str)
        languages = self._languages()

        ballots = {}
        texts = []
        best_text, best_confidence, best_score = '', 0.0, -1

        def covered():
            """Cells read *convincingly*, not merely filled with something."""
            return sum(1 for key, votes in ballots.items()
                       if any(document_parser.plausibility(key, value) >= 2
                              for value, _confidence in votes))

        try:
            with Image.open(io.BytesIO(raw)) as opened:
                grayscale = opened.convert('L')
                for name, variant in self._image_variants(grayscale):
                    if name != 'raw' and covered() >= self.ENOUGH_RAW_FIELDS:
                        # The plain image already read well; further treatment
                        # would only add noisy votes and time.
                        break
                    scale = self._measure_scale(variant, languages[0])
                    prepared = self._preprocess(variant, scale)
                    # Adaptive thresholding is decisively the best rendering
                    # for a foil card, so it goes first and the others are
                    # only tried when it left cells unread.
                    renderings = [('%s-adaptive' % name,
                                   lambda p=prepared: self._adaptive(p))]
                    renderings += [
                        (name, lambda p=prepared: p),
                        ('%s-otsu' % name, lambda p=prepared: self._binarize(p)),
                    ]
                    for render_name, build in renderings:
                        if render_name.endswith('-adaptive') is False and \
                                covered() >= self.ENOUGH_RENDER_FIELDS:
                            break
                        rendering = build()
                        active = languages if covered() < 3 else languages[:1]
                        for language in active:
                            for psm in self.PSM_CANDIDATES[:3]:
                                text, confidence, words = self._run(
                                    rendering, language, psm)
                                if not words:
                                    continue
                                texts.append(text)
                                parsed = document_parser.parse_text(text,
                                                                    side=side)
                                if len(parsed) > best_score:
                                    best_text = text
                                    best_confidence = confidence
                                    best_score = len(parsed)
                                for key, entry in parsed.items():
                                    ballots.setdefault(key, []).append(
                                        (entry.get('value'), confidence))
                                _logger.debug(
                                    "Mulkiya Tesseract %s: %s/%s/psm%s -> "
                                    "%s words, %s fields", side, render_name,
                                    language, psm, words, len(parsed))
                                if covered() >= self.ENOUGH_FIELDS:
                                    raise _EnoughRead()
        except _EnoughRead:
            pass
        except Exception as exc:
            raise MulkiyaOCRError(
                "Unable to process the Mulkiya. Please try again.",
                technical='%s side: %s' % (side, exc)) from exc

        # Resolve the disagreements between passes.
        union = {}
        for key, votes in ballots.items():
            if self.USE_VOTING:
                value, confidence = document_parser.vote(key, votes)
            else:
                value, confidence = votes[0]
            if value:
                union[key] = {'value': value, 'confidence': int(confidence or 0)}

        # A model designation needs a whole row in view, so it is recovered
        # from every pass: a row lost by one treatment is often intact in
        # another.
        for text in texts:
            document_parser._recover_model(union, text)

        _logger.info("Mulkiya Tesseract: %s side, %s passes, %s fields, best "
                     "text at %.1f%%", side, len(texts), len(union),
                     best_confidence)
        return union, best_text, best_confidence

    def _languages(self):
        configured = self.api_model or self.default_model
        languages = []
        for language in self.LANGUAGE_CANDIDATES:
            language = configured if language is None else language
            if language not in languages:
                languages.append(language)
        return languages

    def _image_variants(self, grayscale):
        """Yield treatments lazily, cheapest first.

        Cropping to the card and straightening it rescue a photo taken on a
        desk, but they cost time and can mislead the engine on a picture that
        was already square and full frame. So they are only computed when the
        untouched image has left the card poorly covered.
        """
        yield 'raw', grayscale
        if not self.USE_TREATMENTS:
            return
        cropped = self._detect_card(grayscale)
        if cropped.size != grayscale.size:
            yield 'crop', cropped
        deskewed = self._deskew(cropped)
        if deskewed.size != cropped.size:
            yield 'deskew', deskewed

    def _run(self, image, language, psm):
        data = pytesseract.image_to_data(
            image, lang=language, config='--oem 1 --psm %s' % psm,
            output_type=Output.DICT)
        return self._rebuild_layout(data)

    #: A crop is only trusted when the detected card covers this much of the
    #: frame: anything smaller is probably a reflection or a shadow.
    MIN_CARD_AREA_RATIO = 0.20
    MAX_CARD_AREA_RATIO = 0.99

    def _detect_card(self, img):
        """Crop away the desk, hand or table around the card.

        A photographed Mulkiya usually fills only part of the frame. The
        background costs resolution where it matters and adds texture the
        engine tries to read, so it is removed before anything else.
        """
        if numpy is None:
            return img
        try:
            small = img.resize((400, max(1, int(400 * img.height / img.width))),
                               Image.BILINEAR)
            data = numpy.asarray(small, dtype=numpy.float32)
            threshold = self._otsu_threshold(small)
            mask = data > threshold

            rows = self._longest_run(mask.mean(axis=1) > 0.45)
            columns = self._longest_run(mask.mean(axis=0) > 0.45)
            if not rows or not columns:
                return img
            scale_x = img.width / float(small.width)
            scale_y = img.height / float(small.height)
            left = int(columns[0] * scale_x)
            right = int((columns[1] + 1) * scale_x)
            top = int(rows[0] * scale_y)
            bottom = int((rows[1] + 1) * scale_y)

            area = (right - left) * (bottom - top)
            ratio = area / float(img.width * img.height)
            if not self.MIN_CARD_AREA_RATIO <= ratio <= self.MAX_CARD_AREA_RATIO:
                return img
            # A little margin: the border rule carries table structure.
            margin_x = int((right - left) * 0.02)
            margin_y = int((bottom - top) * 0.02)
            return img.crop((max(0, left - margin_x), max(0, top - margin_y),
                             min(img.width, right + margin_x),
                             min(img.height, bottom + margin_y)))
        except Exception:  # pragma: no cover - defensive
            _logger.debug("Mulkiya Tesseract: card detection failed",
                          exc_info=True)
            return img

    @staticmethod
    def _longest_run(flags):
        """Return ``(start, end)`` of the longest True run, or None."""
        best = current_start = None
        best_length = 0
        for index, flag in enumerate(flags):
            if flag:
                if current_start is None:
                    current_start = index
            elif current_start is not None:
                if index - current_start > best_length:
                    best_length = index - current_start
                    best = (current_start, index - 1)
                current_start = None
        if current_start is not None and len(flags) - current_start > best_length:
            best = (current_start, len(flags) - 1)
        return best

    def _otsu_threshold(self, img):
        histogram = img.histogram()
        total = sum(histogram)
        if not total:
            return 128
        sum_total = sum(index * count for index, count in enumerate(histogram))
        sum_background = weight_background = 0.0
        best_variance, threshold = -1.0, 128
        for index in range(256):
            weight_background += histogram[index]
            if weight_background == 0:
                continue
            weight_foreground = total - weight_background
            if weight_foreground == 0:
                break
            sum_background += index * histogram[index]
            mean_b = sum_background / weight_background
            mean_f = (sum_total - sum_background) / weight_foreground
            variance = weight_background * weight_foreground * (mean_b - mean_f) ** 2
            if variance > best_variance:
                best_variance, threshold = variance, index
        return threshold

    def _deskew(self, img):
        """Straighten a card photographed at an angle.

        Text rows produce sharp peaks in the horizontal projection only when
        they are level, so the rotation whose projection varies most is the
        one that squares up the document.
        """
        if numpy is None:
            return img
        try:
            probe = img.resize((360, max(1, int(360 * img.height / img.width))),
                               Image.BILINEAR)
            threshold = self._otsu_threshold(probe)
            best_angle, best_score = 0.0, -1.0
            for step in range(-8, 9):
                angle = step * 0.75
                rotated = probe.rotate(angle, resample=Image.BILINEAR,
                                       fillcolor=255)
                data = numpy.asarray(rotated, dtype=numpy.float32)
                ink = (data < threshold).sum(axis=1).astype(numpy.float32)
                score = float(numpy.var(numpy.diff(ink)))
                if score > best_score:
                    best_score, best_angle = score, angle
            if abs(best_angle) < 0.7:
                return img
            _logger.info("Mulkiya Tesseract: deskewing by %.2f degrees",
                         best_angle)
            return img.rotate(best_angle, resample=Image.BICUBIC, expand=True,
                              fillcolor=255)
        except Exception:  # pragma: no cover - defensive
            return img

    def _measure_scale(self, img, language):
        """Work out how much to enlarge, from the printed text height."""
        try:
            data = pytesseract.image_to_data(
                img, lang=language, config='--oem 1 --psm 6',
                output_type=Output.DICT)
        except Exception:  # pragma: no cover - defensive
            return 2.0
        heights = [data['height'][index]
                   for index in range(len(data.get('text') or []))
                   if (data['text'][index] or '').strip()]
        if not heights:
            return 2.0
        heights.sort()
        median = heights[len(heights) // 2] or 1
        scale = float(self.TARGET_GLYPH_HEIGHT) / median
        scale = max(self.MIN_SCALE, min(self.MAX_SCALE, scale))
        longest = max(img.size)
        if longest * scale > self.MAX_LONG_EDGE:
            scale = float(self.MAX_LONG_EDGE) / longest
        return round(scale, 2)

    def _preprocess(self, img, scale=1.0):
        """Grayscale, scale to the measured target, autocontrast, sharpen."""
        img = img.convert('L')
        if scale and abs(scale - 1.0) > 0.05:
            width, height = img.size
            img = img.resize((max(1, int(width * scale)),
                              max(1, int(height * scale))), Image.LANCZOS)
        img = ImageOps.autocontrast(img)
        return img.filter(ImageFilter.SHARPEN)

    #: Local-mean thresholding parameters. The radius must be comfortably
    #: larger than a glyph so the local mean tracks the background, not the
    #: ink; the offset is how much darker than its surroundings a pixel must
    #: be to count as ink.
    ADAPTIVE_RADIUS = 40
    ADAPTIVE_OFFSET = 18

    def _adaptive(self, img, radius=None, offset=None):
        """Threshold each pixel against its own neighbourhood.

        A Mulkiya is printed on gold foil with a guilloche pattern behind the
        text and it reflects light unevenly. A single global threshold either
        keeps the pattern or loses the ink; comparing every pixel with the
        local mean removes the background and the sheen together. Measured on
        a real card, this is the difference between reading two of the five
        key values and reading all five.
        """
        if numpy is None:
            return img
        try:
            radius = self.ADAPTIVE_RADIUS if radius is None else radius
            offset = self.ADAPTIVE_OFFSET if offset is None else offset
            blurred = img.filter(ImageFilter.BoxBlur(radius))
            source = numpy.asarray(img, dtype=numpy.int16)
            local_mean = numpy.asarray(blurred, dtype=numpy.int16)
            binary = numpy.where(source < local_mean - offset, 0, 255)
            return Image.fromarray(binary.astype(numpy.uint8))
        except Exception:  # pragma: no cover - defensive
            _logger.debug("Mulkiya Tesseract: adaptive threshold failed",
                          exc_info=True)
            return img

    def _binarize(self, img):
        """Otsu threshold - recovers text on a glossy or unevenly lit card."""
        histogram = img.histogram()
        total = sum(histogram)
        if not total:
            return img
        sum_total = sum(index * count for index, count in enumerate(histogram))
        sum_background = 0.0
        weight_background = 0.0
        best_variance = -1.0
        threshold = 128
        for index in range(256):
            weight_background += histogram[index]
            if weight_background == 0:
                continue
            weight_foreground = total - weight_background
            if weight_foreground == 0:
                break
            sum_background += index * histogram[index]
            mean_background = sum_background / weight_background
            mean_foreground = (sum_total - sum_background) / weight_foreground
            variance = (weight_background * weight_foreground *
                        (mean_background - mean_foreground) ** 2)
            if variance > best_variance:
                best_variance = variance
                threshold = index
        return img.point(lambda value: 255 if value > threshold else 0, mode='L')

    def _rebuild_layout(self, data):
        """Rebuild text lines, preserving the column gaps.

        Returns ``(text, mean_confidence, word_count)``.

        The parser splits a row into cells on two or more spaces, so the
        horizontal gaps between words carry meaning and must survive.
        """
        lines = {}
        confidences = []
        count = len(data.get('text') or [])
        for index in range(count):
            text = (data['text'][index] or '').strip()
            if not text:
                continue
            try:
                confidence = float(data['conf'][index])
            except (TypeError, ValueError):
                confidence = -1
            if confidence < 0:
                continue
            key = (data['block_num'][index], data['par_num'][index],
                   data['line_num'][index])
            lines.setdefault(key, []).append({
                'text': text,
                'left': data['left'][index],
                'width': data['width'][index],
                'top': data['top'][index],
                'height': data['height'][index],
            })
            confidences.append(confidence)

        if len(confidences) < self.MIN_WORDS:
            return '', 0.0, len(confidences)

        rendered = []
        for key in sorted(lines, key=lambda k: min(w['top'] for w in lines[k])):
            words = sorted(lines[key], key=lambda word: word['left'])
            char_width = statistics.median(
                [max(1, word['width'] / max(1, len(word['text'])))
                 for word in words])
            parts = [words[0]['text']]
            for previous, word in zip(words, words[1:]):
                gap = word['left'] - (previous['left'] + previous['width'])
                # A gap wider than ~2.5 characters is a column break.
                parts.append('   ' if gap > char_width * 2.5 else ' ')
                parts.append(word['text'])
            rendered.append(''.join(parts))

        page_confidence = statistics.mean(confidences) if confidences else 0.0
        return '\n'.join(rendered), page_confidence, len(confidences)
