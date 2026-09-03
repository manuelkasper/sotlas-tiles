# Activation zones

One gzip-compressed `.geojson.gz` file per SOTA association, named with the association in lowercase (e.g. `w7w.geojson.gz`). `maketiles.sh` builds vector tiles from every `*.geojson.gz` in this directory.

## Source data

* **ER**
  Derived from 1 arc-second SRTM data.
* **F, FL**
  Calculated using IGN RGE ALTI Digital Terrain Model 1m.
* **G**
  Calculated using Environment Agency LIDAR Composite DTM 1 m WCS data.
* **GM**
  Calculated using Scottish Remote Sensing Portal DTM catalogue and survey GeoTIFFs, including eligible Scottish National Land LiDAR Programme releases; survey-specific OGL coverage at 1 m or finer.
* **GW**
  Calculated using Welsh Government 32-bit DTM Cloud Optimized GeoTIFFs.
* **HB, HB0**
  Calculated using swissALTI3D data from swisstopo (spatial resolution 0.5 m, accuracy ± 0.3 – 3 m (1σ) depending on the region).
* **OE**
  Calculated using BEV ALS DTM data (spatial resolution 1 m, accuracy generally ± 0.5 m, may vary in high altitude).
* **OK**
  Calculated from the 5th Generation Digital Relief Model of the Czech Republic, an official high-precision digital geographic dataset managed by the Czech Office for Surveying, Mapping and Cadastre (ČÚZK) created by airborne laser scanning (LIDAR).
* **OM**
  Calculated using LiDAR DTM data (spatial resolution 20 m).
* **SP**
  Calculated using 1 m resolution Digital Terrain Model (NMT) from the Head Office of Geodesy and Cartography (GUGiK), derived from LiDAR surveys (EVRF2007 vertical reference).
* **KH0, KH2, KH6, KH8, KLA, KP4, W**
  Calculated using data from the U.S. Geological Survey 3D Elevation Program (3DEP).
* **W7W**
  Calculated using data from Washington State’s Department of Natural Resources public LiDAR portal.
* **ZL**
  Based on LiDAR data (generalised to a 4m x 4m grid) where available, or NZSoSDEM 15m contour-derived DEM grid otherwise.

## Adding a new association

Please create a `.geojson` file for the new association following the format specified below, gzip it (`gzip -n -9 w7w.geojson`), and submit a pull request or email it to mk@neon1.net. Also specify the source and accuracy of the data (for the info popup dialog that appears when a user clicks the blue "i" button next to the activation zones layer checkbox in the map options). Thanks!

## Required format

Each file must be a **single** JSON document (not NDJSON or concatenated objects) whose root is a `FeatureCollection`. Every feature is the activation zone of one summit:

- Geometry is a `Polygon`
- Vertices are 2D `[longitude, latitude]` with **at most 6 decimal digits**.
- `properties.summitCode` holds the SOTA reference, e.g. `KH8/MI-002`.
- Other properties are allowed if they are not just another copy of that code.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "summitCode": "KH8/MI-002" },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[-169.453024, -14.2331], [-169.452955, -14.233161], [-169.45289, -14.2331], [-169.453024, -14.2331]]]
      }
    }
  ]
}
```

## Checking a file

```sh
python3 check_geojson.py w7w.geojson.gz
python3 check_geojson.py *.geojson.gz
```

The script prints `OK` or `FAIL` for each file and exits with status 1 if any file is non-compliant.