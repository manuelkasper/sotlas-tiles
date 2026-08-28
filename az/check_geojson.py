#!/usr/bin/env python3
"""Check that a GeoJSON file matches the AZ FeatureCollection convention.

A compliant file is a single JSON document whose root is a FeatureCollection.
Every feature must be a Polygon (or MultiPolygon, when an AZ is disjoint)
and must have a SOTA reference in properties.summitCode (e.g. KH8/MI-002).
Vertex coordinates must be 2D [lon, lat] with at most 6 decimal digits.
"""

from __future__ import annotations

import json
import re
import sys

SOTA_REF = re.compile(r"^[A-Z0-9]+/[A-Z]{2}-\d{3}$")
POLYGON_TYPES = {"Polygon", "MultiPolygon"}
MAX_DECIMAL_DIGITS = 6
# Floats that match 6 d.p. after JSON parse may still differ by a few ULPs.
PRECISION_TOLERANCE = 1e-9


def check(path: str) -> list[str]:
    issues: list[str] = []
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    decoder = json.JSONDecoder()
    try:
        data, end = decoder.raw_decode(raw)
    except json.JSONDecodeError as e:
        return [f"invalid JSON: {e}"]

    trailing = raw[end:].strip()
    if trailing:
        issues.append(
            "file contains extra JSON after the first value "
            "(concatenated documents or NDJSON); expected one FeatureCollection"
        )

    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        root_type = data.get("type") if isinstance(data, dict) else type(data).__name__
        issues.append(f"root type is {root_type!r}, not FeatureCollection")
        return issues

    features = data.get("features")
    if not isinstance(features, list):
        issues.append("missing or non-array 'features'")
        return issues
    if not features:
        issues.append("FeatureCollection has no features")
        return issues

    seen_codes: dict[str, int] = {}
    not_feature = 0
    missing_props = 0
    bad_code = 0
    missing_geom = 0
    bad_geom = 0
    over_precision = 0
    not_2d = 0
    examples: list[str] = []

    def note(kind: str, detail: str) -> None:
        if len(examples) < 8:
            examples.append(f"{kind}: {detail}")

    for i, feat in enumerate(features):
        prefix = f"features[{i}]"
        if not isinstance(feat, dict) or feat.get("type") != "Feature":
            not_feature += 1
            note("not a Feature", prefix)
            continue

        props = feat.get("properties")
        code = None
        if not isinstance(props, dict):
            missing_props += 1
            note("missing properties", prefix)
        else:
            code = props.get("summitCode")
            if not isinstance(code, str) or not SOTA_REF.match(code):
                bad_code += 1
                note("bad summitCode", f"{prefix} has {code!r}")

        if isinstance(code, str) and SOTA_REF.match(code):
            seen_codes[code] = seen_codes.get(code, 0) + 1

        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            missing_geom += 1
            note("missing geometry", prefix)
            continue
        gtype = geom.get("type")
        if gtype not in POLYGON_TYPES:
            bad_geom += 1
            note("bad geometry", f"{prefix} type={gtype!r}")
            continue
        coord_issues = _check_coords(geom.get("coordinates"), prefix)
        for issue in coord_issues:
            if "not 2D" in issue:
                not_2d += 1
            elif "decimal digits" in issue:
                over_precision += 1
            if len(examples) < 8:
                examples.append(issue)

    def count_issue(n: int, label: str) -> None:
        if n:
            issues.append(f"{n} {label}")

    count_issue(not_feature, "feature(s) are not GeoJSON Feature objects")
    count_issue(missing_props, "feature(s) missing a properties object")
    count_issue(bad_code, "feature(s) missing a valid properties.summitCode")
    count_issue(missing_geom, "feature(s) missing geometry")
    count_issue(bad_geom, "feature(s) whose geometry is not Polygon or MultiPolygon")
    count_issue(not_2d, "feature(s) with vertices that are not 2D [lon, lat]")
    count_issue(over_precision, "feature(s) with coordinates of more than 6 decimal digits")
    for example in examples:
        issues.append(f"e.g. {example}")

    dups = [c for c, n in seen_codes.items() if n > 1]
    if dups:
        sample = ", ".join(dups[:5])
        extra = f" (+{len(dups) - 5} more)" if len(dups) > 5 else ""
        issues.append(f"duplicate summitCode values: {sample}{extra}")

    return issues


def _check_coords(coords, prefix: str) -> list[str]:
    issues: list[str] = []
    over_precision = 0
    not_2d = 0

    def walk(value, depth: int) -> None:
        nonlocal over_precision, not_2d
        if not isinstance(value, list) or not value:
            return
        if isinstance(value[0], (int, float)):
            if len(value) != 2:
                not_2d += 1
            for n in value[:2]:
                if isinstance(n, (int, float)) and abs(n - round(n, MAX_DECIMAL_DIGITS)) > PRECISION_TOLERANCE:
                    over_precision += 1
            return
        for item in value:
            walk(item, depth + 1)

    walk(coords, 0)
    if not_2d:
        issues.append(f"{prefix}: {not_2d} vertex/vertices are not 2D [lon, lat]")
    if over_precision:
        issues.append(
            f"{prefix}: {over_precision} coordinate value(s) have more than "
            f"{MAX_DECIMAL_DIGITS} decimal digits"
        )
    return issues


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: check_geojson.py FILE [FILE ...]", file=sys.stderr)
        return 2

    failed = 0
    for path in args:
        issues = check(path)
        if issues:
            failed += 1
            print(f"FAIL {path}")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"OK   {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
