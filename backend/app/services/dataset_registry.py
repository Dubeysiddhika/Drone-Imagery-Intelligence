"""Cached UAV-VisLoc CSV registry and conservative uploaded-image matching."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ..config import PROJECT_ROOT, resolve_project_path

logger = logging.getLogger(__name__)
DEFAULT_DATASET_ROOT = resolve_project_path(
    os.environ.get("UAV_VISLOC_DATASET_DIR"),
    "UAV_VisLoc_dataset",
)
CONSOLIDATED_CSV = resolve_project_path(
    os.environ.get("UAV_VISLOC_CONSOLIDATED_CSV"),
    "backend/training/uav_visloc/phase1_validation/outputs/consolidated_drone_metadata.csv",
)
_registry_lock = threading.Lock()
_registry: "DatasetRegistry | None" = None


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if np.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _perceptual_hash(path: Path) -> int | None:
    image = cv2.imread(str(path), cv2.IMREAD_REDUCED_GRAYSCALE_4)
    if image is None:
        return None
    image = cv2.resize(image, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    coefficients = cv2.dct(image)[:8, :8].flatten()
    median = float(np.median(coefficients[1:]))
    value = 0
    for coefficient in coefficients:
        value = (value << 1) | int(coefficient > median)
    return value


def _hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _verify_visual_match(query_path: Path, candidate_path: Path) -> tuple[int, float]:
    query = cv2.imread(str(query_path), cv2.IMREAD_GRAYSCALE)
    candidate = cv2.imread(str(candidate_path), cv2.IMREAD_GRAYSCALE)
    if query is None or candidate is None:
        return 0, 0.0
    query_scale = min(1.0, 1400 / max(query.shape[:2]))
    if query_scale < 1.0:
        query = cv2.resize(query, None, fx=query_scale, fy=query_scale, interpolation=cv2.INTER_AREA)
    candidate_scale = min(1.0, 1400 / max(candidate.shape[:2]))
    if candidate_scale < 1.0:
        candidate = cv2.resize(candidate, None, fx=candidate_scale, fy=candidate_scale, interpolation=cv2.INTER_AREA)
    detector = cv2.ORB_create(nfeatures=5000, scaleFactor=1.2, nlevels=8)
    query_points, query_desc = detector.detectAndCompute(query, None)
    candidate_points, candidate_desc = detector.detectAndCompute(candidate, None)
    if query_desc is None or candidate_desc is None:
        return 0, 0.0
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(query_desc, candidate_desc, k=2)
    good = [first for first, second in pairs if first.distance < 0.72 * second.distance]
    if len(good) < 12:
        return 0, len(good) / max(1, len(pairs))
    source = np.float32([query_points[item.queryIdx].pt for item in good])
    target = np.float32([candidate_points[item.trainIdx].pt for item in good])
    _matrix, mask = cv2.findHomography(source, target, cv2.RANSAC, 4.0, maxIters=2000)
    inliers = int(mask.ravel().sum()) if mask is not None else 0
    return inliers, inliers / len(good)


class DatasetRegistry:
    """Read CSVs once and cache content fingerprints for conservative fallback matching."""

    def __init__(self, root: Path = DEFAULT_DATASET_ROOT):
        self.root = root.resolve()
        self.records: list[dict[str, Any]] = []
        self.by_filename: dict[str, list[dict[str, Any]]] = {}
        self._fingerprints: dict[str, tuple[int, int, int]] | None = None
        self._load_csv_registry()

    def _load_csv_registry(self) -> None:
        if not self.root.is_dir():
            return
        consolidated: dict[str, dict[str, str]] = {}
        if CONSOLIDATED_CSV.is_file():
            try:
                with CONSOLIDATED_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
                    for row in csv.DictReader(handle):
                        key = Path(row.get("image_filename", "")).name.casefold()
                        if key:
                            consolidated[key] = row
            except (OSError, csv.Error):
                logger.exception("Could not read the derived UAV-VisLoc metadata index")

        for csv_path in sorted(self.root.glob("*/[0-9]*.csv")):
            flight = csv_path.parent.name
            try:
                with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    rows = csv.DictReader(handle)
                    for raw in rows:
                        filename = Path(raw.get("filename", "")).name
                        if not filename:
                            continue
                        key = filename.casefold()
                        relative = Path(flight) / "drone" / filename
                        source_image = (self.root / relative).resolve()
                        try:
                            source_image.relative_to(self.root)
                        except ValueError:
                            continue
                        extras = consolidated.get(key, {})
                        latitude = _number(raw.get("lat", extras.get("latitude")))
                        longitude = _number(raw.get("lon", extras.get("longitude")))
                        gps_valid = (
                            latitude is not None and longitude is not None
                            and -90 <= latitude <= 90 and -180 <= longitude <= 180
                        )
                        map_name = extras.get("satellite_map") or None
                        record = {
                            "filename": filename,
                            "flight_sequence": flight,
                            "dataset_image_path": relative.as_posix(),
                            "dataset_image_exists": source_image.is_file(),
                            "metadata_csv": csv_path.relative_to(self.root).as_posix(),
                            "satellite_map": map_name,
                            "ground_truth": {
                                "latitude": latitude if gps_valid else None,
                                "longitude": longitude if gps_valid else None,
                                "coordinate_reference_system": "EPSG:4326" if gps_valid else None,
                                "coordinate_source": "uav_visloc_dataset_ground_truth" if gps_valid else None,
                                "available": gps_valid,
                            },
                            "source_fields": dict(raw),
                            "consolidated_fields": dict(extras),
                            "_absolute_path": str(source_image),
                        }
                        self.records.append(record)
                        self.by_filename.setdefault(key, []).append(record)
            except (OSError, csv.Error):
                logger.exception("Could not read UAV-VisLoc metadata CSV %s", csv_path)

    @staticmethod
    def _public(record: dict[str, Any] | None) -> dict[str, Any] | None:
        if record is None:
            return None
        return {key: value for key, value in record.items() if not key.startswith("_")}

    def _build_fingerprint_index(self) -> dict[str, tuple[int, int, int]]:
        cache_path = self.root.parent / ".uav_visloc_fingerprints.json"
        fingerprints: dict[str, tuple[int, int, int]] = {}
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
        for record in self.records:
            path = Path(record["_absolute_path"])
            if not path.is_file():
                continue
            try:
                stat = path.stat()
                relative = record["dataset_image_path"]
                cached = cache.get(relative)
                if cached and cached[:2] == [stat.st_size, stat.st_mtime_ns]:
                    signature = int(cached[2])
                else:
                    signature = _perceptual_hash(path)
                    if signature is None:
                        continue
                    cache[relative] = [stat.st_size, stat.st_mtime_ns, signature]
                fingerprints[relative] = (signature, stat.st_size, stat.st_mtime_ns)
            except OSError:
                continue
        try:
            cache_path.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")
        except OSError:
            logger.warning("Could not persist UAV-VisLoc content fingerprint cache %s", cache_path)
        return fingerprints

    def identify(self, image_path: Path, uploaded_filename: str) -> dict[str, Any]:
        filename_key = Path(uploaded_filename).name.casefold()
        named = self.by_filename.get(filename_key, [])
        if len(named) == 1:
            candidate_path = Path(named[0]["_absolute_path"])
            if candidate_path.is_file():
                try:
                    if _sha256(candidate_path) == _sha256(image_path):
                        return {
                            "status": "matched", "method": "exact_filename_and_sha256",
                            "confidence": 1.0, "record": self._public(named[0]),
                        }
                except OSError:
                    pass

        if self._fingerprints is None:
            with _registry_lock:
                if self._fingerprints is None:
                    self._fingerprints = self._build_fingerprint_index()
        query_hash = _perceptual_hash(image_path)
        if query_hash is None:
            return {"status": "not_matched", "method": None, "confidence": None, "record": None}
        nearest = sorted(
            (
                (_hamming(query_hash, item[0]), record)
                for record in self.records
                if (item := self._fingerprints.get(record["dataset_image_path"])) is not None
            ),
            key=lambda item: item[0],
        )[:8]
        verified: list[tuple[int, float, dict[str, Any]]] = []
        exact_content_matches: list[dict[str, Any]] = []
        for distance, record in nearest:
            if distance > 12:
                continue
            source_path = Path(record["_absolute_path"])
            if not source_path.is_file():
                continue
            try:
                if _sha256(source_path) == _sha256(image_path):
                    exact_content_matches.append(record)
                    continue
                inliers, ratio = _verify_visual_match(image_path, source_path)
                if inliers >= 20 and ratio >= 0.5:
                    verified.append((inliers, ratio, record))
            except (OSError, cv2.error, ValueError):
                continue
        if len(exact_content_matches) == 1:
            return {
                "status": "matched", "method": "sha256_content",
                "confidence": 1.0, "record": self._public(exact_content_matches[0]),
            }
        if len(exact_content_matches) > 1:
            return {"status": "ambiguous", "method": None, "confidence": None, "record": None}
        verified.sort(key=lambda item: (item[0], item[1]), reverse=True)
        if verified:
            best = verified[0]
            ambiguous = len(verified) > 1 and (
                verified[1][0] >= best[0] * 0.9
                and verified[1][1] >= best[1] * 0.9
            )
            if not ambiguous:
                return {
                    "status": "matched", "method": "verified_orb_ransac",
                    "confidence": round(min(1.0, best[1] * min(1.0, best[0] / 40)), 4),
                    "verification": {"ransac_inliers": best[0], "inlier_ratio": round(best[1], 4)},
                    "record": self._public(best[2]),
                }
        return {"status": "ambiguous" if verified else "not_matched", "method": None, "confidence": None, "record": None}


def get_dataset_registry() -> DatasetRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = DatasetRegistry()
    return _registry


def identify_dataset_image(image_path: str | Path, uploaded_filename: str) -> dict[str, Any]:
    """Identify an uploaded image without assigning unverified dataset coordinates."""
    return get_dataset_registry().identify(Path(image_path), uploaded_filename)
