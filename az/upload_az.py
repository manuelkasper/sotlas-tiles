#!/usr/bin/env python3
"""Split association AZ FeatureCollections into per-summit files and upload them.

Each input file is checked with check_geojson.py, then every feature is uploaded
to DigitalOcean Spaces as both GeoJSON and GPX, using the summit code as the
object key (e.g. G/CE-001 -> s3://sotlas-az/G/CE/001.geojson). Bodies are gzip
compressed and served with Content-Encoding: gzip so browsers decompress them
on download.

Requires boto3. Credentials (same names as sotlas-api):

  SPACES_ACCESS_KEY
  SPACES_SECRET_KEY
  SPACES_ENDPOINT   default https://fra1.digitaloceanspaces.com
  SPACES_REGION     default fra1 (or parsed from the endpoint)
  SPACES_BUCKET     default sotlas-az

Optional: a .env file in the current directory or the repo root is loaded
without overriding variables already set in the environment.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from check_geojson import check, read_geojson_text

GPX_NS = "http://www.topografix.com/GPX/1/1"
GEOJSON_CONTENT_TYPE = "application/geo+json"
GPX_CONTENT_TYPE = "application/gpx+xml"

DEFAULT_REGION = "fra1"
DEFAULT_ENDPOINT = f"https://{DEFAULT_REGION}.digitaloceanspaces.com"
DEFAULT_BUCKET = "sotlas-az"
DEFAULT_JOBS = 16
PROGRESS_EVERY = 50
ERROR_EXAMPLES = 8

ET.register_namespace("", GPX_NS)


def load_dotenv() -> None:
    here = Path(__file__).resolve().parent
    candidates = [Path.cwd() / ".env", here / ".env", here.parent / ".env"]
    seen: set[Path] = set()
    for path in candidates:
        path = path.resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), _unquote(value.strip()))


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def normalize_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip()
    if not endpoint.startswith(("http://", "https://")):
        endpoint = "https://" + endpoint
    return endpoint.rstrip("/")


def region_from_endpoint(endpoint: str) -> str:
    host = endpoint.split("://", 1)[-1].split("/", 1)[0]
    if host.endswith(".digitaloceanspaces.com"):
        region = host.split(".", 1)[0]
        if region:
            return region
    return DEFAULT_REGION


def summit_key_base(summit_code: str) -> str:
    association, rest = summit_code.split("/", 1)
    region, number = rest.split("-", 1)
    return f"{association}/{region}/{number}"


def feature_geojson_bytes(feature: dict) -> bytes:
    collection = {"type": "FeatureCollection", "features": [feature]}
    return json.dumps(collection, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _fmt_coord(value: float) -> str:
    text = f"{value:.6f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _iter_rings(geometry: dict) -> Iterator[list]:
    gtype = geometry["type"]
    coords = geometry["coordinates"]
    if gtype == "Polygon":
        yield from coords
    elif gtype == "MultiPolygon":
        for polygon in coords:
            yield from polygon
    else:
        raise ValueError(f"unsupported geometry type {gtype!r}")


def feature_gpx_bytes(feature: dict) -> bytes:
    code = str((feature.get("properties") or {}).get("summitCode", ""))

    gpx = ET.Element(f"{{{GPX_NS}}}gpx", {"version": "1.1", "creator": "sotlas-tiles"})
    metadata = ET.SubElement(gpx, f"{{{GPX_NS}}}metadata")
    ET.SubElement(metadata, f"{{{GPX_NS}}}name").text = f"Activation zone for {code}"

    trk = ET.SubElement(gpx, f"{{{GPX_NS}}}trk")
    ET.SubElement(trk, f"{{{GPX_NS}}}name").text = code
    ET.SubElement(trk, f"{{{GPX_NS}}}desc").text = code

    for ring in _iter_rings(feature["geometry"]):
        seg = ET.SubElement(trk, f"{{{GPX_NS}}}trkseg")
        for point in ring:
            ET.SubElement(
                seg,
                f"{{{GPX_NS}}}trkpt",
                {"lat": _fmt_coord(point[1]), "lon": _fmt_coord(point[0])},
            )

    return ET.tostring(gpx, encoding="utf-8", xml_declaration=True)


def make_s3_client(endpoint: str, region: str, access_key: str, secret_key: str, jobs: int) -> Any:
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            s3={"addressing_style": "virtual"},
            retries={"max_attempts": 8, "mode": "standard"},
            max_pool_connections=max(jobs, 10),
        ),
    )


def put_object(client: Any, bucket: str, key: str, body: bytes, content_type: str) -> None:
    filename = key.rsplit("/", 1)[-1]
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=gzip.compress(body, compresslevel=9, mtime=0),
        ContentType=content_type,
        ContentEncoding="gzip",
        ContentDisposition=f'attachment; filename="{filename}"',
        ACL="public-read",
    )


def process_feature(client: Any, bucket: str, feature: dict) -> None:
    base = summit_key_base(feature["properties"]["summitCode"])
    put_object(client, bucket, f"{base}.geojson", feature_geojson_bytes(feature), GEOJSON_CONTENT_TYPE)
    put_object(client, bucket, f"{base}.gpx", feature_gpx_bytes(feature), GPX_CONTENT_TYPE)


def _print_fail(path: str, details: list[str]) -> None:
    print(f"FAIL {path}")
    for detail in details:
        print(f"  - {detail}")


def _summit_label(n: int) -> str:
    return f"{n} summit" if n == 1 else f"{n} summits"


def process_file(path: str, client: Any | None, bucket: str, jobs: int, dry_run: bool) -> int:
    issues = check(path)
    if issues:
        _print_fail(path, issues)
        return 1

    data = json.loads(read_geojson_text(path))
    features = data["features"]
    n = len(features)
    example = summit_key_base(features[0]["properties"]["summitCode"]) if features else ""

    if dry_run:
        for feature in features:
            feature_geojson_bytes(feature)
            feature_gpx_bytes(feature)
        print(f"OK   {path} ({_summit_label(n)})")
        print(f"  dry-run: would upload {n} .geojson + {n} .gpx to s3://{bucket}/")
        if example:
            print(f"  e.g. {example}.geojson, {example}.gpx")
        return 0

    errors: list[str] = []
    done = 0
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(process_feature, client, bucket, feat): feat["properties"]["summitCode"]
            for feat in features
        }
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                errors.append(f"{futures[fut]}: {e}")
            done += 1
            if done % PROGRESS_EVERY == 0 or done == n:
                print(f"  {path}: {done}/{n}", flush=True)

    if errors:
        extra = [f"({len(errors) - ERROR_EXAMPLES} more)"] if len(errors) > ERROR_EXAMPLES else []
        _print_fail(path, [f"{len(errors)} upload error(s)", *errors[:ERROR_EXAMPLES], *extra])
        return 1

    print(f"OK   {path} ({_summit_label(n)} uploaded to s3://{bucket}/)")
    if example:
        print(f"  e.g. {example}.geojson, {example}.gpx")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Upload per-summit AZ polygons (GeoJSON + GPX) to DigitalOcean Spaces."
    )
    parser.add_argument("files", nargs="+", help="association GeoJSON FeatureCollection files")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and convert without uploading",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        metavar="N",
        help=f"parallel uploads (default {DEFAULT_JOBS})",
    )
    args = parser.parse_args(argv)

    if args.jobs < 1:
        print("error: --jobs must be >= 1", file=sys.stderr)
        return 2

    load_dotenv()

    client = None
    bucket = os.environ.get("SPACES_BUCKET", DEFAULT_BUCKET)
    if not args.dry_run:
        access_key = os.environ.get("SPACES_ACCESS_KEY")
        secret_key = os.environ.get("SPACES_SECRET_KEY")
        if not access_key or not secret_key:
            print(
                "error: SPACES_ACCESS_KEY and SPACES_SECRET_KEY must be set "
                "(or provided in a .env file)",
                file=sys.stderr,
            )
            return 2
        endpoint = normalize_endpoint(os.environ.get("SPACES_ENDPOINT", DEFAULT_ENDPOINT))
        region = os.environ.get("SPACES_REGION") or region_from_endpoint(endpoint)
        try:
            client = make_s3_client(endpoint, region, access_key, secret_key, args.jobs)
        except ImportError:
            print("error: boto3 is required (pip install boto3)", file=sys.stderr)
            return 2

    failed = 0
    for path in args.files:
        failed += process_file(path, client, bucket, args.jobs, args.dry_run)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
