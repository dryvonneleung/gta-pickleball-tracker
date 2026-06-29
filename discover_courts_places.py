#!/usr/bin/env python3
"""
Discover pickleball venues across the GTA using the Google Places API (New).

This is a DISCOVERY step (Stage 1) for private/commercial venues that aren't in
municipal open data. It tiles the GTA into overlapping search circles, runs a
"pickleball" Text Search in each, de-dupes by place id, drops venues already in
courts-data.js, and MERGES new candidates into private-courts-candidates.json
for you to review. It does NOT modify courts-data.js.

Setup:
  Create a Google Cloud project, enable the "Places API (New)", create an API
  key, and export it:

      export GOOGLE_PLACES_API_KEY=your_key_here

  (You can also put it in a .env file — it's gitignored.)

Usage:
  python3 discover_courts_places.py                 # full GTA grid
  python3 discover_courts_places.py --max-pages 1   # cheaper (≤20 results/tile)
  python3 discover_courts_places.py --bbox 43.7,-79.5,43.9,-79.2   # small area
  python3 discover_courts_places.py --query "indoor pickleball club"

Cost note: Text Search is billed per request. The script logs how many requests
it will make before starting; Google's recurring free credit covers light use.

Requires network access to https://places.googleapis.com (no extra pip deps).
"""

import os
import re
import sys
import json
import math
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).parent
COURTS_FILE = SCRIPT_DIR / "courts-data.js"
OUT_FILE = SCRIPT_DIR / "private-courts-candidates.json"

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

# Populated-GTA bounding box (south, west, north, east). Covers the lakeshore
# (Burlington/Oshawa) up to Georgina, and Halton west to Clarington east.
DEFAULT_BBOX = (43.3, -80.2, 44.4, -78.6)
DEFAULT_STEP = 0.2       # degrees between tile centers (~16-22 km)
DEFAULT_RADIUS = 14000   # meters, search circle radius per tile (overlaps neighbours)
DEDUPE_RADIUS_M = 200

FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.websiteUri",
    "places.nationalPhoneNumber",
    "places.primaryType",
    "places.types",
    "places.regularOpeningHours.weekdayDescriptions",
    "nextPageToken",
])


def haversine_m(a_lat, a_lng, b_lat, b_lng):
    R = 6371000
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dlat = math.radians(b_lat - a_lat)
    dlng = math.radians(b_lng - a_lng)
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def build_grid(bbox, step):
    s, w, n, e = bbox
    centers = []
    lat = s
    while lat <= n + 1e-9:
        lng = w
        while lng <= e + 1e-9:
            centers.append((round(lat, 5), round(lng, 5)))
            lng += step
        lat += step
    return centers


