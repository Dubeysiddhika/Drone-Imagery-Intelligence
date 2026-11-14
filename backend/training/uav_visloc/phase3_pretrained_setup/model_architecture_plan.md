# Phase 3A Model Architecture Plan

## Overview

This phase targets a pretrained, CPU-only visual localization pipeline without custom training or fine-tuning.

The pipeline has three stages:

1. Global retrieval using DINOv2 descriptors.
2. Local matching using SuperPoint + LightGlue.
3. Geometric verification and geospatial mapping using OpenCV and Rasterio.

## 1) DINOv2 global descriptors

DINOv2 will be used as the global image encoder for:
- drone image descriptor extraction
- satellite tile descriptor extraction
- cosine-similarity search over a cached tile descriptor bank

The expected workflow is:
- preprocess the drone image into the DINOv2 input format
- preprocess each satellite tile crop onto the same feature extraction pipeline
- extract a fixed-length descriptor vector from the final hidden representation
- store a descriptor index for each tile or tile crop

This stage is designed for candidate retrieval rather than final localization. It narrows the search to the most likely satellite tiles.

## 2) Satellite tile descriptor caching

To keep the retrieval stage lightweight and deterministic:
- precompute descriptors for each georeferenced tile or a small set of tile crops
- save descriptor vectors to disk in a compact format
- map each descriptor row back to the tile ID, flight number, and geospatial bounds
- use a cache to avoid recomputing embeddings for the same tile on each inference pass

This reduces CPU load and avoids repeatedly encoding large satellite imagery.

## 3) Cosine similarity and top-K retrieval

Once the drone image descriptor is computed, compute cosine similarity against the cached tile descriptor matrix. The top-K most similar satellite tiles form the candidate set.

Key points:
- use cosine similarity or normalized dot product for DINOv2 feature vectors
- keep K small for the initial CPU prototype, for example 3 to 10 tiles
- reject tiles that are not geographically valid candidates based on the validated Phase 2A coverage table

This stage does not establish a final match; it only produces the likely map regions.

## 4) SuperPoint local keypoints

SuperPoint is used on the drone image and on the shortlisted satellite tiles.

The local-feature workflow is:
- detect keypoints and descriptors on the drone image
- detect keypoints and descriptors on each candidate tile
- optionally resize the candidate tiles to a more manageable crop size while keeping aspect ratio stable
- normalize image inputs to the format expected by the SuperPoint implementation

The pretrained SuperPoint weights are not custom-trained here; they are loaded through the official model source or the package-provided checkpoint path.

## 5) LightGlue descriptor matching

LightGlue is applied to the extracted SuperPoint descriptors for each shortlist pair.

The matcher takes the feature sets from the drone image and the candidate map tile and returns a set of matched keypoints. This stage is the core geometric matcher and is intended to provide evidence of local visual correspondence.

Important constraints:
- only use LightGlue on a small candidate set, not on all satellite tiles
- retain a confidence threshold and minimum matched-point count
- do not treat a match as valid just because the feature count is high

## 6) OpenCV geometric verification

The matched keypoints are fed into OpenCV for geometric verification.

Typical steps:
- estimate a homography or affine transform from matched points
- run RANSAC to reject outliers
- check inlier ratio and geometric consistency
- reject weak or ambiguous matches

The output is a confidence score based on inlier count, not just raw match count.

## 7) Rasterio geospatial coordinate mapping

Once the local match is accepted, geospatial mapping is applied through the georeferenced tile metadata produced in Phase 2A.

The process:
- use the matched geometric transform to map image-space correspondences back into tile coordinates
- interpret the tile coordinate space using the stored Rasterio transform and CRS
- convert matched pixel locations to lon/lat or to a local geospatial coordinate frame
- preserve the original EPSG:4326 metadata and tile bounds

This stage ensures the final candidate is interpreted in geographic space rather than as a purely visual match.

## 8) Pretrained weights and downloads

The only components that require downloaded pretrained weights are:
- DINOv2 backbone weights
- SuperPoint weights used by the local extractor
- LightGlue weights if the library does not bundle them locally

No training, fine-tuning, or custom checkpoint generation is part of this phase.

The dependency plan is to install the official inference packages and then load these pretrained checkpoint files from the model hub when the inference test is executed.

## 9) Initial system design

For the first CPU-only prototype:
- use DINOv2 as the global retrieval stage
- restrict retrieval to the top 5 to 10 candidates
- run SuperPoint + LightGlue only on the shortlist
- use OpenCV RANSAC to verify geometric consistency
- record the candidate tile ID, match count, and inlier score in the output log

This is a lightweight and defensible first implementation without custom training.
