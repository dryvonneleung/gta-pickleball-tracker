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
import urllib.request
import urllib.error

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
NVIDIA_MODEL    = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")

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
        "url":     "https://www.milton.ca/en/arts-and-recreation/pickleball.aspx",
        "enabled": True,
    },
    {
        "city":    "Ajax",
        "url":     "https://www.ajax.ca/en/play-and-discover/pickleball.aspx",
        "enabled": True,
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
        "city":    "Markham",
        "url":     "https://www.markham.ca/wps/portal/home/recreation/recreation-programs/sports/pickleball",
        "enabled": True,
    },
    {
        "city":    "Mississauga",
        "url":     "https://www.mississauga.ca/parks-and-recreation/sports/pickleball/",
        "enabled": True,
    },
    {
        "city":    "Brampton",
        "url":     "https://www.brampton.ca/EN/residents/Recreation/Pages/Pickleball.aspx",
        "enabled": True,
    },
    {
        "city":    "Toronto",
        "url":     "https://www.toronto.ca/data/parks/prd/facilities/pickleball/index.html",
        "enabled": True,
    },
    {
        "city":    "Vaughan",
        "url":     "https://www.vaughan.ca/pickleball",
        "enabled": True,
    },
    {
        "city":    "Oakville",
        "url":     "https://www.oakville.ca/parks-recreation-culture/parks-trails-gardens/tennis-and-pickleball-courts/",
        "enabled": True,
    },
    {
        "city":    "Pickering",
        "url":     "https://www.pickering.ca/en/discovering/pickleball.aspx",
        "enabled": True,
    },
    {
        "city":    "Whitby",
        "url":     "https://www.whitby.ca/en/play/tennis-and-pickleball-courts.aspx",
        "enabled": True,
    },
    {
        "city":    "Oshawa",
        "url":     "https://www.oshawa.ca/en/parks-recreation-and-culture/racquet-sports.aspx",
        "enabled": True,
    },
    {
        "city":    "Caledon",
        "url":     "https://www.caledon.ca/en/living-here/tennis-and-pickleball.aspx",
        "enabled": True,
    },
    {
        "city":    "Halton Hills",
        "url":     "https://www.haltonhills.ca/courts",
        "enabled": True,
    },
    {
        "city":    "King",
        "url":     "https://www.king.ca/recreation",
        "enabled": True,
    },
    {
        "city":    "Whitchurch-Stouffville",
        "url":     "https://www.townofws.ca/play/parks-and-open-spaces/",
        "enabled": True,
    },
    {
        "city":    "East Gwillimbury",
        "url":     "https://www.eastgwillimbury.ca/en/parks-and-recreation/sports-fields-and-courts.aspx",
        "enabled": True,
    },
    {
        "city":    "Georgina",
        "url":     "https://www.georgina.ca/en/recreation-and-culture/recreation-programs.aspx",
        "enabled": True,
    },
    {
        "city":    "Brock",
        "url":     "https://townshipofbrock.ca/",
        "enabled": True,
    },
    {
        "city":    "Uxbridge",
        "url":     "https://www.uxbridge.ca/en/parks-and-recreation/parks-and-trails.aspx",
        "enabled": True,
    },
    {
        "city":    "Scugog",
        "url":     "https://www.scugog.ca/en/live-and-play/parks-and-trails.aspx",
        "enabled": True,
    },
    {
        "city":    "Clarington",
        "url":     "https://www.clarington.net/en/recreation-and-tourism/parks-and-sports-fields.aspx",
        "enabled": True,
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
    - Estimate lat/lng from the civic address using your knowledge of the GTA area.
    - Be conservative: only flag a court as changed if there is a clear factual difference.
    - Output ONLY valid JSON -- no markdown fences, no explanation text.
""")


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
    amenities = json.dumps(d.get("amenities") or [])
    notes     = str(d.get("notes", "")).replace('"', '\\"')
    cid       = d.get("id")
    id_str    = str(cid) if cid else "null /* TODO: assign id */"
    return (
        "    {\n"
        f"        id: {id_str},\n"
        f"        name: \"{d.get('name', '')}\",\n"
        f"        city: \"{d.get('city', '')}\",\n"
        f"        address: \"{d.get('address', '')}\",\n"
        f"        lat: {d.get('lat', 0)},\n"
        f"        lng: {d.get('lng', 0)},\n"
        f"        type: \"{d.get('type', 'outdoor')}\",\n"
        f"        numCourts: {d.get('numCourts', 1)},\n"
        f"        surface: \"{d.get('surface', 'Asphalt')}\",\n"
        f"        access: \"{d.get('access', 'Public - Free')}\",\n"
        f"        hours: \"{d.get('hours', 'Dawn - Dusk')}\",\n"
        f"        amenities: {amenities},\n"
        f"        notes: \"{notes}\"\n"
        "    }"
    )


def apply_changes(js: str, changes: list) -> tuple:
    if not changes:
        return js, 0
    count = 0
    for court in changes:
        court_id  = court.get("id")
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
            log(f"  Added new: {court.get('name')} ({court.get('city')})")
        count += 1
    return js, count


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
        for u in updates:
            action = "UPDATE" if u.get("id") else "ADD"
            log(f"    [{action}] {u.get('name')} -- {u.get('address')}")

        if not args.dry_run:
            js, n = apply_changes(js, updates)
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
