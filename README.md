Whiffy - a WFS downloader

Copes with feature limits from a WFS server by splitting a 
bounding box in four each time a feature limit is hit.

Outputs GeoJSON.

Usage:
./whiffy.py landgate <feature> -14,129 -35,112 5000 > output.json

