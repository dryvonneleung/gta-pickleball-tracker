#!/usr/bin/env python3
"""
GTA Pickleball Court Auto-Updater
Uses an NVIDIA LLM endpoint to parse municipal recreation websites and
detect new/changed courts, then updates courts-data.js automatically.

Usage:
  python auto_update.py                  # Run once for all configured sources
  python auto_update.py --city aurora    # Run for a specific city
  python auto_update.py --dry-run        # Preview changes without writing
  python auto_update.py --list-sources   # Show all configured URLs

Configuration:
  Set NVIDIA_API_KEY and NVIDIA_BASE_URL in environment or .env file.
"""

import os
import re
import sys
import json
import time
import argparse
import textwrap
import subprocess
from datetime import datetime
from pathlib import Path
import math
import urllib.request
import urllib.error
import urllib.parse

# -- Optional deps (graceful fallback) --
try:
    from openai import OpenAI          # pip install openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from dotenv import load_dotenv     # pip install python-dotenv
    load_dotenv()
except ImportError:
    pass

# -- Config --

SCRIPT_DIR  = Path(__file__).parent
COURTS_FILE = SCRIPT_DIR / "courts-data.js"
LOG_FILE    = SCRIPT_DIR / "auto_update.log"

# NVIDIA NIM endpoint -- override via environment variables
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")   # Required
# meta/llama-3.3-70b-instruct reached end of life on 2026-08-26 and the
# endpoint now answers 410 Gone, which fails every HTML source at once.
NVIDIA_MODEL    = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")

# Municipal pickleball pages to monitor
SOURCES = [
    {
        "city":    "Aurora",
        "url":     "https://www.aurora.ca/recreation-arts-and-culture/recreation-programs-and-drop-in-activities/pickleball/",
        "enabled": True,
    },
    {
        "city":    "Newmarket",
        "url":     "https://www.newmarket.ca/recreation-parks/programs-camps/pickleball",
        "enabled": True,
    },
    {
        "city":    "Milton",
        "url":     "https://www.milton.ca/explore-play/recreation-active-living/pickleball/",
        "enabled": True,
    },
    {
        # Disabled 2026-10-10: Old page 404s; the replacement outdoor-facilities page has no pickleball content.
        "city":    "Ajax",
        "url":     "https://www.ajax.ca/en/play-and-discover/pickleball.aspx",
        "enabled": False,
    },
    {
        "city":    "Burlington",
        "url":     "https://www.burlington.ca/en/recreation/pickleball.aspx",
        "enabled": True,
    },
    {
        "city":    "Richmond Hill",
        "url":     "https://www.richmondhill.ca/en/things-to-do/tennis.aspx",
        "enabled": True,
    },
    {
        # Disabled 2026-10-10: Old portal URL is gone; the new site has no standalone pickleball
        # page -- programs live in the PerfectMind registration system.
        "city":    "Markham",
        "url":     "https://www.markham.ca/wps/portal/home/recreation/recreation-programs/sports/pickleball",
        "enabled": False,
    },
    {
        # Disabled 2026-10-10: No dedicated page any more; listings moved into a JavaScript facility
        # finder that serves no static HTML.
        "city":    "Mississauga",
        "url":     "https://www.mississauga.ca/parks-and-recreation/sports/pickleball/",
        "enabled": False,
    },
    {
        # Disabled 2026-10-10: Pickleball page 404s; the Sports page lists no courts.
        "city":    "Brampton",
        "url":     "https://www.brampton.ca/EN/residents/Recreation/Pages/Pickleball.aspx",
        "enabled": False,
    },
    {
        # Disabled: Toronto courts are sourced from the City of Toronto open-data
        # feed (higher quality than this HTML page). Leaving this off prevents the
        # scraper from overwriting the clean open-data entries in courts-data.js.
        "city":    "Toronto",
        "url":     "https://www.toronto.ca/data/parks/prd/facilities/pickleball/index.html",
        "enabled": False,
    },
    {
        # Disabled 2026-10-10: URL is correct but the site answers 403 to every non-browser client
        # (bot protection), regardless of User-Agent. Needs a headless browser.
        "city":    "Vaughan",
        "url":     "https://www.vaughan.ca/about-city-vaughan/projects-and-initiatives/community-projects/pickleball",
        "enabled": False,
    },
    {
        "city":    "Oakville",
        "url":     "https://www.oakville.ca/parks-recreation-culture/programs-activities/pickleball/",
        "enabled": True,
    },
    {
        "city":    "Pickering",
        "url":     "https://www.pickering.ca/parks-recreation-culture/recreation-programs/pickleball/",
        "enabled": True,
    },
    {
        "city":    "Whitby",
        "url":     "https://www.whitby.ca/explore-and-enjoy/parks-and-recreation/pickleball-and-tennis-courts/",
        "enabled": True,
    },
    {
        "city":    "Oshawa",
        "url":     "https://www.oshawa.ca/explore-play/recreation/facilities-and-rentals/court-rentals/",
        "enabled": True,
    },
    {
        "city":    "Caledon",
        "url":     "https://www.caledon.ca/en/living-here/drop-in-activities.aspx",
        "enabled": True,
    },
    {
        "city":    "Halton Hills",
        "url":     "https://www.haltonhills.ca/courts",
        "enabled": True,
    },
    {
        "city":    "King",
        "url":     "https://www.king.ca/facilities",
        "enabled": True,
    },
    {
        "city":    "Whitchurch-Stouffville",
        "url":     "https://www.townofws.ca/play/parks-and-open-spaces/sport-courts/",
        "enabled": True,
    },
    {
        # Disabled 2026-10-10: Old URL 404s; no replacement page with court content found.
        "city":    "East Gwillimbury",
        "url":     "https://www.eastgwillimbury.ca/en/parks-and-recreation/sports-fields-and-courts.aspx",
        "enabled": False,
    },
    {
        # Disabled 2026-10-10: Old URL 404s; no replacement page with court content found.
        "city":    "Georgina",
        "url":     "https://www.georgina.ca/en/recreation-and-culture/recreation-programs.aspx",
        "enabled": False,
    },
    {
        # Disabled 2026-10-10: Page loads but mentions pickleball once in passing; nothing to extract.
        "city":    "Brock",
        "url":     "https://townshipofbrock.ca/",
        "enabled": False,
    },
    {
        "city":    "Uxbridge",
        "url":     "https://www.uxbridge.ca/explore-and-play/facilities-parks-and-trails/parks-and-trails",
        "enabled": True,
    },
    {
        # Disabled 2026-10-10: Old URL 404s; no replacement page with court content found.
        "city":    "Scugog",
        "url":     "https://www.scugog.ca/en/live-and-play/parks-and-trails.aspx",
        "enabled": False,
    },
    {
        # Disabled 2026-10-10: Old URL 404s; only news posts mention pickleball.
        "city":    "Clarington",
        "url":     "https://www.clarington.net/en/recreation-and-tourism/parks-and-sports-fields.aspx",
        "enabled": False,
    },
]

