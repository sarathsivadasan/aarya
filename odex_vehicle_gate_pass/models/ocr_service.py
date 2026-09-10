# -*- coding: utf-8 -*-
"""OCR service abstraction.

The implementation is deliberately replaceable.  Nothing in the UI knows how
text is extracted from an image - it only calls ``scan_registration_plate`` or
``scan_mulkiya``.  To plug a different engine in, inherit this model and
override ``_ocr_raw_text``.

Providers are configured in Settings (system parameters):

    odex_vehicle_gate_pass.ocr_provider   none | local | api
    odex_vehicle_gate_pass.ocr_endpoint   https://.../ocr
    odex_vehicle_gate_pass.ocr_api_key    secret - server side only

API keys are never sent to the browser.
"""

import base64
import binascii
import json
import logging
import re

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# UAE plates: emirate code + optional category + number, e.g. AUH/1/08830, DXB-A-12345
PLATE_RE = re.compile(r"\b([A-Z]{2,4})\s*[/\-\s]\s*([A-Z0-9]{1,3})\s*[/\-\s]\s*(\d{1,6})\b")
PLATE_SIMPLE_RE = re.compile(r"\b([A-Z]{2,4})\s*[/\-\s]\s*(\d{1,6})\b")
# ISO 3779 VIN: 17 chars, no I, O or Q
VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
ENGINE_RE = re.compile(r"\b[A-Z0-9]{6,20}\b")
YEAR_RE = re.compile(r"\b(19[7-9]\d|20[0-4]\d)\b")

EMIRATE_CODES = {
    "AUH": "Abu Dhabi", "AD": "Abu Dhabi", "DXB": "Dubai", "DU": "Dubai",
    "SHJ": "Sharjah", "SH": "Sharjah", "AJM": "Ajman", "AJ": "Ajman",
    "UAQ": "Umm Al Quwain", "RAK": "Ras Al Khaimah", "FUJ": "Fujairah",
}


