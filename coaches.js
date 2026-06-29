/* ============================================================
   GTA PickleCourts — Coach Directory
   Coaches sign up (incl. how far they'll travel); students
   browse & filter a searchable directory.

   Data layer: Supabase if configured (see supabase-config.js),
   otherwise a localStorage "Demo mode" fallback so the page
   works out of the box. The Supabase client library is loaded
   lazily (only when keys are configured) so the page never
   depends on a CDN in demo mode.
   ============================================================ */

/* ---- GTA city centroids (lat, lng) used for base location
        and distance-based "travels to" filtering ---- */
const GTA_CITIES = [
  { name: 'Toronto',       lat: 43.6532, lng: -79.3832 },
  { name: 'Mississauga',   lat: 43.5890, lng: -79.6441 },
  { name: 'Brampton',      lat: 43.7315, lng: -79.7624 },
  { name: 'Markham',       lat: 43.8561, lng: -79.3370 },
  { name: 'Vaughan',       lat: 43.8361, lng: -79.4985 },
  { name: 'Richmond Hill', lat: 43.8828, lng: -79.4403 },
  { name: 'Oakville',      lat: 43.4675, lng: -79.6877 },
  { name: 'Burlington',    lat: 43.3255, lng: -79.7990 },
  { name: 'Milton',        lat: 43.5183, lng: -79.8774 },
  { name: 'Halton Hills',  lat: 43.6303, lng: -79.9554 },
  { name: 'Newmarket',     lat: 44.0592, lng: -79.4613 },
  { name: 'Aurora',        lat: 44.0065, lng: -79.4504 },
  { name: 'Ajax',          lat: 43.8509, lng: -79.0204 },
  { name: 'Pickering',     lat: 43.8384, lng: -79.0868 },
  { name: 'Whitby',        lat: 43.8975, lng: -78.9428 },
  { name: 'Oshawa',        lat: 43.8971, lng: -78.8658 },
];
const cityByName = Object.fromEntries(GTA_CITIES.map(c => [c.name, c]));

const SKILL_LEVELS = ['Beginner', 'Intermediate', 'Advanced', 'Junior'];

/* ---- Haversine distance in km ---- */
function distanceKm(aLat, aLng, bLat, bLng) {
  const R = 6371;
  const toRad = d => (d * Math.PI) / 180;
  const dLat = toRad(bLat - aLat);
  const dLng = toRad(bLng - aLng);
  const lat1 = toRad(aLat);
  const lat2 = toRad(bLat);
  const h = Math.sin(dLat / 2) ** 2 +
            Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/* ============================================================
   Data layer
   ============================================================ */
const cfg = window.SUPABASE_CONFIG || {};
const SUPABASE_READY =
  !!cfg.url && !!cfg.anonKey &&
  cfg.url.startsWith('http') && !cfg.url.includes('YOUR_');

let supa = null;
let supaPromise = null;
async function getClient() {
  if (!SUPABASE_READY) return null;
  if (supa) return supa;
  if (!supaPromise) {
    supaPromise = import('https://esm.sh/@supabase/supabase-js@2')
      .then(({ createClient }) => {
        supa = createClient(cfg.url, cfg.anonKey);
        return supa;
      });
  }
  return supaPromise;
}

const LS_KEY = 'gta_coaches_v1';

const store = {
  mode: SUPABASE_READY ? 'supabase' : 'demo',

  async list() {
    const supa = await getClient();
    if (supa) {
      const { data, error } = await supa
        .from('coaches')
        .select('*')
        .order('created_at', { ascending: false });
      if (error) throw error;
      return data || [];
    }
    try {
      return JSON.parse(localStorage.getItem(LS_KEY) || '[]');
    } catch {
      return [];
    }
  },

  async add(coach) {
    const supa = await getClient();
    if (supa) {
      const { data, error } = await supa
        .from('coaches')
        .insert(coach)
        .select()
        .single();
      if (error) throw error;
      return data;
    }
    const rows = await this.list();
    const row = {
      ...coach,
      id: 'demo-' + Date.now(),
      created_at: new Date().toISOString(),
    };
    rows.unshift(row);
    localStorage.setItem(LS_KEY, JSON.stringify(rows));
    return row;
  },
};

/* ============================================================
   State + DOM
   ============================================================ */
const state = {
  coaches: [],
  filters: { q: '', travelsTo: '', skills: new Set(), maxRate: null, sort: 'newest' },
  map: null,
  layer: null,
};

const $  = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function toast(msg) {
  const t = $('#toast');
  $('#toast-msg').textContent = msg;
  t.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add('hidden'), 3200);
}

/* ============================================================
   Populate static UI (selects, chips, banner)
   ============================================================ */
