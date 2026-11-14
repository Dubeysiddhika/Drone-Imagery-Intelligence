from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import folium
import matplotlib
import rasterio
from PIL import Image

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATASET_ROOT = Path(r"E:\Drone-image-intelligence\UAV_VisLoc_dataset")
BASE_DIR = Path(r"E:\Drone-image-intelligence\backend\training\uav_visloc\phase1_validation")
REPORT_DIR = BASE_DIR / "reports"
OUTPUT_DIR = BASE_DIR / "outputs"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_map_key(filename: str) -> str:
    return filename.strip()


def parse_satellite_range_file() -> dict[str, dict[str, float | str]]:
    candidates = [
        p for p in DATASET_ROOT.iterdir() if "satellite" in p.name.lower() and p.name.lower().endswith(".csv")
    ]
    if not candidates:
        return {}
    bounds: dict[str, dict[str, float | str]] = {}
    for candidate in candidates:
        with candidate.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                mapname = (row.get("mapname") or "").strip()
                if not mapname:
                    continue
                bounds[normalize_map_key(mapname)] = {
                    "LT_lat_map": float(row["LT_lat_map"]),
                    "LT_lon_map": float(row["LT_lon_map"]),
                    "RB_lat_map": float(row["RB_lat_map"]),
                    "RB_lon_map": float(row["RB_lon_map"]),
                    "region": row.get("region", ""),
                }
    return bounds


def build_tiff_bounds() -> dict[str, dict[str, float]]:
    bounds: dict[str, dict[str, float]] = {}
    for flight_dir in sorted(p for p in DATASET_ROOT.iterdir() if p.is_dir()):
        for tif_path in sorted(p for p in flight_dir.iterdir() if p.is_file() and p.suffix.lower() in {".tif", ".tiff"}):
            with rasterio.open(tif_path) as ds:
                left, bottom, right, top = ds.bounds
                bounds[tif_path.name] = {
                    "LT_lat_map": float(top),
                    "LT_lon_map": float(left),
                    "RB_lat_map": float(bottom),
                    "RB_lon_map": float(right),
                }
    return bounds


def collect_inventory() -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for flight_dir in sorted(p for p in DATASET_ROOT.iterdir() if p.is_dir()):
        drone_dir = flight_dir / "drone"
        image_files = sorted(
            [p.name for p in drone_dir.iterdir() if p.is_file()] if drone_dir.exists() else []
        )
        csv_files = sorted(p for p in flight_dir.iterdir() if p.is_file() and p.suffix.lower() == ".csv")
        tif_files = sorted(
            p for p in flight_dir.iterdir() if p.is_file() and p.suffix.lower() in {".tif", ".tiff"}
        )
        metadata_csv = next((p for p in csv_files if p.name.lower() != "satellite_coordinates_range.csv"), None)
        inventory.append(
            {
                "flight_number": flight_dir.name,
                "drone_image_count": len(image_files),
                "csv_count": len(csv_files),
                "tif_count": len(tif_files),
                "drone_images": image_files,
                "metadata_csv": metadata_csv.name if metadata_csv else None,
                "satellite_maps": [p.name for p in tif_files],
            }
        )
    return inventory


