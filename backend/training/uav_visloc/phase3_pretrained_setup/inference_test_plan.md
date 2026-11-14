# Phase 3A Inference Test Plan

## Goal

Prepare a lightweight inference validation procedure for the pretrained DINOv2 + SuperPoint + LightGlue pipeline without custom training or fine-tuning.

The test is intentionally small and uses representative examples from geographically important flights. It does not yet implement the full production pipeline.

## Representative image set

Use one representative drone image from each of the following flights:
- Flight 01
- Flight 05
- Flight 09
- Flight 02
- Flight 10

These flights were selected because they cover:
- a typical non-uncertain region
- a validation-type coverage location
- a tile-rich flight with a coherent geospatial layout
- a held-out test-type flight region

## Test workflow

### Step 1: load a drone image

For each selected flight:
- load a single drone image from the consolidated metadata set
- retain the original source metadata and file name
- note the flight number and matched geographic region

### Step 2: load relevant satellite candidates

Select the candidate satellite map candidates based on:
- the drone GPS center
- the Phase 2A coverage validation result
- the relevant tile metadata produced in Phase 2A

The shortlist should be derived from the geospatially valid candidates only. The uncertain out-of-coverage cases must remain excluded.

### Step 3: extract global descriptors

For the chosen drone image and the candidate satellite tiles:
- preprocess with the DINOv2 input pipeline
- compute the global descriptor for each image
- compute cosine similarity between the drone descriptor and each candidate tile descriptor

This step produces a ranked list of likely satellite tiles.

### Step 4: retrieve top candidates

For each drone image:
- retain the top K candidates, using a small value such as K = 3 to 10
- ensure the shortlist is limited to valid candidate tiles
- record the ranking and similarity score for each candidate

### Step 5: run local matching

For the top-K candidates only:
- detect keypoints and descriptors with SuperPoint
- match local features with LightGlue
- record the number of matches and the confidence of the matcher

### Step 6: verify geometry

Run OpenCV geometric verification:
- estimate a homography or affine transform using RANSAC
- compute inlier count and inlier ratio
- reject weak or degenerate matches

### Step 7: report the final result

Output a result record containing:
- flight number
- drone image filename
- candidate tile ID
- top-K rank
- descriptor similarity score
- feature match count
- inlier count
- RANSAC status
- accepted or rejected as a valid local match

## Acceptance criteria

A candidate is considered promising only if it satisfies all of the following:
- the candidate tile is geospatially valid
- the drone image is not an uncertain case
- DINOv2 retrieval ranks the correct tile highly
- LightGlue generates a credible local match
- geometric verification passes with enough inliers

A result should be rejected or marked as uncertain if:
- the tile is in an invalid coverage region
- the match count is too low
- the inlier ratio or transform is unstable
- the map candidate is ambiguous among multiple potential tiles

## Test reporting

The final test report should include:
- which representative drone images were used
- which candidate tiles were shortlisted
- whether DINOv2 retrieval chose the expected tile
- whether local matching succeeded
- whether RANSAC verification accepted the match
- whether the pipeline is ready for broader inference on the dataset

## Important restrictions

This test plan stays within the project restrictions:
- no custom training
- no fine-tuning
- no model weight training
- no modification of the existing detector or API routes
- no use of uncertain or out-of-coverage examples

This is a planned validation step, not a full production inference run.
