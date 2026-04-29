# Geospatial Converter

CLI tool for converting vector geospatial datasets into GeoJSON and optionally PMTiles.

> This project is for self-development, workflow experimentation, and learning only. It is not intended as a production-ready geospatial pipeline.

## What it does

The converter accepts common vector inputs and writes normalized outputs that are easier to inspect, reuse, or load into mapping workflows.

Supported input patterns include:

- zip archives
- extracted folders
- shapefiles (`.shp`)
- GeoJSON / JSON
- selected GDAL-supported vector formats

Supported outputs:

- GeoJSON
- PMTiles (optional)

## Requirements

- Python 3.11+
- `pyshp`
- `pyproj`
- `tippecanoe` for PMTiles output

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Show help:

```bash
python geo_converter.py --help
```

Convert to GeoJSON:

```bash
python geo_converter.py ./data/sample.zip --output ./output --format geojson
```

Convert to PMTiles:

```bash
python geo_converter.py ./data/sample_folder --output ./output --format pmtiles
```

## Notes

- This tool is focused on vector data.
- Some formats depend on external GDAL tooling being available on `PATH`.
- PMTiles output requires `tippecanoe`.
- The code is aimed at personal learning and repeatable local workflows, not hardened production use.