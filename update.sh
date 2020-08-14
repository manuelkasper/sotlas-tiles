#!/bin/sh

set -e

cd /data/tiles
rm -f summitslist.csv
/usr/local/bin/wget -q https://www.sotadata.org.uk/summitslist.csv
/usr/local/bin/php makegeojson.php
/usr/local/bin/tippecanoe -qQ -z10 -B3 -pi -pg --force --drop-densest-as-needed --extend-zooms-if-still-dropping -o summits.mbtiles summits.geojson
/usr/local/bin/tippecanoe -qQ -z10 -B3 -pi -pg --force --drop-densest-as-needed --extend-zooms-if-still-dropping -o summits_inactive.mbtiles summits_inactive.geojson
/usr/local/bin/tippecanoe -qQ -z10 -B3 -pi -pg --force --drop-densest-as-needed --extend-zooms-if-still-dropping -o regions.mbtiles -L areas:regions_areas.geojson -L labels:regions_labels.geojson
cp *.mbtiles /data/openmaptiles
su pm2 -c "/usr/local/bin/pm2 restart tileserver" > /dev/null

# Copy tiles to US map server and restart tile server
scp -q *.mbtiles root@map-us.sotl.as:/data/openmaptiles
ssh root@map-us.sotl.as 'su pm2 -c "/usr/local/bin/pm2 restart tileserver" > /dev/null'
