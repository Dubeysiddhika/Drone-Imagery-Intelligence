# Camera Calibration Investigation

## Objective

Determine whether camera calibration or intrinsics are available in local documentation or dataset metadata.

## Local documentation review

The dataset README and the Phase 1 report were reviewed. The local dataset documentation describes the metadata schema as:

- num
- filename
- date
- lat
- lon
- height
- Omega
- Kappa
- Phi1
- Phi2

There is no documented field for:

- focal length
- sensor width
- sensor height
- camera model
- intrinsic matrix
- calibration file
- lens distortion parameters

The dataset description explicitly indicates that latitude and longitude are the center coordinates of the drone image, and that Omega/Kappa/Phi1/Phi2 represent the drone pose. It does not provide the camera model or geometric calibration needed for a ground-truth footprint estimate.

## Dataset metadata review

The consolidated metadata export includes altitude and pose angles, but not camera intrinsics. The original CSV schema and the phase outputs preserve the source values without inventing missing parameters.

## Embedded image metadata review

Representative drone images from Flights 01, 02, 05, 09, and 10 were checked using Pillow. Their EXIF metadata was empty for the relevant camera fields. No camera make, model, focal length, or sensor metadata was present in the image files.

## Conclusion

Camera calibration is not available in the local documentation or embedded image metadata. The dataset provides drone center position and pose angles, but not the calibration data necessary to compute a reliable image footprint or determine exact overlap from first principles. This means any footprint-based filtering must remain conservative and not rely on invented assumptions.
