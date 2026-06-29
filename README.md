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

Run the auto-update script to fetch and parse the latest court listings across various GTA municipalities (which uses an LLM to parse pages):

```bash
python3 auto_update.py
```

## 📄 License

MIT