# -- Logging --

def log(msg: str, level: str = "INFO"):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# -- HTTP helpers --

def fetch_page(url: str, timeout: int = 15) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; GTAPickleballBot/1.0; "
            "+https://dryvonneleung.github.io/gta-pickleball-tracker)"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw     = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        log(f"HTTP {e.code} fetching {url}", "WARN")
        return ""
    except Exception as e:
        log(f"Error fetching {url}: {e}", "ERROR")
        return ""


def strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


# -- courts-data.js helpers --

def read_courts_js() -> str:
    return COURTS_FILE.read_text(encoding="utf-8")


def get_max_id(js: str) -> int:
    ids = [int(x) for x in re.findall(r"\bid:\s*(\d+)", js)]
    return max(ids) if ids else 4900


def extract_city_block(js: str, city: str) -> str:
    entries = []
    for m in re.finditer(
        r"\{[^{}]*city:\s*[\"']" + re.escape(city) + r"[\"'][^{}]*\}", js, re.S
    ):
        entries.append(m.group())
    return "\n".join(entries)


# -- NVIDIA LLM client --

def get_llm_client():
    if not HAS_OPENAI:
        raise RuntimeError("openai package not installed. Run: pip install openai")
    if not NVIDIA_API_KEY:
        raise RuntimeError(
            "NVIDIA_API_KEY is not set. "
            "Export it in your shell or add it to a .env file in the project folder."
        )
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)