class OdexOcrService(models.AbstractModel):
    _name = "odex.ocr.service"
    _description = "Gate Pass OCR Service"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @api.model
    def _get_param(self, key, default=""):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("odex_vehicle_gate_pass.%s" % key, default)
            or default
        )

    @api.model
    def get_status(self):
        """Return provider availability. Safe to call from JavaScript."""
        provider = self._get_param("ocr_provider", "none")
        message = ""
        available = True
        if provider == "none":
            available = False
            message = _("OCR service is not configured.")
        elif provider == "local":
            try:
                import pytesseract  # noqa: F401
                from PIL import Image  # noqa: F401
            except ImportError:
                available = False
                message = _(
                    "Local OCR selected but pytesseract/Pillow is not installed on the server."
                )
        elif provider == "api":
            if not self._get_param("ocr_endpoint"):
                available = False
                message = _("OCR provider is set to External API but no endpoint is configured.")
        else:
            available = False
            message = _("Unknown OCR provider: %s") % provider
        return {"provider": provider, "available": available, "message": message}

    # ------------------------------------------------------------------
    # Engine - override this method to plug another OCR engine in
    # ------------------------------------------------------------------
    @api.model
    def _ocr_raw_text(self, image_b64, hint="plate"):
        """Return the raw text found in a base64 image, or '' when unavailable."""
        status = self.get_status()
        if not status["available"]:
            raise UserError(status["message"])

        try:
            image_bytes = base64.b64decode(image_b64 or "", validate=False)
        except (binascii.Error, ValueError) as err:
            _logger.warning("Gate Pass OCR: invalid image payload (%s)", err)
            raise UserError(_("The captured image could not be read. Take the photo again."))
        if not image_bytes:
            raise UserError(_("No image was received. Take the photo again."))

        provider = status["provider"]
        _logger.info("Gate Pass OCR request: provider=%s hint=%s bytes=%s",
                     provider, hint, len(image_bytes))

        if provider == "local":
            text = self._ocr_local(image_bytes)
        else:
            text = self._ocr_api(image_bytes, hint)

        _logger.info("Gate Pass OCR response: provider=%s chars=%s", provider, len(text or ""))
        return text or ""

    @api.model
    def _ocr_local(self, image_bytes):
        import io

        import pytesseract
        from PIL import Image

        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = image.convert("L")
            return pytesseract.image_to_string(image)
        except Exception as err:  # noqa: BLE001 - any engine failure must stay a UserError
            _logger.exception("Gate Pass OCR: local engine failed")
            raise UserError(_("The OCR engine could not read this image (%s).") % err)

    @api.model
    def _ocr_api(self, image_bytes, hint):
        import requests

        endpoint = self._get_param("ocr_endpoint")
        api_key = self._get_param("ocr_api_key")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = "Bearer %s" % api_key
        payload = {
            "hint": hint,
            "image": base64.b64encode(image_bytes).decode("ascii"),
        }
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            raise UserError(_("The OCR service did not answer in time. Try again."))
        except requests.exceptions.RequestException as err:
            _logger.warning("Gate Pass OCR: API call failed (%s)", err)
            raise UserError(_("The OCR service could not be reached."))
        except (ValueError, json.JSONDecodeError):
            raise UserError(_("The OCR service returned an unreadable answer."))

        if isinstance(data, dict):
            for key in ("text", "raw_text", "ParsedText", "result"):
                if isinstance(data.get(key), str):
                    return data[key]
        return str(data)

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------
    @api.model
    def normalize_plate(self, value):
        if not value:
            return ""
        text = re.sub(r"\s+", " ", str(value)).strip().upper()
        text = text.replace("\\", "/")
        match = PLATE_RE.search(text)
        if match:
            return "%s/%s/%s" % (match.group(1), match.group(2), match.group(3))
        match = PLATE_SIMPLE_RE.search(text)
        if match:
            return "%s/%s" % (match.group(1), match.group(2))
        return re.sub(r"\s*([/\-])\s*", r"\1", text)

    @api.model
    def normalize_vin(self, value):
        if not value:
            return ""
        text = re.sub(r"[^A-Z0-9]", "", str(value).upper())
        match = VIN_RE.search(text)
        return match.group(0) if match else text

    # ------------------------------------------------------------------
    # Public API used by the UI
    # ------------------------------------------------------------------
    @api.model
    def scan_registration_plate(self, image):
        """Read a number plate. Returns {'registration_no': str, 'raw_text': str}."""
        text = self._ocr_raw_text(image, hint="plate")
        upper = text.upper()
        plate = ""
        match = PLATE_RE.search(upper)
        if match:
            plate = "%s/%s/%s" % (match.group(1), match.group(2), match.group(3))
        else:
            match = PLATE_SIMPLE_RE.search(upper)
            if match:
                plate = "%s/%s" % (match.group(1), match.group(2))
        if not plate:
            for token in re.findall(r"[A-Z0-9/\-]{4,}", upper):
                if any(char.isdigit() for char in token):
                    plate = self.normalize_plate(token)
                    break
        source = ""
        for code in EMIRATE_CODES:
            if plate.startswith(code + "/"):
                source = EMIRATE_CODES[code]
                break
        return {
            "registration_no": plate,
            "plate_source": source,
            "raw_text": text.strip(),
            "found": bool(plate),
        }

    @api.model
    def scan_mulkiya(self, image):
        """Read a UAE Mulkiya / registration card.

        Returns whatever could be read; missing keys are simply absent.
        """
        text = self._ocr_raw_text(image, hint="mulkiya")
        upper = text.upper()
        result = {"raw_text": text.strip()}

        vin_match = VIN_RE.search(re.sub(r"[^A-Z0-9\s]", " ", upper))
        if vin_match:
            result["chassis_no"] = vin_match.group(0)

        plate_match = PLATE_RE.search(upper) or PLATE_SIMPLE_RE.search(upper)
        if plate_match:
            result["registration_no"] = self.normalize_plate(plate_match.group(0))

        year_match = YEAR_RE.search(upper)
        if year_match:
            result["manufacturing_year"] = year_match.group(0)

        labels = {
            "engine_no": (r"ENGINE\s*(?:NO|NUMBER)?\s*[:.\-]?\s*([A-Z0-9\-]{5,20})",),
            "brand": (r"(?:MAKE|BRAND)\s*[:.\-]?\s*([A-Z][A-Z\s]{2,20})",),
            "vehicle_model": (r"MODEL\s*[:.\-]?\s*([A-Z0-9][A-Z0-9\s\-]{1,20})",),
            "color": (r"(?:COLOU?R)\s*[:.\-]?\s*([A-Z][A-Z\s]{2,15})",),
        }
        for key, patterns in labels.items():
            for pattern in patterns:
                match = re.search(pattern, upper)
                if match:
                    result[key] = match.group(1).strip()
                    break

        result["found"] = bool(result.get("chassis_no") or result.get("registration_no"))
        return result
