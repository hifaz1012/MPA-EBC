# Geospatial Converter

Generic CLI tool to convert zipped or extracted vector geospatial datasets into GeoJSON and optionally PMTiles.

The converter is designed to work for repeatable ingestion pipelines where datasets are downloaded as zip files, extracted, and normalized into map-friendly formats.

## Features

- Accepts input as zip file, folder, `.shp`, `.geojson`, or `.json`.
- Recursively discovers supported vector files in a folder.
- Converts Shapefile to GeoJSON using `pyshp`.
- Reprojects coordinates to a target CRS (default `EPSG:4326`) using `pyproj` when needed.
- Creates PMTiles via `tippecanoe` (optional dependency).
- Supports batch processing when multiple sources exist inside one input folder/zip.

## Supported Input Types

- Native path handling:
  - `.zip` (auto-extract to temp folder)
  - Directory
  - Single vector file
- Vector formats:
  - `.shp`
  - `.geojson`
  - `.json` (copied directly when valid GeoJSON, otherwise converted via GDAL `ogr2ogr`)
  - `.gpkg`, `.kml`, `.gml`, `.fgb` (via GDAL `ogr2ogr`)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Optional: PMTiles Support

PMTiles output requires `tippecanoe`.

macOS:

```bash
brew install tippecanoe
```

## Usage

Run from this directory:

```bash
python geo_converter.py <input> [options]
```

Or from another directory:

```bash
python path/to/geo_converter.py <input> [options]
```

### Convert Zip To GeoJSON

```bash
python geo_converter.py ./datasets/sample.zip \
  --output ./output \
  --format geojson \
  --overwrite
```

### Convert Folder To PMTiles

```bash
python geo_converter.py ./datasets/sample_folder \
  --output ./output \
  --format pmtiles \
  --overwrite
```

### Produce Both GeoJSON And PMTiles

```bash
python geo_converter.py ./datasets/sample_folder \
  --output ./output \
  --format both \
  --overwrite
```

### Common Options

- `--target-crs EPSG:4326` target CRS for output GeoJSON
- `--layer-name <name>` override output stem when there is exactly one source
- `--min-zoom <z>` and `--max-zoom <z>` PMTiles zoom controls
- `--tippecanoe-arg <arg>` pass extra arguments to `tippecanoe` (repeatable)
- `--keep-intermediate` keep generated GeoJSON when format is `pmtiles`

See full help:

```bash
python geo_converter.py --help
```

## Output Behavior

- Each discovered source creates one output file stem.
- Default output directory is `./output`.
- Existing files are protected unless `--overwrite` is set.

## Notes

- This tool is focused on vector data. Raster formats are not handled.
- Some formats require GDAL `ogr2ogr` to be installed and available on `PATH`.
- For map visualization platforms like Microsoft Fabric Maps, both GeoJSON and PMTiles are supported vector layer formats.
