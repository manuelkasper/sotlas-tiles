#!/bin/sh

tippecanoe -Z12 -pg --force --drop-densest-as-needed --extend-zooms-if-still-dropping -o az.mbtiles -l az *.geojson