function populateStatic() {
  // City selects (signup base + directory "travels to")
  const baseSel = $('#f-city');
  const toSel   = $('#filter-travels-to');
  GTA_CITIES.forEach(c => {
    baseSel.insertAdjacentHTML('beforeend', `<option value="${c.name}">${c.name}</option>`);
    toSel.insertAdjacentHTML('beforeend', `<option value="${c.name}">${c.name}</option>`);
  });

  // Skill checkboxes (signup form)
  $('#f-skills').innerHTML = SKILL_LEVELS.map(s => `
    <label class="check-pill">
      <input type="checkbox" name="skill" value="${s}"> ${s}
    </label>`).join('');

  // Skill filter chips (directory)
  $('#filter-skills').innerHTML = SKILL_LEVELS.map(s => `
    <button type="button" class="chip small" data-skill="${s}">${s}</button>`).join('');

  // Mode banner
  if (store.mode === 'demo') {
    const b = $('#mode-banner');
    b.classList.remove('hidden');
    b.innerHTML = `<strong>Demo mode.</strong> Sign-ups are saved only in this
      browser. Add your Supabase keys in <code>supabase-config.js</code> to enable
      a shared database that everyone can see.`;
  }
}

/* ============================================================
   Signup form
   ============================================================ */
function initForm() {
  const form = $('#coach-form');
  const travel = $('#f-travel');
  const travelOut = $('#f-travel-val');
  travelOut.textContent = `${travel.value} km`;
  travel.addEventListener('input', () => {
    travelOut.textContent = `${travel.value} km`;
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(form);

    // The form is novalidate, so validate the required fields here.
    const name = (fd.get('name') || '').trim();
    if (!name) { toast('Please enter your name.'); return; }

    const email = (fd.get('email') || '').trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { toast('Please enter a valid email address.'); return; }

    const cityName = fd.get('city');
    const city = cityByName[cityName];
    if (!city) { toast('Please pick a home-base city.'); return; }

    const skills = $$('#f-skills input[name="skill"]:checked').map(i => i.value);
    if (skills.length === 0) { toast('Pick at least one skill level you teach.'); return; }

    const coach = {
      name,
      email,
      phone: (fd.get('phone') || '').trim() || null,
      city: cityName,
      lat: city.lat,
      lng: city.lng,
      travel_distance_km: Number(fd.get('travel')),
      skill_levels: skills,
      years_experience: fd.get('experience') ? Number(fd.get('experience')) : null,
      hourly_rate: fd.get('rate') ? Number(fd.get('rate')) : null,
      certifications: (fd.get('certifications') || '').trim() || null,
      bio: (fd.get('bio') || '').trim() || null,
    };

    const btn = $('#submit-btn');
    btn.disabled = true;
    btn.textContent = 'Submitting…';
    try {
      await store.add(coach);
      form.reset();
      travelOut.textContent = `${travel.value} km`;
      toast('🎉 You\'re listed! Thanks for joining the coach directory.');
      await loadCoaches();
      $('#directory').scrollIntoView({ behavior: 'smooth' });
    } catch (err) {
      console.error(err);
      toast('Something went wrong saving your signup. Please try again.');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Join the directory';
    }
  });
}

/* ============================================================
   Directory filters
   ============================================================ */
function initFilters() {
  $('#search-input').addEventListener('input', e => {
    state.filters.q = e.target.value.toLowerCase().trim();
    render();
  });
  $('#filter-travels-to').addEventListener('change', e => {
    state.filters.travelsTo = e.target.value;
    render();
  });
  $('#filter-rate').addEventListener('input', e => {
    state.filters.maxRate = e.target.value ? Number(e.target.value) : null;
    render();
  });
  $('#filter-sort').addEventListener('change', e => {
    state.filters.sort = e.target.value;
    render();
  });
  $('#filter-skills').addEventListener('click', e => {
    const btn = e.target.closest('[data-skill]');
    if (!btn) return;
    const skill = btn.dataset.skill;
    if (state.filters.skills.has(skill)) state.filters.skills.delete(skill);
    else state.filters.skills.add(skill);
    btn.classList.toggle('active');
    render();
  });
  $('#clear-filters').addEventListener('click', () => {
    state.filters = { q: '', travelsTo: '', skills: new Set(), maxRate: null, sort: 'newest' };
    $('#search-input').value = '';
    $('#filter-travels-to').value = '';
    $('#filter-rate').value = '';
    $('#filter-sort').value = 'newest';
    $$('#filter-skills .chip').forEach(c => c.classList.remove('active'));
    render();
  });
}

function applyFilters(coaches) {
  const f = state.filters;
  const to = f.travelsTo ? cityByName[f.travelsTo] : null;

  let rows = coaches.map(c => {
    let distance = null;
    if (to) distance = distanceKm(c.lat, c.lng, to.lat, to.lng);
    return { ...c, _distance: distance };
  });

  rows = rows.filter(c => {
    if (f.q) {
      const hay = `${c.name} ${c.city} ${c.bio || ''} ${c.certifications || ''}`.toLowerCase();
      if (!hay.includes(f.q)) return false;
    }
    if (f.skills.size) {
      const has = (c.skill_levels || []).some(s => f.skills.has(s));
      if (!has) return false;
    }
    if (f.maxRate != null) {
      if (c.hourly_rate == null || c.hourly_rate > f.maxRate) return false;
    }
    if (to) {
      // coach must be willing to travel far enough to reach the selected city
      if (c._distance > c.travel_distance_km) return false;
    }
    return true;
  });

  const s = f.sort;
  rows.sort((a, b) => {
    if (s === 'distance' && to) return (a._distance ?? 1e9) - (b._distance ?? 1e9);
    if (s === 'rate')       return (a.hourly_rate ?? 1e9) - (b.hourly_rate ?? 1e9);
    if (s === 'experience') return (b.years_experience ?? -1) - (a.years_experience ?? -1);
    if (s === 'travel')     return (b.travel_distance_km ?? 0) - (a.travel_distance_km ?? 0);
    // newest
    return new Date(b.created_at) - new Date(a.created_at);
  });
  return rows;
}

