#!/bin/sh

set -e

cd /app/sotlas-tiles
rm -f summitslist.csv
wget -q https://www.sotadata.org.uk/summitslist.csv
php makegeojson.php
tippecanoe -qQ -z10 -B3 -pi -pg --force --drop-densest-as-needed --extend-zooms-if-still-dropping -o summits.mbtiles summits.geojson
tippecanoe -qQ -z10 -B3 -pi -pg --force --drop-densest-as-needed --extend-zooms-if-still-dropping -o summits_inactive.mbtiles summits_inactive.geojson
tippecanoe -qQ -z10 -B3 -pi -pg --force --drop-densest-as-needed --extend-zooms-if-still-dropping -o regions.mbtiles -L areas:regions_areas.geojson -L labels:regions_labels.geojson
cp *.mbtiles /data/tiles
su pm2 -c "pm2 restart tileserver" > /dev/null

# Copy tiles to US map server and restart tile server
scp -q *.mbtiles root@map-us.sotl.as:/data/tiles
ssh root@map-us.sotl.as 'su pm2 -c "pm2 restart tileserver" > /dev/null'
