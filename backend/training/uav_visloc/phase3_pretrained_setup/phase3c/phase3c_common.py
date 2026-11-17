from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, cast

import numpy as np
import psutil
import torch
import yaml
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent


class ResourceMonitor:
    def __init__(self, minimum_available_ram_gb: float, interval_seconds: float = 0.25) -> None:
        self._process = psutil.Process()
        self._minimum_available_bytes = int(minimum_available_ram_gb * 1024**3)
        self._interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._pressure = threading.Event()
        self._thread: threading.Thread | None = None
        self.peak_rss_bytes = self._process.memory_info().rss
        self.minimum_available_bytes = psutil.virtual_memory().available

    def start(self) -> None:
        self._sample()
        self._thread = threading.Thread(target=self._run, name="phase3c-memory-monitor", daemon=True)
        self._thread.start()

    def _sample(self) -> None:
        self.peak_rss_bytes = max(self.peak_rss_bytes, self._process.memory_info().rss)
        available = psutil.virtual_memory().available
        self.minimum_available_bytes = min(self.minimum_available_bytes, available)
        if available < self._minimum_available_bytes:
            self._pressure.set()

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            self._sample()

    @property
    def memory_pressure(self) -> bool:
        return self._pressure.is_set()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        self._sample()


def load_config(config_path: Path | None = None) -> tuple[dict[str, Any], dict[str, Path]]:
    path = config_path or BASE_DIR / "index_config.yaml"
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")

    path_keys = (
        "dataset_root",
        "phase1_metadata",
        "phase2_tile_metadata",
        "tile_metadata",
        "satellite_tiles",
        "global_features",
        "local_features",
        "index_metadata",
        "reports",
    )
    paths: dict[str, Path] = {}
    for key in path_keys:
        value = Path(config[key])
        paths[key] = (BASE_DIR / value).resolve() if not value.is_absolute() else value
    return config, paths


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def checkpoint_number(
    payload: dict[str, object], key: str, default: int | float
) -> int | float:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid numeric checkpoint value for {key}: {value!r}")
    return value


def write_csv_atomic(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def write_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            cast(Any, np.savez_compressed)(handle, **arrays)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def configure_cpu(config: dict[str, Any]) -> torch.device:
    if config["inference"]["device"].lower() != "cpu":
        raise ValueError("Phase 3C supports CPU inference only.")
    torch.set_num_threads(int(config["inference"]["cpu_threads"]))
    return torch.device("cpu")


def feature_signature(config: dict[str, Any], family: str) -> str:
    payload: dict[str, Any] = {
        "family": family,
        "torch_version": torch.__version__,
        "device": config["inference"]["device"],
        "cpu_threads": config["inference"]["cpu_threads"],
    }
    if family == "dinov2":
        payload["model"] = config["dinov2"]
    elif family == "superpoint":
        payload["model"] = config["superpoint"]
    else:
        raise ValueError(f"Unknown feature family: {family}")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_dinov2(config: dict[str, Any], device: torch.device) -> torch.nn.Module:
    model = cast(
        torch.nn.Module,
        torch.hub.load(
            config["dinov2"]["repository"],
            config["dinov2"]["entrypoint"],
            trust_repo="check",
        ),
    )
    model = model.to(device)
    model.eval()
    if model.training:
        raise RuntimeError("DINOv2 did not enter evaluation mode.")
    return model


def image_tensor(path: Path, config: dict[str, Any]) -> torch.Tensor:
    size = int(config["dinov2"]["input_size_px"])
    with Image.open(path) as source:
        image = source.convert("RGB")
        image.thumbnail((size, size), Image.Resampling.BICUBIC)
        canvas = Image.new("RGB", (size, size), (124, 116, 104))
        canvas.paste(image, ((size - image.width) // 2, (size - image.height) // 2))
        pixels = np.asarray(canvas, dtype=np.float32) / 255.0
    pixels = (pixels - np.asarray(config["dinov2"]["image_mean"], dtype=np.float32)) / np.asarray(
        config["dinov2"]["image_std"], dtype=np.float32
    )
    return torch.from_numpy(pixels.transpose(2, 0, 1)).unsqueeze(0)


def dinov2_descriptor(
    model: torch.nn.Module, path: Path, config: dict[str, Any], device: torch.device
) -> np.ndarray:
    with torch.inference_mode():
        output = model(image_tensor(path, config).to(device))
    if isinstance(output, dict):
        output = output.get("x_norm_clstoken")
    if not isinstance(output, torch.Tensor) or output.ndim != 2 or output.shape[0] != 1:
        raise RuntimeError(f"Unexpected DINOv2 output for {path}: {type(output)}")
    descriptor = output[0].detach().cpu().numpy().astype(np.float32, copy=False)
    if descriptor.shape != (int(config["dinov2"]["descriptor_dim"]),):
        raise RuntimeError(f"Unexpected descriptor shape {descriptor.shape} for {path}")
    norm = float(np.linalg.norm(descriptor))
    if not np.isfinite(descriptor).all() or not np.isfinite(norm) or norm <= 0.0:
        raise ValueError(f"DINOv2 produced an invalid descriptor for {path}")
    return descriptor / norm


def tile_image_path(row: dict[str, str], paths: dict[str, Path]) -> Path:
    image_path = paths["satellite_tiles"] / row["image_relative_path"]
    if not image_path.is_file():
        raise FileNotFoundError(f"Missing generated satellite tile: {image_path}")
    return image_path


def metadata_by_tile_id(paths: dict[str, Path]) -> dict[str, dict[str, str]]:
    rows = read_csv(paths["tile_metadata"])
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        tile_id = row["tile_id"]
        if tile_id in result:
            raise ValueError(f"Duplicate tile_id in {paths['tile_metadata']}: {tile_id}")
        result[tile_id] = row
    return result


def sorted_shards(directory: Path, prefix: str) -> list[Path]:
    return sorted(directory.glob(f"{prefix}_*.npz"))