def ask_llm(client, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    response = client.chat.completions.create(
        model=NVIDIA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


# -- Core update logic --

SYSTEM_PROMPT = textwrap.dedent("""
    You are a data extraction assistant for the GTA Pickleball Court Tracker.
    Your job is to compare existing court entries with fresh municipal website content
    and return ONLY a JSON array of courts that are NEW or have CHANGED.

    Each court object must have EXACTLY these fields:
    {
      "id":        <integer | null -- null for new courts, existing id for updates>,
      "name":      <string>,
      "city":      <string>,
      "address":   <full civic address string>,
      "lat":       <float latitude>,
      "lng":       <float longitude>,
      "type":      <"indoor" | "outdoor" | "both">,
      "numCourts": <integer>,
      "surface":   <string>,
      "access":    <string e.g. "Public - Free" or "Public / Drop-in">,
      "hours":     <string>,
      "amenities": <array from: "washrooms","parking","lights","dropin","pro_shop","coaching">,
      "notes":     <concise factual string>
    }

    Rules:
    - Return [] (empty array) if nothing has changed and no new courts are found.
    - Do NOT include courts that already exist in the database unchanged.
    - Give the most complete civic address you can find, including the street
      type (St, Ave, Rd, Blvd) and the city. Accuracy of the address matters:
      coordinates are resolved from it by a geocoder afterwards.
    - Set lat and lng to null. Do NOT estimate them -- estimated coordinates
      were kilometres out and put courts in the wrong place on the map.
    - Be conservative: only flag a court as changed if there is a clear factual difference.
    - Output ONLY valid JSON -- no markdown fences, no explanation text.
""")


# -- Geocoding ----------------------------------------------------------------
#
# Coordinates used to be estimated by the model, which an audit found to be
# wrong by up to 10 km -- plausible-looking numbers in the right city, pinned
# kilometres from the actual venue, so courts appeared to be missing. Addresses
# are resolved through OpenStreetMap instead, and a court whose address cannot
# be resolved keeps whatever coordinates it already had rather than guessing.

NOMINATIM_URL   = "https://nominatim.openstreetmap.org/search"
NOMINATIM_AGENT = "GTAPickleballTracker/1.0 (+https://dryvonneleung.github.io/gta-pickleball-tracker)"
GEOCODE_MAX_KM  = 25.0     # a resolved point further than this from the city is wrong
GTA_LAT = (43.0, 44.6)
GTA_LNG = (-80.5, -78.3)


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geocode(query: str):
    """Resolve an address to (lat, lng), or (None, None)."""
    params = urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "ca"})
    req = urllib.request.Request(f"{NOMINATIM_URL}?{params}",
                                 headers={"User-Agent": NOMINATIM_AGENT})
    try:
        hits = json.loads(urllib.request.urlopen(req, timeout=25).read())
    except Exception as e:
        log(f"    geocode failed ({type(e).__name__})", "WARN")
        return None, None
    if not hits:
        return None, None
    return float(hits[0]["lat"]), float(hits[0]["lon"])


def resolve_coordinates(courts: list, city: str):
    """Fill in lat/lng from each court's address. Nominatim asks for at most one
    request a second, so this paces itself."""
    # The GTA bounding box alone is too coarse -- it contains Hamilton, so a
    # wrong-city match can pass it. Anchor on the city actually being scraped.
    anchor_lat, anchor_lng = geocode(f"{city}, Ontario, Canada")
    time.sleep(1.1)
    if anchor_lat is None:
        log(f"    could not locate {city}; falling back to GTA bounds only", "WARN")

    for c in courts:
        addr = str(c.get("address") or "").strip()
        if not addr:
            continue
        query = addr if re.search(r",\s*(ON|Ontario)\b", addr, re.I) else f"{addr}, {city}, Ontario"
        lat, lng = geocode(query)
        time.sleep(1.1)

        if lat is None:
            # Fall back to the venue name, which OSM often knows directly.
            lat, lng = geocode(f"{c.get('name','')}, {city}, Ontario")
            time.sleep(1.1)

        if lat is None:
            if c.get("lat") is None or c.get("lng") is None:
                log(f"    {c.get('name')}: address did not geocode, no coordinates", "WARN")
            continue

        if not (GTA_LAT[0] <= lat <= GTA_LAT[1] and GTA_LNG[0] <= lng <= GTA_LNG[1]):
            log(f"    {c.get('name')}: geocoded outside the GTA, ignoring", "WARN")
            continue

        if anchor_lat is not None:
            away = haversine_km(anchor_lat, anchor_lng, lat, lng)
            if away > GEOCODE_MAX_KM:
                log(f"    {c.get('name')}: geocoded {away:.0f} km from {city}, "
                    f"ignoring (wrong match)", "WARN")
                continue

        old_lat, old_lng = c.get("lat"), c.get("lng")
        c["lat"], c["lng"] = round(lat, 6), round(lng, 6)
        if old_lat is not None and old_lng is not None:
            try:
                moved = haversine_km(float(old_lat), float(old_lng), lat, lng)
                if moved > 0.5:
                    log(f"    {c.get('name')}: pin corrected by {moved:.1f} km")
            except (TypeError, ValueError):
                pass