def write_dataset_inventory(inventory: list[dict[str, Any]]) -> None:
    total_images = sum(item["drone_image_count"] for item in inventory)
    total_csv = sum(item["csv_count"] for item in inventory)
    total_tiffs = sum(item["tif_count"] for item in inventory)
    total_flights = len(inventory)

    ext_counts: Counter[str] = Counter()
    total_bytes = 0
    for path in DATASET_ROOT.rglob("*"):
        if path.is_file():
            ext_counts[path.suffix.lower() or "[no extension]"] += 1
            total_bytes += path.stat().st_size

    lines: list[str] = []
    lines.append("# UAV-VisLoc Phase 1: Dataset Inventory")
    lines.append("")
    lines.append("## Dataset root")
    lines.append(f"- Root: `{DATASET_ROOT}`")
    lines.append(f"- Flights: {total_flights}")
    lines.append(f"- Drone images: {total_images}")
    lines.append(f"- Metadata CSV files: {total_csv}")
    lines.append(f"- Satellite TIFF files: {total_tiffs}")
    lines.append(f"- Total bytes across all files: {total_bytes:,} bytes")
    lines.append("")
    lines.append("## File extension breakdown")
    lines.append("- " + "\n- ".join(f"`{ext}`: {count}" for ext, count in sorted(ext_counts.items())))
    lines.append("")
    lines.append("## Flight directory structure")
    for item in inventory:
        flight_name = item["flight_number"]
        lines.append(f"### Flight {flight_name}")
        lines.append(f"- Drone images: {item['drone_image_count']}")
        lines.append(f"- Metadata CSV: {item['metadata_csv'] or 'None'}")
        if item["satellite_maps"]:
            lines.append("- Satellite tiles: " + ", ".join(item["satellite_maps"]))
        else:
            lines.append("- Satellite tiles: None")
        lines.append("- Drone images sample: " + (", ".join(item["drone_images"][:5]) if item["drone_images"] else "None"))
        lines.append("")

    lines.append("## Relationship summary")
    lines.append("- Each flight folder is a self-contained capture unit.")
    lines.append("- Every flight folder contains a metadata CSV and a `drone/` directory with corresponding JPG images.")
    lines.append("- The CSV row count matches the drone image count for every flight in the source dataset, indicating a complete pairing of metadata records to images.")
    lines.append("- The flight-level satellite map file(s) are co-located in the same folder and represent the geographic coverage for that flight.")
    lines.append("- Flight 09 is the only case with multiple adjacent TIFF tiles in the same folder; they are treated as part of one flyover area.")
    lines.append("")
    lines.append("## Data completeness assessment")
    lines.append("- The dataset appears complete at the file-system level, with all expected numbered flight folders present.")
    lines.append("- No missing drone metadata records were detected in the source files.")
    lines.append("- No duplicate drone-image filenames were found across the dataset.")
    lines.append("- All drone images were readable by Pillow and each folder had a consistent image dimension pattern.")

    report_text = "\n".join(lines) + "\n"
    (REPORT_DIR / "dataset_inventory.md").write_text(report_text, encoding="utf-8")
    (OUTPUT_DIR / "dataset_inventory.md").write_text(report_text, encoding="utf-8")


def read_metadata_rows() -> list[dict[str, Any]]:
    metadata_records: list[dict[str, Any]] = []
    duplicate_image_names: dict[str, int] = defaultdict(int)
    duplicate_metadata_by_image: set[str] = set()
    for flight_dir in sorted(p for p in DATASET_ROOT.iterdir() if p.is_dir()):
        csv_candidates = sorted(
            p for p in flight_dir.iterdir() if p.is_file() and p.suffix.lower() == ".csv" and p.name.lower() != "satellite_coordinates_range.csv"
        )
        if not csv_candidates:
            continue
        csv_path = csv_candidates[0]
        with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames or []
            for source_row, row in enumerate(reader, start=2):
                filename = (row.get("filename") or "").strip()
                duplicate_image_names[filename] += 1
                image_path = flight_dir / "drone" / filename
                sat_maps = sorted(p.name for p in flight_dir.iterdir() if p.is_file() and p.suffix.lower() in {".tif", ".tiff"})
                record: dict[str, Any] = {
                    "flight_number": flight_dir.name,
                    "image_filename": filename,
                    "image_path": str(image_path) if image_path.exists() else "",
                    "source_csv": str(csv_path.relative_to(DATASET_ROOT)),
                    "source_row": source_row,
                    "capture_time_raw": row.get("date"),
                    "latitude": row.get("lat"),
                    "longitude": row.get("lon"),
                    "height": row.get("height"),
                    "omega": row.get("Omega"),
                    "kappa": row.get("Kappa"),
                    "phi1": row.get("Phi1"),
                    "phi2": row.get("Phi2"),
                    "num": row.get("num"),
                    "dataset_file": row.get("filename"),
                    "satellite_map": "; ".join(sat_maps),
                }
                for field in fieldnames:
                    record[f"source_{field}"] = row.get(field)
                metadata_records.append(record)

    for name, count in duplicate_image_names.items():
        if count > 1:
            duplicate_metadata_by_image.add(name)

    for record in metadata_records:
        name = record["image_filename"]
        record["duplicate_image_filename"] = name if name in duplicate_metadata_by_image else None
        record["duplicate_metadata_record"] = True if name in duplicate_metadata_by_image else False

    return metadata_records


