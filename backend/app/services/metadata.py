from datetime import datetime

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


def convert_to_degrees(value):
    """
    Convert GPS coordinates from
    degrees/minutes/seconds to decimal degrees.
    """

    degrees = float(value[0])
    minutes = float(value[1])
    seconds = float(value[2])

    return degrees + minutes / 60 + seconds / 3600


def extract_metadata(filepath):

    metadata = {
        "latitude": None,
        "longitude": None,
        "altitude": None,
        "captured_at": None
    }

    try:

        image = Image.open(filepath)

        exif = image.getexif()

        if not exif:
            return metadata

        decoded = {}

        for key, value in exif.items():

            decoded[TAGS.get(key, key)] = value

        # -----------------------------
        # GPS INFORMATION
        # -----------------------------

        gps_info = decoded.get("GPSInfo")

        if gps_info:

            gps = {}

            for key, value in gps_info.items():

                gps[GPSTAGS.get(key, key)] = value

            # Latitude and Longitude
            if "GPSLatitude" in gps and "GPSLongitude" in gps:

                latitude = convert_to_degrees(
                    gps["GPSLatitude"]
                )

                longitude = convert_to_degrees(
                    gps["GPSLongitude"]
                )

                # South latitude
                if gps.get("GPSLatitudeRef") == "S":
                    latitude = -latitude

                # West longitude
                if gps.get("GPSLongitudeRef") == "W":
                    longitude = -longitude

                metadata["latitude"] = latitude
                metadata["longitude"] = longitude

            # Altitude
            if "GPSAltitude" in gps:

                try:

                    metadata["altitude"] = float(
                        gps["GPSAltitude"]
                    )

                except (TypeError, ValueError):

                    pass

        # -----------------------------
        # CAPTURE DATE/TIME
        # -----------------------------

        date_string = decoded.get(
            "DateTimeOriginal"
        )

        if date_string:

            try:

                metadata["captured_at"] = datetime.strptime(
                    date_string,
                    "%Y:%m:%d %H:%M:%S"
                )

            except (ValueError, TypeError):

                pass

    except Exception as error:

        print(
            "Metadata extraction error:",
            error
        )

    return metadata