def detect_changes(client, city: str, page_text: str, existing_block: str, next_id: int) -> list:
    user_prompt = f"""
CITY: {city}

=== EXISTING COURTS IN DATABASE ===
{existing_block if existing_block else "(none yet)"}

=== LIVE WEBSITE CONTENT (first 6000 chars) ===
{page_text[:6000]}

=== NEXT AVAILABLE ID FOR NEW COURTS: {next_id} ===

Identify any NEW courts or CHANGED details. Return the JSON array.
""".strip()

    raw = ask_llm(client, SYSTEM_PROMPT, user_prompt)

    match = re.search(r"\[.*\]", raw, re.S)
    if not match:
        log(f"LLM returned no JSON array for {city}. Raw: {raw[:200]}", "WARN")
        return []
    try:
        changes = json.loads(match.group())
        return changes if isinstance(changes, list) else []
    except json.JSONDecodeError as e:
        log(f"JSON parse error for {city}: {e}. Raw snippet: {raw[:200]}", "ERROR")
        return []


def dict_to_js_entry(d: dict) -> str:
    # `d.get(k, default)` returns None when the model supplied an explicit
    # null, and an f-string then writes Python's `None` into the file, which
    # is not valid JavaScript and takes the whole page down with a
    # ReferenceError. Coerce every field through a null-aware helper instead.
    def field(key, default):
        v = d.get(key)
        return default if v is None else v

    amenities = json.dumps(d.get("amenities") or [])
    notes     = str(d.get("notes") or "").replace('"', '\\"')
    cid       = d.get("id")
    if not cid:
        # Never emit a null id: app.js matches courts with `c.id === id` and
        # keys markers by `court.id`, so a null court cannot be opened and all
        # such courts collapse onto one marker key. apply_changes assigns ids.
        raise ValueError(f"court {d.get('name')!r} reached rendering with no id")
    id_str    = str(cid)
    return (
        "    {\n"
        f"        id: {id_str},\n"
        f"        name: \"{field('name', '')}\",\n"
        f"        city: \"{field('city', '')}\",\n"
        f"        address: \"{field('address', '')}\",\n"
        f"        lat: {field('lat', 0)},\n"
        f"        lng: {field('lng', 0)},\n"
        f"        type: \"{field('type', 'outdoor')}\",\n"
        f"        numCourts: {field('numCourts', 1)},\n"
        f"        surface: \"{field('surface', 'Asphalt')}\",\n"
        f"        access: \"{field('access', 'Public - Free')}\",\n"
        f"        hours: \"{field('hours', 'Dawn - Dusk')}\",\n"
        f"        amenities: {amenities},\n"
        f"        notes: \"{notes}\"\n"
        "    }"
    )


def apply_changes(js: str, changes: list, next_id: int = None) -> tuple:
    if not changes:
        return js, 0, next_id
    if next_id is None:
        next_id = get_max_id(js) + 1
    count = 0
    for court in changes:
        court_id  = court.get("id")
        # Only an id the model recognised from the existing block counts as an
        # update; everything else is new and gets its id here, not from the
        # model, which used to answer null.
        if not (court_id and re.search(rf"\bid:\s*{court_id}\b", js)):
            court["id"] = next_id
            next_id += 1
        js_entry  = dict_to_js_entry(court)
        if court_id and re.search(rf"\bid:\s*{court_id}\b", js):
            js = re.sub(
                rf"\{{[^{{}}]*\bid:\s*{court_id}\b[^{{}}]*\}}",
                js_entry,
                js,
                count=1,
                flags=re.S,
            )
            log(f"  Updated id={court_id}: {court.get('name')}")
        else:
            js = js.rstrip()
            if js.endswith("];"):
                js = js[:-2].rstrip().rstrip(",") + ",\n" + js_entry + "\n\n];"
            else:
                js += "\n" + js_entry
            log(f"  Added new id={court['id']}: {court.get('name')} ({court.get('city')})")
        count += 1
    return js, count, next_id