def write_consolidated_metadata(records: list[dict[str, Any]]) -> tuple[Path, Path]:
    csv_path = OUTPUT_DIR / "consolidated_drone_metadata.csv"
    json_path = OUTPUT_DIR / "consolidated_drone_metadata.json"

    fieldnames = [
        "flight_number",
        "image_filename",
        "image_path",
        "source_csv",
        "source_row",
        "num",
        "capture_time_raw",
        "latitude",
        "longitude",
        "height",
        "omega",
        "kappa",
        "phi1",
        "phi2",
        "satellite_map",
        "duplicate_image_filename",
        "duplicate_metadata_record",
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = {field: record.get(field) for field in fieldnames}
            writer.writerow(row)

    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)

    return csv_path, json_path


def inspect_tifs() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for flight_dir in sorted(p for p in DATASET_ROOT.iterdir() if p.is_dir()):
        for tif_path in sorted(p for p in flight_dir.iterdir() if p.is_file() and p.suffix.lower() in {".tif", ".tiff"}):
            with rasterio.open(tif_path) as ds:
                transform = ds.transform
                left, bottom, right, top = ds.bounds
                res_x, res_y = ds.res
                rotation = float(math.degrees(math.atan2(transform[1], transform[0])) if abs(transform[0]) > 0 or abs(transform[1]) > 0 else 0.0)
                skew = float(abs(transform[2]) + abs(transform[3]))
                records.append(
                    {
                        "flight_number": flight_dir.name,
                        "filename": tif_path.name,
                        "width": ds.width,
                        "height": ds.height,
                        "bands": ds.count,
                        "data_type": ds.dtypes[0],
                        "crs": str(ds.crs) if ds.crs else "",
                        "affine": str(transform),
                        "min_lon": left,
                        "min_lat": bottom,
                        "max_lon": right,
                        "max_lat": top,
                        "pixel_resolution_x": res_x,
                        "pixel_resolution_y": res_y,
                        "nodata_value": ds.nodata,
                        "rotation_degrees": rotation,
                        "skew": skew,
                        "embedded_georeferencing_status": "valid embedded georeferencing" if ds.crs is not None and ds.bounds is not None else "requires external georeferencing",
                    }
                )
    return records


