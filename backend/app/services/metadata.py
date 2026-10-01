from datetime import datetime
from typing import Any, cast

from PIL import Image
from PIL import ExifTags
from PIL.ExifTags import GPSTAGS, TAGS


def _as_float(value: Any) -> float:
    if isinstance(value, (tuple, list)) and len(value) == 2:
        numerator = float(value[0])
        denominator = float(value[1])
        if denominator == 0:
            raise ValueError("EXIF rational has a zero denominator")
        return numerator / denominator
    return float(cast(float, value))


def convert_to_degrees(value: Any) -> float:
    """Convert an EXIF degrees/minutes/seconds coordinate to decimal degrees."""
    if len(value) != 3:
        raise ValueError("GPS coordinates must contain degrees, minutes, seconds")

    degrees, minutes, seconds = (_as_float(part) for part in value)
    if not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError("GPS minutes and seconds must be in [0, 60)")
    return degrees + minutes / 60 + seconds / 3600


def _normalise_reference(value: Any) -> str | int | None:
    if isinstance(value, bytes):
        if len(value) == 1 and value[0] in (0, 1):
            return value[0]
        try:
            return value.decode("ascii").strip("\x00 ").upper()
        except UnicodeDecodeError:
            return None
    if isinstance(value, str):
        return value.strip("\x00 ").upper()
    if isinstance(value, int):
        return value
    return None


def extract_gps_values(gps: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    """Decode named EXIF GPS tags into signed decimal coordinates and altitude."""
    latitude = None
    longitude = None

    try:
        latitude_degrees = convert_to_degrees(gps["GPSLatitude"])
        latitude_ref = _normalise_reference(gps.get("GPSLatitudeRef"))
        if latitude_ref in {"N", "S"} and latitude_degrees <= 90:
            latitude = -latitude_degrees if latitude_ref == "S" else latitude_degrees
    except (KeyError, TypeError, ValueError, OverflowError):
        pass

    try:
        longitude_degrees = convert_to_degrees(gps["GPSLongitude"])
        longitude_ref = _normalise_reference(gps.get("GPSLongitudeRef"))
        if longitude_ref in {"E", "W"} and longitude_degrees <= 180:
            longitude = -longitude_degrees if longitude_ref == "W" else longitude_degrees
    except (KeyError, TypeError, ValueError, OverflowError):
        pass

    altitude = None
    if "GPSAltitude" in gps:
        try:
            altitude = _as_float(gps["GPSAltitude"])
            altitude_ref = _normalise_reference(gps.get("GPSAltitudeRef"))
            if altitude_ref == 1 or altitude_ref == "1":
                altitude = -altitude
            elif altitude_ref not in (None, 0, "0"):
                altitude = None
        except (TypeError, ValueError, OverflowError):
            pass

    return latitude, longitude, altitude


def _decode_text(value: Any) -> str | None:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="replace")
        except Exception:
            return None
    if value is None:
        return None
    text = str(value).strip("\x00 ")
    return text or None


def _parse_capture_time(value: Any) -> datetime | None:
    date_string = _decode_text(value)
    if not date_string:
        return None
    try:
        return datetime.strptime(date_string[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def extract_metadata(filepath: str) -> dict[str, Any]:
    """Extract available EXIF fields and image dimensions without inventing values."""
    metadata: dict[str, Any] = {
        "latitude": None,
        "longitude": None,
        "altitude": None,
        "captured_at": None,
        "camera_make": None,
        "camera_model": None,
        "width": None,
        "height": None,
        "exif_available": False,
    }

    try:
        with Image.open(filepath) as image:
            metadata["width"], metadata["height"] = image.size
            exif = image.getexif()
            metadata["exif_available"] = bool(exif)
            if not exif:
                return metadata

            decoded = {
                str(TAGS.get(tag, tag)): value
                for tag, value in exif.items()
            }
            metadata["camera_make"] = _decode_text(decoded.get("Make"))
            metadata["camera_model"] = _decode_text(decoded.get("Model"))

            try:
                exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            except (AttributeError, KeyError, TypeError):
                exif_ifd = {}
            exif_decoded = {
                str(TAGS.get(tag, tag)): value
                for tag, value in exif_ifd.items()
            }
            capture_value = (
                exif_decoded.get("DateTimeOriginal")
                or exif_decoded.get("DateTimeDigitized")
                or decoded.get("DateTime")
            )
            metadata["captured_at"] = _parse_capture_time(capture_value)

            try:
                gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
            except (AttributeError, KeyError, TypeError):
                gps_ifd = {}
            gps = {
                str(GPSTAGS.get(tag, tag)): value
                for tag, value in gps_ifd.items()
            }
            (
                metadata["latitude"],
                metadata["longitude"],
                metadata["altitude"],
            ) = extract_gps_values(gps)
    except (OSError, ValueError, TypeError):
        return metadata

    return metadata