# -- Git helpers --

def git_commit_push(cities: list, dry_run: bool):
    if dry_run:
        log("Dry-run: skipping git commit/push.")
        return
    city_str = ", ".join(cities)
    msg      = f"Auto-update: {city_str} [{datetime.now().strftime('%Y-%m-%d')}]"
    for cmd in [
        ["git", "add", "courts-data.js"],
        ["git", "commit", "-m", msg],
        ["git", "push", "origin", "main"],
    ]:
        result = subprocess.run(cmd, cwd=SCRIPT_DIR, capture_output=True, text=True)
        if result.returncode != 0:
            log(f"  git {cmd[1]} failed: {result.stderr.strip()}", "WARN")
        else:
            log(f"  git {cmd[1]} OK")


# -- Main --

def main():
    parser = argparse.ArgumentParser(description="GTA Pickleball auto-updater via NVIDIA LLM")
    parser.add_argument("--city",         help="Only update this city (case-insensitive)")
    parser.add_argument("--dry-run",      action="store_true", help="Preview without writing")
    parser.add_argument("--list-sources", action="store_true", help="Print all source URLs")
    args = parser.parse_args()

    if args.list_sources:
        for s in SOURCES:
            status = "ON " if s["enabled"] else "OFF"
            print(f"  [{status}] {s['city']}: {s['url']}")
        return

    sources = [s for s in SOURCES if s["enabled"]]
    if args.city:
        sources = [s for s in sources if s["city"].lower() == args.city.lower()]
        if not sources:
            print(f"No source configured for city: {args.city}")
            sys.exit(1)

    log(f"Starting auto-update for {len(sources)} source(s).")
    if args.dry_run:
        log("DRY RUN MODE -- no files will be written.")

    client  = get_llm_client()
    js      = read_courts_js()
    max_id  = get_max_id(js)
    changed = []
    total   = 0

    for source in sources:
        city = source["city"]
        url  = source["url"]
        log(f"\n-- {city} --")
        log(f"  Fetching: {url}")

        html = fetch_page(url)
        if not html:
            log("  No content returned -- skipping.", "WARN")
            continue

        page_text     = strip_html(html)
        existing_data = extract_city_block(js, city)
        next_id       = max_id + 1

        log(f"  Page: {len(page_text):,} chars | Existing entries: {existing_data.count('id:')}")
        log(f"  Querying {NVIDIA_MODEL}...")

        try:
            updates = detect_changes(client, city, page_text, existing_data, next_id)
        except Exception as e:
            log(f"  LLM error: {e}", "ERROR")
            continue

        if not updates:
            log("  No changes detected.")
            continue

        log(f"  {len(updates)} change(s) detected:")
        # Resolve coordinates from the address before anything is written. The
        # model is explicitly told not to estimate them.
        log(f"  Geocoding {len(updates)} address(es)...")
        resolve_coordinates(updates, city)
        for u in updates:
            action = "UPDATE" if u.get("id") else "ADD"
            log(f"    [{action}] {u.get('name')} -- {u.get('address')}")

        usable = []
        for u in updates:
            if u.get("lat") is None or u.get("lng") is None:
                log(f"    Skipping {u.get('name')} -- no coordinates could be resolved.", "WARN")
            else:
                usable.append(u)
        updates = usable
        if not updates:
            log("  Nothing left to apply after geocoding.")
            continue

        if not args.dry_run:
            js, n, max_id = apply_changes(js, updates)
            max_id = get_max_id(js)
            total += n
            changed.append(city)
        else:
            log("  (Dry run -- not applied)")

        time.sleep(1)

    if total > 0 and not args.dry_run:
        log(f"\nWriting {total} change(s) to {COURTS_FILE.name}...")
        COURTS_FILE.write_text(js, encoding="utf-8")
        log("Committing and pushing to GitHub...")
        git_commit_push(changed, dry_run=False)
        log("Done!")
    elif total == 0 and not args.dry_run:
        log("\nNo changes -- courts-data.js is already up to date.")
    else:
        log(f"\nDry run complete -- {len(changed)} source(s) had detected changes.")


if __name__ == "__main__":
    main()
