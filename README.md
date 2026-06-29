# 🏓 GTA PickleCourts

**Greater Toronto Area Pickleball Court Finder**

An interactive map-based web app to discover pickleball courts across the Greater Toronto Area. Find indoor and outdoor courts in Toronto, Mississauga, Brampton, Markham, Vaughan, Richmond Hill, and more.

## ✨ Features

- 🗺️ **Interactive Map** — Browse 180+ courts on a beautiful dark-themed map
- 🔍 **Search & Filter** — Filter by city, court type (indoor/outdoor), amenities, and free access
- 📍 **Detailed Court Info** — View court count, surface type, hours, amenities, and notes
- 🆓 **Free Court Filter** — Quickly find free public courts
- 📱 **Mobile Responsive** — Works on desktop, tablet, and phone
- 🧭 **Get Directions** — One-click Google Maps directions to any court

## 🏙️ Cities Covered

Toronto · Mississauga · Brampton · Markham · Vaughan · Richmond Hill · Oakville · Ajax · Pickering · Oshawa · Burlington · Newmarket · Milton · Halton Hills

## 🚀 Live Demo

Visit the app at: **[dryvonneleung.github.io/gta-pickleball-tracker](https://dryvonneleung.github.io/gta-pickleball-tracker)**

## 🛠️ Tech Stack

- Pure HTML, CSS, JavaScript (no build step required)
- [Leaflet.js](https://leafletjs.com/) for interactive maps
- [OpenStreetMap](https://www.openstreetmap.org/) tiles
- Court data sourced from City of Toronto Open Data API and municipal websites

## 📦 Data Sources

- **Toronto**: [City of Toronto Open Data — Pickleball Listings](https://www.toronto.ca/data/parks/live/pickleballlisting.json)
- **Richmond Hill**: [richmondhill.ca](https://www.richmondhill.ca)
- **Other cities**: Municipal websites, Pickleheads, and community resources

## 🏓 Coach Directory

A second page (`coaches.html`, linked as **Find a Coach** in the header) lets
pickleball coaches sign up to teach and lets students browse a searchable
directory. Each coach lists a **home-base city** and **how far they're willing
to travel** to reach students, so the directory can filter to "coaches who will
travel to *my* city."

- **Signup** — name, contact, base city, travel range (km), skill levels, rate,
  certifications, and bio.
- **Directory** — search + filter by travel area, skill level, and max rate;
  sort by distance, rate, experience, or travel range; map shows each coach's
  coverage radius.

### Setting up the shared database (Supabase)

The directory uses [Supabase](https://supabase.com) (free tier) so signups are
shared across all visitors. Until it's configured, the page runs in **Demo
mode** and stores signups only in the current browser (`localStorage`).

1. Create a free project at [supabase.com](https://supabase.com).
2. In the SQL Editor, run the script in [`supabase/schema.sql`](supabase/schema.sql)
   to create the `coaches` table and its Row Level Security policies.
3. In **Project Settings → API**, copy the **Project URL** and the **anon /
   public** key into [`supabase-config.js`](supabase-config.js).

The anon key is safe to commit — access is gated by the RLS policies. Signup is
open to the public by default; see the note in `schema.sql` for adding
moderation/CAPTCHA before production.

## 🔄 Updating Court Data

`auto_update.py` fetches each municipality's official pickleball page and uses an
LLM to extract new/changed courts, then writes them to `courts-data.js`.

### Run it manually

```bash
export NVIDIA_API_KEY=your_key_here
python3 auto_update.py            # all cities
python3 auto_update.py --city Aurora   # one city
python3 auto_update.py --dry-run       # preview only
```

### Automatic scheduled updates (GitHub Action)

The workflow [`.github/workflows/auto-update-courts.yml`](.github/workflows/auto-update-courts.yml)
runs the scraper every **Monday at 08:00 UTC** (and on demand from the Actions
tab) and commits any changes, which redeploys the site.

**One-time setup** — in **Settings → Secrets and variables → Actions**:

| Type | Name | Required | Default |
|------|------|----------|---------|
| Secret | `NVIDIA_API_KEY` | ✅ yes | — |
| Variable | `NVIDIA_BASE_URL` | optional | `https://integrate.api.nvidia.com/v1` |
| Variable | `NVIDIA_MODEL` | optional | `meta/llama-3.3-70b-instruct` |

To run it immediately, go to **Actions → Auto-update courts → Run workflow**
(optionally enter a single city). Adjust the `cron:` line in the workflow to
change the schedule.

### Discovering private / commercial venues

Private clubs (e.g. King Square Sports Centre) aren't in municipal open data, so
they're discovered separately in two stages:

1. **Discover** with `discover_courts_osm.py` — queries OpenStreetMap (free, no
   API key) for pickleball venues across the GTA and writes new candidates to
   `private-courts-candidates.json` (it de-dupes against `courts-data.js` and
   does **not** modify it):

   ```bash
   python3 discover_courts_osm.py
   ```

   Data © OpenStreetMap contributors (ODbL) — attribute OSM if you publish it.

   For broader coverage of commercial clubs, also run the **Google Places**
   discovery (`discover_courts_places.py`), which tiles the GTA and runs a
   "pickleball" search in each cell, then **merges** new finds into the same
   `private-courts-candidates.json`:

   ```bash
   export GOOGLE_PLACES_API_KEY=your_key_here   # Places API (New) must be enabled
   python3 discover_courts_places.py            # full GTA grid (~54 tiles)
   python3 discover_courts_places.py --max-pages 1   # cheaper, ≤20 results/tile
   ```

   Set up a key: Google Cloud → enable **Places API (New)** → create an API key.
   Text Search is billed per request (the script logs the request count before
   starting; Google's recurring free credit covers light use). Results tagged
   `_low_confidence` are likely not pickleball venues — check them before adding.

2. **Review & enrich** — sanity-check each candidate's address/coordinates,
   optionally run `auto_update.py` against the venue's website to fill in court
   count/hours, then paste vetted entries into `courts-data.js`.

Court entries may include an optional `website` field (booking/info link), shown
as a **Book / Visit site** button in the court detail modal. The court list can
be filtered by **Free** or **Private/Paid** access.

## 📄 License

MIT