def places_text_search(query, center, radius, page_token=None):
    body = {
        "textQuery": query,
        "locationBias": {
            "circle": {
                "center": {"latitude": center[0], "longitude": center[1]},
                "radius": float(radius),
            }
        },
    }
    if page_token:
        body["pageToken"] = page_token
    req = urllib.request.Request(
        PLACES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": FIELD_MASK,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("places", []), data.get("nextPageToken")


def load_existing_courts():
    if not COURTS_FILE.exists():
        return []
    text = COURTS_FILE.read_text(encoding="utf-8")
    out = []
    for block in re.findall(r"\{[^{}]*\}", text, re.S):
        name = re.search(r'name:\s*"([^"]*)"', block)
        lat = re.search(r"lat:\s*(-?\d+\.?\d*)", block)
        lng = re.search(r"lng:\s*(-?\d+\.?\d*)", block)
        if name and lat and lng:
            out.append((name.group(1), float(lat.group(1)), float(lng.group(1))))
    return out


def in_bbox(lat, lng, bbox):
    s, w, n, e = bbox
    return s <= lat <= n and w <= lng <= e


SPORT_HINTS = ("sport", "athletic", "recreation", "gym", "fitness", "club", "park", "stadium", "arena")
RETAIL_TYPES = {"store", "shopping_mall", "restaurant", "cafe", "bar", "lodging",
                "supermarket", "clothing_store", "sporting_goods_store", "shoe_store"}


def infer_type(name, types):
    blob = (name + " " + " ".join(types)).lower()
    if any(k in blob for k in ("indoor", "centre", "center", "club", "gym", "fitness", "arena", "complex")):
        return "indoor"
    return "outdoor"


def to_candidate(place):
    name = (place.get("displayName") or {}).get("text")
    loc = place.get("location") or {}
    lat, lng = loc.get("latitude"), loc.get("longitude")
    if not name or lat is None or lng is None:
        return None
    types = place.get("types", [])
    hours = "; ".join((place.get("regularOpeningHours") or {}).get("weekdayDescriptions", []))
    phone = place.get("nationalPhoneNumber", "")
    notes = "From Google Places — verify details (court count, indoor/outdoor, access)."
    if phone:
        notes += f" Phone: {phone}."
    # confidence: is this plausibly a pickleball venue?
    blob = (name + " " + " ".join(types)).lower()
    is_retail = bool(set(types) & RETAIL_TYPES)
    likely = ("pickle" in blob) or (any(h in blob for h in SPORT_HINTS) and not is_retail)
    return {
        "id": None,
        "name": name,
        "city": "",
        "address": place.get("formattedAddress", ""),
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "type": infer_type(name, types),
        "numCourts": None,
        "surface": "",
        "access": "Unknown — verify",
        "hours": hours,
        "amenities": [],
        "website": place.get("websiteUri", ""),
        "notes": notes,
        "_source": "google_places",
        "_place_id": place.get("id", ""),
        "_types": types,
        "_low_confidence": not likely,
    }


def main():
    ap = argparse.ArgumentParser(description="Discover GTA pickleball venues via Google Places API (New)")
    ap.add_argument("--query", default="pickleball")
    ap.add_argument("--bbox", help="south,west,north,east")
    ap.add_argument("--step", type=float, default=DEFAULT_STEP)
    ap.add_argument("--radius", type=float, default=DEFAULT_RADIUS)
    ap.add_argument("--max-pages", type=int, default=2, help="pages per tile (1-3, 20 results each)")
    ap.add_argument("--all", action="store_true", help="include venues already in courts-data.js")
    args = ap.parse_args()

    if not API_KEY:
        print("ERROR: GOOGLE_PLACES_API_KEY is not set. Export it or add it to .env.")
        sys.exit(1)

    bbox = tuple(float(x) for x in args.bbox.split(",")) if args.bbox else DEFAULT_BBOX
    centers = build_grid(bbox, args.step)
    max_pages = max(1, min(3, args.max_pages))
    print(f"GTA grid: {len(centers)} tiles × up to {max_pages} page(s) "
          f"→ up to {len(centers) * max_pages} Places requests.")

    seen_ids, raw = set(), []
    for i, c in enumerate(centers, 1):
        token = None
        for page in range(max_pages):
            try:
                places, token = places_text_search(args.query, c, args.radius, token)
            except urllib.error.HTTPError as ex:
                print(f"  tile {i}: HTTP {ex.code} {ex.read()[:160].decode('utf-8','replace')}")
                break
            except urllib.error.URLError as ex:
                print(f"  tile {i}: network error {ex}; need access to places.googleapis.com")
                break
            for pl in places:
                pid = pl.get("id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    raw.append(pl)
            if not token:
                break
            time.sleep(2)  # nextPageToken needs a moment to become valid
        if i % 10 == 0:
            print(f"  …{i}/{len(centers)} tiles, {len(raw)} unique places so far")

    print(f"Collected {len(raw)} unique places from Google Places.")

    existing = load_existing_courts()
    prior = []
    if OUT_FILE.exists():
        try:
            prior = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prior = []

    def is_dupe(cand, pool):
        key = cand["name"].lower().strip()
        for (nm, la, ln) in pool:
            if nm.lower().strip() == key or haversine_m(cand["lat"], cand["lng"], la, ln) < DEDUPE_RADIUS_M:
                return True
        return False

    existing_pool = [(n, la, ln) for (n, la, ln) in existing]
    prior_pool = [(p.get("name", ""), p.get("lat", 0), p.get("lng", 0)) for p in prior]

    added, skipped = [], 0
    for pl in raw:
        cand = to_candidate(pl)
        if not cand or not in_bbox(cand["lat"], cand["lng"], bbox):
            continue
        if not args.all and is_dupe(cand, existing_pool):
            skipped += 1
            continue
        if is_dupe(cand, prior_pool):
            continue
        added.append(cand)
        prior_pool.append((cand["name"], cand["lat"], cand["lng"]))

    merged = prior + added
    OUT_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n  {len(added)} new candidate(s) added ({skipped} already in courts-data.js).")
    print(f"  {len(merged)} total candidate(s) in {OUT_FILE.name}.")
    lowc = sum(1 for c in added if c.get("_low_confidence"))
    if lowc:
        print(f"  ({lowc} flagged _low_confidence — likely not pickleball venues; check before adding.)")
    if added:
        print("\n  Preview:")
        for c in added[:15]:
            site = f"  [{c['website']}]" if c["website"] else ""
            flag = " (?)" if c["_low_confidence"] else ""
            print(f"    • {c['name']}{flag} — {c['address'] or '(no address)'}{site}")
    print("\nNext: review the JSON, set type/access/numCourts, then paste vetted entries into courts-data.js.")


if __name__ == "__main__":
    main()
