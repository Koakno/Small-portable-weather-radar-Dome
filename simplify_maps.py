#!/usr/bin/env python3
"""
simplify_maps.py — One-time GeoJSON optimization script
Run this once from inside the portable_radar folder to reduce
map file sizes for faster loading over the Cloudflare tunnel.

Usage:
    cd portable_radar
    python3 simplify_maps.py

Tolerance of 0.001 degrees (~100 meters) removes redundant
coordinate points invisible at 20km radar scale. Typical results:
    indiana_roads.geojson:    27MB -> ~3-5MB
    indiana_counties.geojson:  6MB -> ~1-2MB

Safe to re-run — backs up originals before modifying.
"""

import json
import os
import shutil

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
FILES = [
    ("indiana_roads.geojson",    0.001),
    ("indiana_counties.geojson", 0.001),
]


def simplify_coords(coords, tolerance):
    """
    Remove intermediate points closer than tolerance degrees
    to the previous kept point. Preserves first and last point.
    """
    if len(coords) < 3:
        return coords
    result = [coords[0]]
    for point in coords[1:-1]:
        last = result[-1]
        if abs(point[0] - last[0]) > tolerance or \
           abs(point[1] - last[1]) > tolerance:
            result.append(point)
    result.append(coords[-1])
    return result


def simplify_geometry(geometry, tolerance):
    """Apply coordinate simplification to any GeoJSON geometry type."""
    if not geometry:
        return
    gtype = geometry["type"]

    if gtype == "Polygon":
        geometry["coordinates"] = [
            simplify_coords(ring, tolerance)
            for ring in geometry["coordinates"]
        ]
    elif gtype == "MultiPolygon":
        geometry["coordinates"] = [
            [simplify_coords(ring, tolerance) for ring in poly]
            for poly in geometry["coordinates"]
        ]
    elif gtype == "LineString":
        geometry["coordinates"] = simplify_coords(
            geometry["coordinates"], tolerance
        )
    elif gtype == "MultiLineString":
        geometry["coordinates"] = [
            simplify_coords(line, tolerance)
            for line in geometry["coordinates"]
        ]


def simplify_file(filename, tolerance):
    filepath = os.path.join(STATIC_DIR, filename)
    backup   = filepath + ".backup"

    if not os.path.exists(filepath):
        print(f"  [SKIP] {filename} not found in static/")
        return

    original_size = os.path.getsize(filepath) / (1024 * 1024)

    # Back up original if no backup exists yet
    if not os.path.exists(backup):
        shutil.copy2(filepath, backup)
        print(f"  [BACKUP] {filename}.backup created")

    print(f"  [LOAD]  {filename} ({original_size:.1f} MB)...")
    with open(filepath, "r") as f:
        data = json.load(f)

    feature_count = len(data.get("features", []))
    point_count_before = sum(
        len(c)
        for feat in data.get("features", [])
        if feat.get("geometry")
        for ring in (
            feat["geometry"]["coordinates"]
            if feat["geometry"]["type"] in ("Polygon", "MultiLineString")
            else [feat["geometry"]["coordinates"]]
        )
        for c in (ring if isinstance(ring[0], list) else [ring])
    )

    print(f"  [PROC]  {feature_count} features, simplifying...")
    for feature in data["features"]:
        simplify_geometry(feature.get("geometry"), tolerance)

    # Write compacted JSON (no spaces)
    print(f"  [SAVE]  Writing simplified file...")
    with open(filepath, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    new_size = os.path.getsize(filepath) / (1024 * 1024)
    reduction = (1 - new_size / original_size) * 100
    print(f"  [DONE]  {original_size:.1f} MB -> {new_size:.1f} MB "
          f"({reduction:.0f}% reduction)\n")


def main():
    print("=" * 50)
    print("  GeoJSON Map Simplifier")
    print("  portable_radar/simplify_maps.py")
    print("=" * 50 + "\n")

    if not os.path.isdir(STATIC_DIR):
        print(f"[ERROR] static/ directory not found at {STATIC_DIR}")
        print("        Run this script from inside the portable_radar folder.")
        return

    for filename, tolerance in FILES:
        print(f"Processing {filename} (tolerance: {tolerance} deg)...")
        simplify_file(filename, tolerance)

    print("All done. Restart Flask to serve the simplified files.")
    print("\nTo restore originals if needed:")
    for filename, _ in FILES:
        print(f"  cp static/{filename}.backup static/{filename}")


if __name__ == "__main__":
    main()