/* ============================================================
   Render directory + map
   ============================================================ */
function coachCard(c) {
  const initials = (c.name || '?').split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase();
  const skills = (c.skill_levels || []).map(s =>
    `<span class="tag">${escapeHtml(s)}</span>`).join('');
  const meta = [];
  if (c.years_experience != null) meta.push(`${c.years_experience} yr${c.years_experience === 1 ? '' : 's'} exp`);
  if (c.certifications) meta.push(escapeHtml(c.certifications));
  const rate = c.hourly_rate != null ? `$${c.hourly_rate}/hr` : 'Rate on request';
  const distLine = c._distance != null
    ? `<span class="coach-dist">≈ ${Math.round(c._distance)} km from ${escapeHtml(state.filters.travelsTo)}</span>`
    : '';

  return `
  <article class="coach-card">
    <div class="coach-top">
      <div class="coach-avatar">${escapeHtml(initials)}</div>
      <div class="coach-id">
        <h3>${escapeHtml(c.name)}</h3>
        <p class="coach-base">📍 ${escapeHtml(c.city)} · travels up to <strong>${c.travel_distance_km} km</strong></p>
        ${distLine}
      </div>
      <div class="coach-rate">${escapeHtml(rate)}</div>
    </div>
    ${skills ? `<div class="coach-tags">${skills}</div>` : ''}
    ${meta.length ? `<p class="coach-meta">${meta.join(' · ')}</p>` : ''}
    ${c.bio ? `<p class="coach-bio">${escapeHtml(c.bio)}</p>` : ''}
    <div class="coach-actions">
      <a class="btn btn-primary" href="mailto:${escapeHtml(c.email)}?subject=Pickleball%20coaching%20enquiry">Contact</a>
      ${c.phone ? `<a class="btn btn-secondary" href="tel:${escapeHtml(c.phone.replace(/[^\d+]/g, ''))}">Call</a>` : ''}
    </div>
  </article>`;
}

function render() {
  const rows = applyFilters(state.coaches);
  const list = $('#coach-list');
  $('#results-count').textContent =
    `${rows.length} coach${rows.length === 1 ? '' : 'es'}` +
    (state.filters.travelsTo ? ` who travel to ${state.filters.travelsTo}` : '');

  if (rows.length === 0) {
    list.innerHTML = `<div class="empty-state">
      <p>No coaches match your filters yet.</p>
      <p class="muted">Try widening the travel area or clearing filters — or sign up above to be the first!</p>
    </div>`;
  } else {
    list.innerHTML = rows.map(coachCard).join('');
  }
  renderMap(rows);
}

function renderMap(rows) {
  if (typeof L === 'undefined') return; // Leaflet unavailable — skip map, keep directory working
  if (!state.map) {
    state.map = L.map('coach-map', {
      center: [43.72, -79.42], zoom: 9, zoomControl: true, attributionControl: false,
    });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 })
      .addTo(state.map);
    state.layer = L.layerGroup().addTo(state.map);
  }
  state.layer.clearLayers();

  rows.forEach(c => {
    const marker = L.circleMarker([c.lat, c.lng], {
      radius: 7, color: '#ff1d8e', fillColor: '#ff8a00', fillOpacity: 0.9, weight: 2,
    });
    marker.bindPopup(
      `<strong>${escapeHtml(c.name)}</strong><br>${escapeHtml(c.city)} · up to ${c.travel_distance_km} km`
    );
    state.layer.addLayer(marker);
    // coverage radius
    L.circle([c.lat, c.lng], {
      radius: c.travel_distance_km * 1000,
      color: '#ff8a00', weight: 1, fillColor: '#ff8a00', fillOpacity: 0.07,
    }).addTo(state.layer);
  });

  // highlight the "travels to" target city
  const to = state.filters.travelsTo ? cityByName[state.filters.travelsTo] : null;
  if (to) {
    L.marker([to.lat, to.lng]).addTo(state.layer)
      .bindPopup(`<strong>${escapeHtml(to.name)}</strong><br>your selected area`);
  }
}

/* ============================================================
   Boot
   ============================================================ */
async function loadCoaches() {
  try {
    state.coaches = await store.list();
  } catch (err) {
    console.error(err);
    toast('Could not load the coach directory.');
    state.coaches = [];
  }
  render();
}

function init() {
  populateStatic();
  initForm();
  initFilters();
  loadCoaches();
}

document.addEventListener('DOMContentLoaded', init);
