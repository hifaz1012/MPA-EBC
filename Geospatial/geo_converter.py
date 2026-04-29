#!/usr/bin/env python3
"""Convert extracted or zipped geospatial vector datasets to GeoJSON or PMTiles."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from numbers import Real
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, Sequence


class ConversionError(RuntimeError):
    """Raised when an input cannot be converted with the available tooling."""


@dataclass(frozen=True)
class GeoJsonResult:
    source: Path
    output: Path
    feature_count: Optional[int]
    driver: str
    source_crs: str


@dataclass(frozen=True)
class PmtilesResult:
    source: Path
    output: Path
    layer_name: str


DIRECT_GEOJSON_EXTENSIONS = {".geojson", ".json"}
OGR_EXTENSIONS = {".fgb", ".gml", ".gpkg", ".json", ".kml"}
SHAPEFILE_EXTENSION = ".shp"


def install_hint() -> str:
    return "Install dependencies with: python -m pip install -r requirements.txt"


def read_cpg_encoding(shapefile_path: Path) -> str:
    cpg_path = shapefile_path.with_suffix(".cpg")
    if not cpg_path.exists():
        return "utf-8"
    encoding_name = cpg_path.read_text(encoding="ascii", errors="ignore").strip()
    return encoding_name or "utf-8"


def is_wgs84_projection(projection_wkt: str) -> bool:
    normalized_wkt = projection_wkt.upper()
    return "WGS_1984" in normalized_wkt or "WGS 84" in normalized_wkt or "EPSG\",\"4326" in normalized_wkt


def build_coordinate_projector(
    shapefile_path: Path,
    target_crs: str,
) -> tuple[Callable[[Sequence[float]], list[float]], str]:
    projection_path = shapefile_path.with_suffix(".prj")
    if not projection_path.exists():
        return lambda coordinate_pair: list(coordinate_pair), "unknown"

    projection_wkt = projection_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not projection_wkt:
        return lambda coordinate_pair: list(coordinate_pair), "unknown"

    try:
        from pyproj import CRS, Transformer
    except ImportError as import_error:
        if is_wgs84_projection(projection_wkt) and target_crs.upper() in {"EPSG:4326", "WGS84", "WGS 84"}:
            return lambda coordinate_pair: list(coordinate_pair), "WGS84"
        raise ConversionError(
            f"{shapefile_path.name} has a projection file, but pyproj is not installed. "
            "Install Geospatial/requirements.txt to enable reprojection."
        ) from import_error

    source_crs = CRS.from_wkt(projection_wkt)
    destination_crs = CRS.from_user_input(target_crs)
    source_label = source_crs.to_string() or projection_path.name

    if source_crs.equals(destination_crs):
        return lambda coordinate_pair: list(coordinate_pair), source_label

    transformer = Transformer.from_crs(source_crs, destination_crs, always_xy=True)

    def project_coordinate(coordinate_pair: Sequence[float]) -> list[float]:
        source_x = coordinate_pair[0]
        source_y = coordinate_pair[1]
        target_x, target_y = transformer.transform(source_x, source_y)
        return [target_x, target_y, *coordinate_pair[2:]]

    return project_coordinate, source_label


def transform_coordinates(
    coordinates: Any,
    project_coordinate: Callable[[Sequence[float]], list[float]],
) -> Any:
    if not isinstance(coordinates, (list, tuple)):
        return coordinates

    if len(coordinates) >= 2 and isinstance(coordinates[0], Real) and isinstance(coordinates[1], Real):
        return project_coordinate(coordinates)

    return [transform_coordinates(child_coordinates, project_coordinate) for child_coordinates in coordinates]


def transform_geometry(
    geometry: Optional[dict[str, Any]],
    project_coordinate: Callable[[Sequence[float]], list[float]],
) -> Optional[dict[str, Any]]:
    if geometry is None:
        return None

    if geometry.get("type") == "GeometryCollection":
        return {
            "type": "GeometryCollection",
            "geometries": [
                transform_geometry(child_geometry, project_coordinate)
                for child_geometry in geometry.get("geometries", [])
            ],
        }

    if "coordinates" not in geometry:
        return geometry

    transformed_geometry = dict(geometry)
    transformed_geometry["coordinates"] = transform_coordinates(geometry["coordinates"], project_coordinate)
    return transformed_geometry


def json_safe_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): json_safe_value(child_value) for key, child_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe_value(child_value) for child_value in value]
    return value


def ensure_output_available(output_path: Path, overwrite: bool) -> None:
    if output_path.exists() and not overwrite:
        raise ConversionError(f"Output already exists: {output_path}. Use --overwrite to replace it.")
    output_path.parent.mkdir(parents=True, exist_ok=True)


def convert_shapefile_to_geojson(
    source_path: Path,
    output_path: Path,
    target_crs: str,
    overwrite: bool,
) -> GeoJsonResult:
    try:
        import shapefile
    except ImportError as import_error:
        raise ConversionError(
            "Shapefile conversion requires pyshp. "
            f"{install_hint()}"
        ) from import_error

    ensure_output_available(output_path, overwrite)
    encoding_name = read_cpg_encoding(source_path)
    project_coordinate, source_crs = build_coordinate_projector(source_path, target_crs)
    reader = shapefile.Reader(str(source_path), encoding=encoding_name)

    feature_count = 0
    with output_path.open("w", encoding="utf-8") as output_file:
        output_file.write('{"type":"FeatureCollection","features":[\n')
        for shape_record in reader.iterShapeRecords():
            if feature_count:
                output_file.write(",\n")

            geometry = None
            if shape_record.shape.shapeType != shapefile.NULL:
                geometry = transform_geometry(shape_record.shape.__geo_interface__, project_coordinate)

            properties = {
                str(property_name): json_safe_value(property_value)
                for property_name, property_value in shape_record.record.as_dict().items()
            }
            feature = {"type": "Feature", "geometry": geometry, "properties": properties}
            json.dump(feature, output_file, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            feature_count += 1
        output_file.write("\n]}\n")

    return GeoJsonResult(source_path, output_path, feature_count, "pyshp", source_crs)


def count_geojson_features(geojson_path: Path) -> Optional[int]:
    try:
        with geojson_path.open("r", encoding="utf-8") as geojson_file:
            payload = json.load(geojson_file)
    except json.JSONDecodeError:
        return None

    if payload.get("type") == "FeatureCollection" and isinstance(payload.get("features"), list):
        return len(payload["features"])
    if payload.get("type") == "Feature":
        return 1
    return None


def copy_geojson(source_path: Path, output_path: Path, overwrite: bool) -> GeoJsonResult:
    ensure_output_available(output_path, overwrite)
    if source_path.resolve() != output_path.resolve():
        shutil.copy2(source_path, output_path)
    return GeoJsonResult(source_path, output_path, count_geojson_features(output_path), "copy", "already GeoJSON")


def is_geojson_payload(source_path: Path) -> bool:
    try:
        with source_path.open("r", encoding="utf-8") as source_file:
            payload = json.load(source_file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False

    payload_type = payload.get("type")
    return payload_type in {"FeatureCollection", "Feature", "GeometryCollection", "Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}


def convert_with_ogr2ogr(
    source_path: Path,
    output_path: Path,
    target_crs: str,
    overwrite: bool,
) -> GeoJsonResult:
    ogr2ogr_path = shutil.which("ogr2ogr")
    if not ogr2ogr_path:
        raise ConversionError(
            f"{source_path.suffix} input requires GDAL ogr2ogr, which was not found on PATH. "
            "Install GDAL or convert this source to Shapefile/GeoJSON first."
        )

    ensure_output_available(output_path, overwrite)
    command = [ogr2ogr_path, "-f", "GeoJSON", "-t_srs", target_crs]
    if overwrite:
        command.append("-overwrite")
    command.extend([str(output_path), str(source_path)])
    subprocess.run(command, check=True)
    return GeoJsonResult(source_path, output_path, count_geojson_features(output_path), "ogr2ogr", target_crs)


def convert_source_to_geojson(
    source_path: Path,
    output_path: Path,
    target_crs: str,
    overwrite: bool,
) -> GeoJsonResult:
    extension = source_path.suffix.lower()
    if extension == SHAPEFILE_EXTENSION:
        return convert_shapefile_to_geojson(source_path, output_path, target_crs, overwrite)
    if extension == ".geojson":
        return copy_geojson(source_path, output_path, overwrite)
    if extension == ".json":
        if is_geojson_payload(source_path):
            return copy_geojson(source_path, output_path, overwrite)
        return convert_with_ogr2ogr(source_path, output_path, target_crs, overwrite)
    if extension in OGR_EXTENSIONS:
        return convert_with_ogr2ogr(source_path, output_path, target_crs, overwrite)
    raise ConversionError(f"Unsupported vector file type: {source_path}")


def make_pmtiles(
    geojson_path: Path,
    output_path: Path,
    layer_name: str,
    overwrite: bool,
    min_zoom: Optional[int],
    max_zoom: Optional[int],
    extra_tippecanoe_args: list[str],
) -> PmtilesResult:
    tippecanoe_path = shutil.which("tippecanoe")
    if not tippecanoe_path:
        raise ConversionError(
            "PMTiles output requires tippecanoe, which was not found on PATH. "
            "On macOS, install it with: brew install tippecanoe"
        )

    ensure_output_available(output_path, overwrite)
    command = [
        tippecanoe_path,
        "-o",
        str(output_path),
        "-l",
        layer_name,
        "--drop-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        "--read-parallel",
    ]
    if overwrite:
        command.append("--force")
    if min_zoom is not None:
        command.extend(["-Z", str(min_zoom)])
    if max_zoom is None:
        command.append("-zg")
    else:
        command.extend(["-z", str(max_zoom)])
    command.extend(extra_tippecanoe_args)
    command.append(str(geojson_path))
    subprocess.run(command, check=True)
    return PmtilesResult(geojson_path, output_path, layer_name)


def source_output_stem(source_path: Path, layer_name: Optional[str], source_count: int) -> str:
    if layer_name and source_count == 1:
        return layer_name
    return source_path.stem


def is_hidden_path(path: Path) -> bool:
    return any(path_part.startswith(".") for path_part in path.parts)


def find_vector_sources(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() in {SHAPEFILE_EXTENSION, *DIRECT_GEOJSON_EXTENSIONS, *OGR_EXTENSIONS}:
            return [input_path]
        raise ConversionError(f"Unsupported input file: {input_path}")

    if not input_path.is_dir():
        raise ConversionError(f"Input does not exist: {input_path}")

    source_paths: list[Path] = []
    supported_extensions = {SHAPEFILE_EXTENSION, *DIRECT_GEOJSON_EXTENSIONS, *OGR_EXTENSIONS}
    for candidate_path in sorted(input_path.rglob("*")):
        relative_candidate = candidate_path.relative_to(input_path)
        if is_hidden_path(relative_candidate):
            continue
        if candidate_path.is_file() and candidate_path.suffix.lower() in supported_extensions:
            source_paths.append(candidate_path)

    if not source_paths:
        raise ConversionError(f"No supported vector sources found under: {input_path}")
    return source_paths


def safe_extract_zip(zip_path: Path, destination_path: Path) -> None:
    destination_root = destination_path.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_destination = (destination_root / member.filename).resolve()
            try:
                member_destination.relative_to(destination_root)
            except ValueError as value_error:
                raise ConversionError(f"Unsafe zip member path: {member.filename}") from value_error
        archive.extractall(destination_root)


@contextlib.contextmanager
def prepared_input_path(input_path: Path) -> Iterator[Path]:
    if input_path.suffix.lower() != ".zip":
        yield input_path
        return

    with tempfile.TemporaryDirectory(prefix="geo-converter-") as temporary_directory:
        extracted_path = Path(temporary_directory) / input_path.stem
        extracted_path.mkdir(parents=True, exist_ok=True)
        safe_extract_zip(input_path, extracted_path)
        yield extracted_path


def print_geojson_result(result: GeoJsonResult) -> None:
    count_text = "unknown" if result.feature_count is None else str(result.feature_count)
    print(
        f"GeoJSON: {result.output} "
        f"({count_text} features, source={result.source.name}, driver={result.driver}, source_crs={result.source_crs})"
    )


def print_pmtiles_result(result: PmtilesResult) -> None:
    print(f"PMTiles: {result.output} (layer={result.layer_name}, source={result.source.name})")


def run(args: argparse.Namespace) -> int:
    input_path = Path(args.input).expanduser().resolve()
    output_directory = Path(args.output).expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    pmtiles_only = args.format == "pmtiles" and not args.keep_intermediate
    temporary_geojson_context = tempfile.TemporaryDirectory(prefix="geojson-intermediate-") if pmtiles_only else None

    try:
        with prepared_input_path(input_path) as prepared_path:
            source_paths = find_vector_sources(prepared_path)
            geojson_directory = Path(temporary_geojson_context.name) if temporary_geojson_context else output_directory

            for source_path in source_paths:
                output_stem = source_output_stem(source_path, args.layer_name, len(source_paths))
                geojson_path = geojson_directory / f"{output_stem}.geojson"
                geojson_result = convert_source_to_geojson(source_path, geojson_path, args.target_crs, args.overwrite)

                if args.format in {"geojson", "both"} or args.keep_intermediate:
                    print_geojson_result(geojson_result)

                if args.format in {"pmtiles", "both"}:
                    pmtiles_path = output_directory / f"{output_stem}.pmtiles"
                    pmtiles_result = make_pmtiles(
                        geojson_result.output,
                        pmtiles_path,
                        output_stem,
                        args.overwrite,
                        args.min_zoom,
                        args.max_zoom,
                        args.tippecanoe_arg,
                    )
                    print_pmtiles_result(pmtiles_result)
    finally:
        if temporary_geojson_context:
            temporary_geojson_context.cleanup()

    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a zipped or extracted vector geospatial dataset to GeoJSON or PMTiles."
    )
    parser.add_argument("input", help="Input zip, folder, .shp, or GeoJSON path.")
    parser.add_argument("-o", "--output", default="./output", help="Output directory.")
    parser.add_argument(
        "--format",
        choices=["geojson", "pmtiles", "both"],
        default="geojson",
        help="Output format. PMTiles requires tippecanoe.",
    )
    parser.add_argument("--target-crs", default="EPSG:4326", help="Target CRS for GeoJSON output.")
    parser.add_argument("--layer-name", help="Layer/output name to use when the input has exactly one source.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output files.")
    parser.add_argument("--keep-intermediate", action="store_true", help="Keep GeoJSON when creating PMTiles.")
    parser.add_argument("--min-zoom", type=int, help="Minimum PMTiles zoom passed to tippecanoe as -Z.")
    parser.add_argument("--max-zoom", type=int, help="Maximum PMTiles zoom passed to tippecanoe as -z.")
    parser.add_argument(
        "--tippecanoe-arg",
        action="append",
        default=[],
        help="Extra argument passed through to tippecanoe. Repeat for multiple arguments.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return run(args)
    except subprocess.CalledProcessError as process_error:
        print(f"Command failed with exit code {process_error.returncode}: {process_error.cmd}", file=sys.stderr)
        return process_error.returncode or 1
    except ConversionError as conversion_error:
        print(f"Error: {conversion_error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())