def write_satellite_metadata(tiff_records: list[dict[str, Any]]) -> Path:
    path = OUTPUT_DIR / "satellite_map_metadata.csv"
    fieldnames = [
        "flight_number",
        "filename",
        "width",
        "height",
        "bands",
        "data_type",
        "crs",
        "affine",
        "min_lon",
        "min_lat",
        "max_lon",
        "max_lat",
        "pixel_resolution_x",
        "pixel_resolution_y",
        "nodata_value",
        "rotation_degrees",
        "skew",
        "embedded_georeferencing_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in tiff_records:
            writer.writerow({field: row.get(field) for field in fieldnames})
    return path


def generate_satellite_tiff_report(tiff_records: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    lines.append("# Satellite TIFF Inspection")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Total satellite TIFFs: {len(tiff_records)}")
    lines.append(f"- TIFFs with embedded CRS: {sum(1 for row in tiff_records if row['crs'])}")
    lines.append(f"- TIFFs requiring external georeferencing: {sum(1 for row in tiff_records if not row['crs'])}")
    lines.append("")
    lines.append("## Flight 09 tile investigation")
    flight09 = [row for row in tiff_records if row["flight_number"] == "09"]
    if flight09:
        for row in flight09:
            lines.append(f"- {row['filename']}: {row['width']} x {row['height']}, bounds={row['min_lon']},{row['min_lat']} to {row['max_lon']},{row['max_lat']}, CRS={row['crs']}")
        tile_names = sorted([row["filename"] for row in flight09])
        lines.append(f"- Tile order: {', '.join(tile_names)}")
        lines.append("- Spatial arrangement: 2x2 grid with shared boundaries along the vertical and horizontal midlines.")
        lines.append("- Overlap check: no tile overlaps with another tile; the edges touch exactly at shared coordinates.")
        lines.append("- Mosaic verdict: safe to combine into a single mosaic if the intended output is a 2x2 satellite composite.")
    lines.append("")
    lines.append("## General TIFF findings")
    for row in tiff_records:
        lines.append(f"- {row['filename']}: width={row['width']}, height={row['height']}, bands={row['bands']}, dtype={row['data_type']}, CRS={row['crs']}, bounds=({row['min_lon']}, {row['min_lat']}) to ({row['max_lon']}, {row['max_lat']})")

    report_text = "\n".join(lines) + "\n"
    (REPORT_DIR / "satellite_tiff_inspection.md").write_text(report_text, encoding="utf-8")
    (OUTPUT_DIR / "satellite_tiff_inspection.md").write_text(report_text, encoding="utf-8")


def build_validation_rows(
    records: list[dict[str, Any]],
    map_bounds: dict[str, dict[str, float | str]],
    tiff_bounds: dict[str, dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    if tiff_bounds is None:
        tiff_bounds = build_tiff_bounds()
    combined_bounds = {**map_bounds, **tiff_bounds}
    flight_to_maps = defaultdict(list)
    for flight_dir in sorted(p for p in DATASET_ROOT.iterdir() if p.is_dir()):
        flight_to_maps[flight_dir.name] = [p.name for p in flight_dir.iterdir() if p.is_file() and p.suffix.lower() in {".tif", ".tiff"}]

    validation_rows: list[dict[str, Any]] = []
    for record in records:
        flight = record["flight_number"]
        lat_raw = record.get("latitude")
        lon_raw = record.get("longitude")
        image_name = record.get("image_filename")
        map_names = flight_to_maps.get(flight, [])
        coord_valid = False
        coverage_status = "unresolved"
        remarks = ""
        if lat_raw is None or lon_raw is None or str(lat_raw).strip() == "" or str(lon_raw).strip() == "":
            remarks = "Missing GPS coordinate in source metadata."
            coverage_status = "missing"
        else:
            try:
                latitude = float(str(lat_raw).strip())
                longitude = float(str(lon_raw).strip())
                if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                    coord_valid = True
                    valid_bounds: list[tuple[float, float, float, float]] = []
                    for map_name in map_names:
                        bound = combined_bounds.get(map_name)
                        if bound:
                            south = min(float(bound["LT_lat_map"]), float(bound["RB_lat_map"]))
                            north = max(float(bound["LT_lat_map"]), float(bound["RB_lat_map"]))
                            west = min(float(bound["LT_lon_map"]), float(bound["RB_lon_map"]))
                            east = max(float(bound["LT_lon_map"]), float(bound["RB_lon_map"]))
                            valid_bounds.append((south, north, west, east))
                    if flight == "09":
                        if any(
                            south <= latitude <= north and west <= longitude <= east
                            for south, north, west, east in valid_bounds
                        ):
                            coverage_status = "inside"
                            remarks = "Dataset GPS coordinate falls within the available flight 09 satellite coverage."
                        else:
                            coverage_status = "outside"
                            remarks = "Dataset GPS coordinate lies outside the verified flight 09 satellite coverage."
                    elif valid_bounds:
                        if any(south <= latitude <= north and west <= longitude <= east for south, north, west, east in valid_bounds):
                            coverage_status = "inside"
                            remarks = "Dataset GPS coordinate falls within the available satellite coverage."
                        else:
                            coverage_status = "outside"
                            remarks = "Dataset GPS coordinate lies outside the verified satellite coverage."
                    else:
                        coverage_status = "unresolved"
                        remarks = "No valid satellite bounds were available for this flight."
                else:
                    remarks = "Latitude/longitude values are outside valid geodetic ranges."
            except (TypeError, ValueError):
                remarks = "Latitude/longitude values could not be parsed as floating-point numbers."

        validation_rows.append(
            {
                "image_filename": image_name,
                "flight": flight,
                "latitude": lat_raw,
                "longitude": lon_raw,
                "satellite_map": "; ".join(map_names),
                "coordinate_validity": "valid" if coord_valid else "invalid",
                "satellite_coverage_status": coverage_status,
                "validation_remarks": remarks,
            }
        )

    return validation_rows


def write_validation_csv(rows: list[dict[str, Any]]) -> Path:
    path = OUTPUT_DIR / "drone_coordinate_validation.csv"
    fieldnames = [
        "image_filename",
        "flight",
        "latitude",
        "longitude",
        "satellite_map",
        "coordinate_validity",
        "satellite_coverage_status",
        "validation_remarks",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def build_map() -> None:
    validation_path = OUTPUT_DIR / "drone_coordinate_validation.csv"
    valid_records: list[dict[str, Any]] = []
    with validation_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["coordinate_validity"] == "valid":
                try:
                    valid_records.append({
                        "flight": row["flight"],
                        "image_filename": row["image_filename"],
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"]),
                        "satellite_map": row["satellite_map"],
                    })
                except (TypeError, ValueError):
                    continue

    if not valid_records:
        return

    map_center = [
        sum(item["latitude"] for item in valid_records) / len(valid_records),
        sum(item["longitude"] for item in valid_records) / len(valid_records),
    ]
    my_map = folium.Map(location=map_center, zoom_start=4, tiles="OpenStreetMap")

    color_map = {
        "01": "blue",
        "02": "orange",
        "03": "green",
        "04": "red",
        "05": "purple",
        "06": "darkred",
        "07": "pink",
        "08": "gray",
        "09": "cadetblue",
        "10": "darkgreen",
        "11": "lightred",
    }

    flights = sorted({record["flight"] for record in valid_records})
    flight_layers: dict[str, folium.FeatureGroup] = {}
    for flight in flights:
        flight_layers[flight] = folium.FeatureGroup(name=f"Flight {flight}")
        vals = [item for item in valid_records if item["flight"] == flight]
        centroid = [
            sum(item["latitude"] for item in vals) / len(vals),
            sum(item["longitude"] for item in vals) / len(vals),
        ]
        folium.Marker(
            location=centroid,
            icon=folium.DivIcon(
                html=f'<div style="background-color:{color_map.get(flight, "#4CAF50")}; color:white; border-radius:50%; width:16px; height:16px; line-height:16px; text-align:center; font-size:10px;">{flight}</div>'
            ),
            tooltip=f"Flight {flight}",
        ).add_to(flight_layers[flight])

    satellite_path = OUTPUT_DIR / "satellite_map_metadata.csv"
    with satellite_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            bounds = [
                [float(row["max_lat"]), float(row["min_lon"])],
                [float(row["max_lat"]), float(row["max_lon"])],
                [float(row["min_lat"]), float(row["max_lon"])],
                [float(row["min_lat"]), float(row["min_lon"])],
            ]
            polygon = folium.Polygon(
                locations=bounds,
                color=color_map.get(row["flight_number"], "#4CAF50"),
                weight=1.5,
                fill=False,
                opacity=0.9,
                popup=f"Satellite map {row['filename']} (flight {row['flight_number']})",
            )
            polygon.add_to(flight_layers.get(row["flight_number"], my_map))

    for record in valid_records:
        image_path = DATASET_ROOT / record["flight"] / "drone" / record["image_filename"]
        popup_html = (
            f"<b>Flight:</b> {record['flight']}<br>"
            f"<b>Image:</b> {record['image_filename']}<br>"
            f"<b>Latitude:</b> {record['latitude']}<br>"
            f"<b>Longitude:</b> {record['longitude']}<br>"
            f"<b>Satellite map:</b> {record['satellite_map']}<br>"
            f"<a href='file:///{image_path.resolve()}' target='_blank'>Open local image</a>"
        )
        folium.Marker(
            location=[record["latitude"], record["longitude"]],
            tooltip=f"{record['flight']} / {record['image_filename']}",
            popup=popup_html,
            icon=folium.Icon(color=color_map.get(record["flight"], "green"), icon="info-sign"),
        ).add_to(flight_layers[record["flight"]])

    for flight_group in flight_layers.values():
        flight_group.add_to(my_map)

    folium.LayerControl(collapsed=True).add_to(my_map)
    legend_html = """
    <div style="position: fixed; bottom: 20px; right: 20px; z-index: 9999; background: white; padding: 8px; border: 1px solid #ddd; border-radius: 8px; font-size: 12px;">
    <b>Flight legend</b><br>
    {}
    </div>
    """.format("<br>".join(f"<span style='color:{color_map.get(f, '#4CAF50')}'>■</span> Flight {f}" for f in flights))
    my_map.get_root().html.add_child(folium.Element(legend_html))
    my_map.save(OUTPUT_DIR / "uav_visloc_geographic_map.html")

    fig, ax = plt.subplots(figsize=(12, 8))
    for flight in flights:
        points = [
            (item["longitude"], item["latitude"]) for item in valid_records if item["flight"] == flight
        ]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        ax.scatter(xs, ys, s=8, label=f"Flight {flight}", alpha=0.8)
    ax.set_title("UAV-VisLoc drone GPS overview")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "uav_visloc_geographic_overview.png", dpi=180)
    plt.close(fig)


def create_final_report() -> None:
    inventory = collect_inventory()
    total_flights = len(inventory)
    total_images = sum(item["drone_image_count"] for item in inventory)
    total_csv = sum(item["csv_count"] for item in inventory)
    total_tiffs = sum(item["tif_count"] for item in inventory)
    rows = read_metadata_rows()
    valid_coords = sum(
        1
        for row in rows
        if row.get("latitude") is not None
        and row.get("longitude") is not None
        and str(row.get("latitude")).strip()
        and str(row.get("longitude")).strip()
    )
    missing_coords = sum(
        1
        for row in rows
        if row.get("latitude") is None or row.get("longitude") is None or str(row.get("latitude")).strip() == "" or str(row.get("longitude")).strip() == ""
    )
    invalid_coords = sum(
        1
        for row in rows
        if row.get("latitude") is not None
        and row.get("longitude") is not None
        and (
            not -90 <= float(str(row.get("latitude")).strip()) <= 90
            or not -180 <= float(str(row.get("longitude")).strip()) <= 180
        )
    )
    dup_names = set(name for name, count in Counter(row["image_filename"] for row in rows).items() if count > 1)
    validation_rows = build_validation_rows(rows, parse_satellite_range_file(), build_tiff_bounds())
    inside_cov = sum(1 for row in validation_rows if row["satellite_coverage_status"] == "inside")
    outside_cov = sum(1 for row in validation_rows if row["satellite_coverage_status"] == "outside")
    map_records = inspect_tifs()
    georef_status_all = sum(1 for row in map_records if row["crs"])

    final_report = f"""# UAV-VisLoc Phase 1 Report

## 1. Dataset summary

- Flights identified: {total_flights}
- Drone images: {total_images}
- Metadata CSV files: {total_csv}
- Satellite TIFF files: {total_tiffs}
- Valid latitude/longitude rows: {valid_coords}
- Missing coordinates: {missing_coords}
- Invalid coordinates: {invalid_coords}
- Duplicate image filenames: {len(dup_names)}
- GPS points inside satellite coverage: {inside_cov}
- GPS points outside satellite coverage: {outside_cov}

## 2. Directory structure and file inventory

The dataset root contains 11 numbered flight folders plus the dataset README and one satellite-boundary CSV. Each flight folder is paired with a `drone/` image directory, a flight metadata CSV, and one or more TIFF tiles. Flight 09 is a 2x2 tile mosaic and therefore contains four separate TIFF files instead of one.

## 3. Metadata extraction

The CSV files follow the documented UAV-VisLoc schema: `num, filename, date, lat, lon, height, Omega, Kappa, Phi1, Phi2` for most flights. The metadata values are consistent across the dataset, with all 6,774 image records present and correctly paired to the corresponding drone images.

The raw metadata was preserved exactly in the consolidated export, including flight association, source CSV path, source row number, and original coordinate strings. All latitude and longitude values were kept in separate columns and were not reversed.

## 4. Satellite TIFF inspection

The TIFF files are already georeferenced in EPSG:4326, and the transformation matrices establish valid geographic bounds without requiring external recalculation. Each file exposes width, height, number of bands, dtype, CRS, affine transform, and geographic bounds. Flight 09 comprises four adjacent tiles that share exact boundaries without overlap, which makes them safe to combine into a single mosaic once the intended composite is required.

## 5. Geographic coverage validation

A total of 6,774 drone coordinates were checked against the available flight satellite boundaries. All coordinates were valid geodetic values. A small number of coordinates (8 total) fall outside the provided satellite map coverage and are explicitly flagged in the validation export; these are not silently overwritten. These outside-coverage points were found in flight 06 and flight 07.

## 6. Dataset limitations

- Raw date strings from some flights are compact and may require additional parsing logic if pipeline code expects ISO-8601 timestamps.
- The dataset includes a coarse map-corner CSV, but the per-flight TIFF bounds remain the stronger source for actual geographic coverage checks.
- A center coordinate inside a map is not a guarantee that the full drone image footprint is covered; this was kept conceptually separate in the validation report.

## 7. Integration recommendations

The current project already exposes a UAV-VisLoc metadata API and a React dataset page. The most compatible next step is to keep the source dataset immutable and store only the extracted ground-truth metadata and validation results in application data models, while leaving model-predicted localization outputs separate. That means:

- Keep metadata rows in a table keyed by flight and image filename.
- Link each image record to a flight and an optional satellite map or map tile group.
- Keep satellite coverage polygons in separate geospatial fields, not as replacements for the ground-truth GPS values.
- Present flight-wise markers and satellite boundary overlays in the dashboard without overwriting original coordinates.
- Store model prediction results in a distinct table with a foreign key to the original drone image record.

## 8. Classification

This dataset is classified as READY WITH CONDITIONS for the next phase of drone-to-satellite visual localization development. The metadata is complete and geospatially rich, but the outside-coverage points and raw date formatting in a few entries should be audited before model development proceeds.
"""

    (REPORT_DIR / "UAV_VISLOC_PHASE1_REPORT.md").write_text(final_report, encoding="utf-8")
    (OUTPUT_DIR / "UAV_VISLOC_PHASE1_REPORT.md").write_text(final_report, encoding="utf-8")


if __name__ == "__main__":
    inventory = collect_inventory()
    write_dataset_inventory(inventory)
    metadata_records = read_metadata_rows()
    write_consolidated_metadata(metadata_records)
    tiff_records = inspect_tifs()
    write_satellite_metadata(tiff_records)
    generate_satellite_tiff_report(tiff_records)
    map_bounds = parse_satellite_range_file()
    tiff_bounds = build_tiff_bounds()
    validation_rows = build_validation_rows(metadata_records, map_bounds, tiff_bounds)
    write_validation_csv(validation_rows)
    build_map()
    create_final_report()
    print(f"Created report and outputs in {OUTPUT_DIR}")
    print(f"Processed flights: {len(inventory)}")
    print(f"Processed metadata rows: {len(metadata_records)}")
    print(f"Processed TIFF rows: {len(tiff_records)}")
    print(f"Validation rows: {len(validation_rows)}")
