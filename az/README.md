# Activation zones

One gzip-compressed `.geojson.gz` file per SOTA association, named with the association in lowercase (e.g. `w7w.geojson.gz`). `maketiles.sh` builds vector tiles from every `*.geojson.gz` in this directory.

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