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

## 🔄 Updating Court Data

Run the auto-update script to fetch and parse the latest court listings across various GTA municipalities (which uses an LLM to parse pages):

```bash
python3 auto_update.py
```

## 📄 License

MIT
