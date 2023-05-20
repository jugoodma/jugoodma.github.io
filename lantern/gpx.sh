#!/bin/bash

# npm install -g npx

# ./gpx.sh file.gpx
npx -y @mapbox/togeojson $1 \
    | npx -y simplify-geojson -t 0.00005 \
    | jq -c "{type:.type, features: [{type: .features[].type, geometry: .features[].geometry}]}" \
    > "${1%%.*}.geojson"

