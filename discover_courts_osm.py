#!/usr/bin/env python3
"""
Discover pickleball venues across the GTA from OpenStreetMap (Overpass API).

This is a DISCOVERY step (Stage 1): it finds candidate venues — including
private/commercial clubs — and writes them to private-courts-candidates.json
for you to review before adding to courts-data.js. It does NOT modify
courts-data.js. Coordinates/names from OSM should be sanity-checked, and you
can enrich details (court count, hours) by running auto_update.py against each
venue's website (Stage 2).

Data © OpenStreetMap contributors, licensed under the ODbL. If you publish
this data, attribute OpenStreetMap.

Usage:
  python3 discover_courts_osm.py            # query GTA, dedupe, write candidates
  python3 discover_courts_osm.py --all      # include matches already in courts-data.js

Requires network access to https://overpass-api.de (no API key needed).
"""

import re
import json
import math
import argparse
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
COURTS_FILE = SCRIPT_DIR / "courts-data.js"
OUT_FILE = SCRIPT_DIR / "private-courts-candidates.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# GTA bounding box (south, west, north, east) with a small margin.
BBOX = (43.0, -80.5, 44.6, -78.3)

# Roughly how close (meters) an OSM hit must be to an existing court to be
# treated as a duplicate and skipped.
DEDUPE_RADIUS_M = 200


def overpass_query(bbox) -> str:
    s, w, n, e = bbox
    b = f"{s},{w},{n},{e}"
    return f"""
[out:json][timeout:120];
(
  nwr["leisure"="pitch"]["sport"~"pickleball"]({b});
  nwr["sport"~"pickleball"]({b});
  nwr["name"~"pickle",i]({b});
);
out center tags;
""".strip()


def fetch_overpass(query: str) -> dict:
    data = ("data=" + urllib.parse.quote(query)).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "GTAPickleballBot/1.0 (+https://dryvonneleung.github.io/gta-pickleball-tracker)"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def haversine_m(a_lat, a_lng, b_lat, b_lng) -> float:
    R = 6371000
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dlat = math.radians(b_lat - a_lat)
    dlng = math.radians(b_lng - a_lng)
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def load_existing_courts():
    """Lightweight extraction of (name, lat, lng) from courts-data.js."""
    if not COURTS_FILE.exists():
        return []
    text = COURTS_FILE.read_text(encoding="utf-8")
    existing = []
    for block in re.findall(r"\{[^{}]*\}", text, re.S):
        name = re.search(r'name:\s*"([^"]*)"', block)
        lat = re.search(r"lat:\s*(-?\d+\.?\d*)", block)
        lng = re.search(r"lng:\s*(-?\d+\.?\d*)", block)
        if name and lat and lng:
            existing.append((name.group(1), float(lat.group(1)), float(lng.group(1))))
    return existing


def elem_latlng(el):
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    c = el.get("center")
    if c:
        return c["lat"], c["lon"]
    return None, None


def build_address(tags):
    parts = []
    if tags.get("addr:housenumber"):
        parts.append(tags["addr:housenumber"])
    if tags.get("addr:street"):
        parts.append(tags["addr:street"])
    line = " ".join(parts)
    city = tags.get("addr:city", "")
    bits = [b for b in [line, city, "ON"] if b]
    return ", ".join(bits)


def derive_access(tags):
    access = (tags.get("access") or "").lower()
    fee = (tags.get("fee") or "").lower()
    if access in ("private", "members", "membership"):
        return "Private — Members"
    if access == "customers" or fee in ("yes", "1", "true"):
        return "Private — Paid"
    if fee == "no" or access in ("yes", "public"):
        return "Public — Free"
    return "Unknown — verify"


def to_candidate(el):
    tags = el.get("tags", {})
    name = tags.get("name")
    if not name:
        return None
    lat, lng = elem_latlng(el)
    if lat is None:
        return None
    website = tags.get("website") or tags.get("contact:website") or ""
    indoor = tags.get("indoor") == "yes" or tags.get("building") is not None
    return {
        "id": None,  # assign before adding to courts-data.js
        "name": name,
        "city": tags.get("addr:city", ""),
        "address": build_address(tags),
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "type": "indoor" if indoor else "outdoor",
        "numCourts": int(tags["pickleball"]) if str(tags.get("pickleball", "")).isdigit() else None,
        "surface": (tags.get("surface") or "").title(),
        "access": derive_access(tags),
        "hours": tags.get("opening_hours", ""),
        "amenities": [],
        "website": website,
        "notes": "Imported from OpenStreetMap — verify details (court count, hours, access).",
        "_osm": f"{el['type']}/{el['id']}",
    }


def main():
    ap = argparse.ArgumentParser(description="Discover GTA pickleball venues from OpenStreetMap")
    ap.add_argument("--all", action="store_true", help="Include venues already present in courts-data.js")
    args = ap.parse_args()

    print(f"Querying Overpass for pickleball venues in the GTA…")
    try:
        result = fetch_overpass(overpass_query(BBOX))
    except urllib.error.URLError as e:
        print(f"ERROR: could not reach Overpass API: {e}")
        print("This script needs outbound network access to overpass-api.de.")
        return

    elements = result.get("elements", [])
    print(f"  Overpass returned {len(elements)} raw element(s).")

    existing = load_existing_courts()
    candidates, skipped = [], 0
    seen_names = set()

    for el in elements:
        cand = to_candidate(el)
        if not cand:
            continue
        key = cand["name"].lower().strip()
        if key in seen_names:
            continue
        seen_names.add(key)

        if not args.all:
            dup = any(
                haversine_m(cand["lat"], cand["lng"], elat, elng) < DEDUPE_RADIUS_M
                or ename.lower().strip() == key
                for (ename, elat, elng) in existing
            )
            if dup:
                skipped += 1
                continue
        candidates.append(cand)

    candidates.sort(key=lambda c: (c["city"], c["name"]))
    OUT_FILE.write_text(json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n  {len(candidates)} new candidate venue(s) written to {OUT_FILE.name}")
    print(f"  {skipped} skipped as already present (use --all to include them).")
    if candidates:
        print("\n  Preview:")
        for c in candidates[:15]:
            site = f"  [{c['website']}]" if c["website"] else ""
            print(f"    • {c['name']} — {c['address'] or '(no address)'} [{c['access']}]{site}")
    print("\nNext: review the JSON, fix any addresses/coords, optionally enrich via")
    print("auto_update.py against each website, then paste vetted entries into courts-data.js.")


if __name__ == "__main__":
    main()
