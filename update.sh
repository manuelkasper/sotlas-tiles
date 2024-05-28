#!/bin/sh

set -e

cd /app/sotlas-tiles
export $(grep -v '^#' .env | xargs)

rm -f summitslist.csv
wget -q https://www.sotadata.org.uk/summitslist.csv
php makegeojson.php
tippecanoe -qQ -z10 -B3 -pi -pg --force --drop-densest-as-needed --extend-zooms-if-still-dropping -o summits.mbtiles summits.geojson
tippecanoe -qQ -z10 -B3 -pi -pg --force --drop-densest-as-needed --extend-zooms-if-still-dropping -o summits_inactive.mbtiles summits_inactive.geojson
tippecanoe -qQ -z10 -B3 -pi -pg --force --drop-densest-as-needed --extend-zooms-if-still-dropping -o regions.mbtiles -L areas:regions_areas.geojson -L labels:regions_labels.geojson

# Upload tiles to MapTiler
.venv/bin/maptiler-cloud --token=$MAPTILER_UPLOAD_TOKEN tiles ingest --document-id=d6ccc3ec-a677-4fcd-a211-2f2da36965cb summits.mbtiles > /dev/null
.venv/bin/maptiler-cloud --token=$MAPTILER_UPLOAD_TOKEN tiles ingest --document-id=ac4e1bc3-fbfb-4830-8279-675cc18f86f0 summits_inactive.mbtiles > /dev/null
.venv/bin/maptiler-cloud --token=$MAPTILER_UPLOAD_TOKEN tiles ingest --document-id=2d324268-fe52-4875-96ca-bc5692fc1225 regions.mbtiles > /dev/null
