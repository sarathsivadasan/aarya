# -*- coding: utf-8 -*-
"""Server side image validation and preparation (sections 38 and 39)."""

import base64
import binascii
import io
import logging

from odoo import _
from odoo.exceptions import UserError

from . import constants

_logger = logging.getLogger(__name__)

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow ships with Odoo
    Image = None


class MulkiyaImageError(UserError):
    """Raised when an uploaded image cannot be used for OCR."""


def decode(value):
    """Return raw bytes for a base64 (str/bytes) image field value."""
    if not value:
        return b''
    if isinstance(value, (bytes, bytearray)) and not _looks_base64(value):
        return bytes(value)
    try:
        return base64.b64decode(value)
    except (binascii.Error, ValueError) as exc:
        raise MulkiyaImageError(_("The uploaded file could not be read.")) from exc


def _looks_base64(value):
    sample = bytes(value[:16])
    return all(chr(c) in
               'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\r\n'
               for c in sample)


def detect_mimetype(raw):
    """Detect the mimetype from magic bytes. Never trust the client filename."""
    if not raw:
        return None
    if raw.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'image/webp'
    return None


def validate(value, label, max_file_mb=constants.DEFAULT_MAX_FILE_MB):
    """Validate a base64 image field value. Returns the decoded bytes."""
    raw = decode(value)
    if not raw:
        raise MulkiyaImageError(_("Please upload the %s side of the Mulkiya.", label))

    mimetype = detect_mimetype(raw)
    if mimetype not in constants.SUPPORTED_MIMETYPES:
        raise MulkiyaImageError(_(
            "Unsupported file type for the %s side. "
            "Please upload a JPEG, PNG or WEBP image.", label))

    size_mb = len(raw) / (1024.0 * 1024.0)
    if max_file_mb and size_mb > max_file_mb:
        raise MulkiyaImageError(_(
            "The %(side)s image is too large (%(size).1f MB). "
            "The maximum allowed size is %(max)s MB.",
            side=label, size=size_mb, max=max_file_mb))
    return raw


def prepare(value, label, max_dimension=constants.DEFAULT_MAX_DIMENSION,
            max_file_mb=constants.DEFAULT_MAX_FILE_MB, quality=88):
    """Validate, downscale and re-encode an image before sending it to a provider.

    Large originals are never forwarded untouched: they are expensive, slow and
    frequently rejected by OCR providers. Downscaling is capped so that the
    document text stays readable.

    :return: tuple ``(base64_str, mimetype)``
    """
    raw = validate(value, label, max_file_mb=max_file_mb)
    mimetype = detect_mimetype(raw)

    if Image is None:
        return base64.b64encode(raw).decode(), mimetype

    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = _apply_exif_orientation(img)
            width, height = img.size
            longest = max(width, height)
            needs_resize = max_dimension and longest > max_dimension
            if not needs_resize and mimetype == 'image/jpeg':
                # Already a reasonable JPEG, forward as-is.
                return base64.b64encode(raw).decode(), mimetype
            if needs_resize:
                ratio = float(max_dimension) / float(longest)
                img = img.resize(
                    (max(1, int(width * ratio)), max(1, int(height * ratio))),
                    Image.LANCZOS,
                )
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode(), 'image/jpeg'
    except MulkiyaImageError:
        raise
    except Exception:  # pragma: no cover - defensive
        _logger.warning("Mulkiya: could not post-process the %s image, "
                        "sending the original.", label, exc_info=True)
        return base64.b64encode(raw).decode(), mimetype


def _apply_exif_orientation(img):
    """Rotate the image according to its EXIF orientation tag when present."""
    try:
        exif = img.getexif()
        orientation = exif.get(274) if exif else None
    except Exception:  # pragma: no cover - defensive
        orientation = None
    if orientation == 3:
        return img.rotate(180, expand=True)
    if orientation == 6:
        return img.rotate(270, expand=True)
    if orientation == 8:
        return img.rotate(90, expand=True)
    return img


#: Below this the printed text is too small for any OCR engine to be reliable.
MIN_USEFUL_LONG_EDGE = 1200


def measure(value):
    """Return ``(width, height)`` of a base64 image, or ``(0, 0)``."""
    if Image is None:  # pragma: no cover
        return (0, 0)
    try:
        with Image.open(io.BytesIO(decode(value))) as img:
            return img.size
    except Exception:  # pragma: no cover - defensive
        return (0, 0)


def resolution_warning(front_value, back_value):
    """Warn when the uploaded pictures are too small to read accurately.

    Resolution is the single biggest driver of OCR accuracy. A card filling a
    600px frame leaves roughly 15px of glyph height, which is under half of
    what an OCR engine needs, and no amount of upscaling recovers detail that
    was never captured.
    """
    sizes = []
    for label, value in ((_("front"), front_value), (_("back"), back_value)):
        width, height = measure(value)
        if width and max(width, height) < MIN_USEFUL_LONG_EDGE:
            sizes.append('%s (%sx%s)' % (label, width, height))
    if not sizes:
        return None
    return _(
        "The uploaded images are small: %s. Text this size is hard to read "
        "accurately.\n\nFor best results photograph the Mulkiya so it fills "
        "the frame, in even light and without flash, at your camera's normal "
        "resolution.", ', '.join(sizes))
