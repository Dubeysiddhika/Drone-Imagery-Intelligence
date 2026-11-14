# Footprint Feasibility Report

## Objective

Evaluate whether image-footprint estimation is feasible without inventing camera parameters.

## Available information

The dataset includes:

- image center latitude/longitude
- altitude (height)
- drone pose angles: Omega, Kappa, Phi1, Phi2
- image dimensions in pixels for the drone images

The dataset does not include:

- focal length
- sensor width or height
- principal point
- distortion coefficients
- calibration file
- terrain/elevation model
- camera make or model

## Why the footprint cannot be recovered reliably

A photogrammetric footprint estimate requires a projective model of the camera. In practice, an estimate requires at least:

- focal length in mm
- sensor size in mm
- principal point
- image resolution
- camera pose
- a ground elevation or terrain model

Without focal length and sensor dimensions, the ground footprint at a given altitude cannot be determined. A center GPS coordinate alone is not equivalent to the full image extent, and using it as a proxy would be a modeling assumption rather than a verified measurement.

## Conclusion

Image-footprint estimation is not feasible from the current dataset without explicit calibration data and a documented terrain model. This is consistent with the Phase 2A conclusion and is not an issue that can be resolved by assumption alone.
