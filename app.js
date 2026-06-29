/**
 * GTA PickleCourts — Main Application Logic
 */

(function () {
    'use strict';

    // ============ STATE ============
    const state = {
        courts: COURTS_DATA,
        filteredCourts: [],
        activeTypeFilter: 'all',
        activeCityFilter: 'all',
        activeAmenityFilters: new Set(),
        freeOnly: false,
        searchQuery: '',
        sortOrder: 'name', // 'name' | 'courts' | 'city'
        selectedCourtId: null,
        map: null,
        markers: {},
        markerLayer: null
    };

    // ============ DOM REFS ============
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const dom = {
        map: $('#map'),
        courtList: $('#court-list'),
        searchInput: $('#search-input'),
        searchClear: $('#search-clear'),
        resultsCount: $('#results-count'),
        typeFilters: $('#type-filters'),
        cityFilters: $('#city-filters'),
        amenityFilters: $('#amenity-filters'),
        accessFilters: $('#access-filters'),
        sortBtn: $('#sort-btn'),
        statTotal: $('#stat-total'),
        statIndoor: $('#stat-indoor'),
        statOutdoor: $('#stat-outdoor'),
        modalOverlay: $('#modal-overlay'),
        modalClose: $('#modal-close'),
        modalTitle: $('#modal-title'),
        modalAddress: $('#modal-address'),
        modalBadge: $('#modal-badge'),
        modalHeader: $('#modal-header'),
        modalInfoGrid: $('#modal-info-grid'),
        modalAmenities: $('#modal-amenities'),
        modalNotes: $('#modal-notes'),
        modalNotesSection: $('#modal-notes-section'),
        modalDirections: $('#modal-directions'),
        modalShare: $('#modal-share'),
        mobileToggle: $('#mobile-toggle'),
        sidebar: $('#sidebar'),
        toggleIconList: $('#toggle-icon-list'),
        toggleIconMap: $('#toggle-icon-map'),
        btnUpdate: $('#btn-update'),
        btnMyLocation: $('#btn-my-location'),
        btnResetView: $('#btn-reset-view'),
        toast: $('#toast'),
        toastMsg: $('#toast-msg')
    };

    // ============ INIT ============
    function init() {
        initMap();
        populateCityFilters();
        updateStats();
        applyFilters();
        bindEvents();
        animateStatsIn();
    }

    // ============ MAP ============
    function initMap() {
        state.map = L.map('map', {
            center: [43.72, -79.42],
            zoom: 10,
            zoomControl: true,
            attributionControl: false
        });

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
        }).addTo(state.map);

        state.markerLayer = L.layerGroup().addTo(state.map);
    }

    function createMarkerIcon(type) {
        const typeClass = type === 'both' ? 'both' : type;
        return L.divIcon({
            className: 'custom-marker',
            html: `<div class="marker-dot ${typeClass}"></div>`,
            iconSize: [18, 18],
            iconAnchor: [9, 9],
            popupAnchor: [0, -14]
        });
    }

    function addMarkers(courts) {
        state.markerLayer.clearLayers();
        state.markers = {};

        courts.forEach(court => {
            const marker = L.marker([court.lat, court.lng], {
                icon: createMarkerIcon(court.type)
            });

            const badgeClass = court.type;
            const typeLabel = court.type === 'both' ? 'Indoor & Outdoor' : court.type.charAt(0).toUpperCase() + court.type.slice(1);

            marker.bindPopup(`
                <div class="popup-content">
                    <div class="popup-badge ${badgeClass}">${typeLabel}</div>
                    <div class="popup-name">${court.name}</div>
                    <div class="popup-address">${court.address}</div>
                    <div class="popup-courts">${court.numCourts} court${court.numCourts > 1 ? 's' : ''} · ${court.surface}</div>
                    <a class="popup-link" onclick="window.__openCourtModal(${court.id})">
                        View Details →
                    </a>
                </div>
            `, { maxWidth: 280, closeButton: false });

            marker.on('click', () => {
                highlightCourtCard(court.id);
            });

            marker.addTo(state.markerLayer);
            state.markers[court.id] = marker;
        });
    }

    // ============ FILTERS ============
    function populateCityFilters() {
        const cities = [...new Set(state.courts.map(c => c.city))].sort();
        const container = dom.cityFilters;

        cities.forEach(city => {
            const count = state.courts.filter(c => c.city === city).length;
            const btn = document.createElement('button');
            btn.className = 'chip';
            btn.dataset.city = city;
            btn.textContent = `${city} (${count})`;
            btn.id = `filter-city-${city.toLowerCase().replace(/\s/g, '-')}`;
            container.appendChild(btn);
        });
    }

    function applyFilters() {
        let filtered = [...state.courts];

        // Type filter
        if (state.activeTypeFilter !== 'all') {
            filtered = filtered.filter(c => {
                if (state.activeTypeFilter === 'indoor') return c.type === 'indoor' || c.type === 'both';
                if (state.activeTypeFilter === 'outdoor') return c.type === 'outdoor' || c.type === 'both';
                return true;
            });
        }

        // City filter
        if (state.activeCityFilter !== 'all') {
            filtered = filtered.filter(c => c.city === state.activeCityFilter);
        }

        // Amenity filters
        if (state.activeAmenityFilters.size > 0) {
            filtered = filtered.filter(c =>
                [...state.activeAmenityFilters].every(a => c.amenities.includes(a))
            );
        }

        // Free filter
        if (state.freeOnly) {
            filtered = filtered.filter(c => c.access && c.access.toLowerCase().includes('free'));
        }

        // Search
        if (state.searchQuery) {
            const q = state.searchQuery.toLowerCase();
            filtered = filtered.filter(c =>
                c.name.toLowerCase().includes(q) ||
                c.city.toLowerCase().includes(q) ||
                c.address.toLowerCase().includes(q) ||
                c.surface.toLowerCase().includes(q)
            );
        }

        // Sort
        filtered.sort((a, b) => {
            if (state.sortOrder === 'courts') return b.numCourts - a.numCourts;
            if (state.sortOrder === 'city') return a.city.localeCompare(b.city);
            return a.name.localeCompare(b.name);
        });

        state.filteredCourts = filtered;
        renderCourtList();
        addMarkers(filtered);
        updateResultsCount();
    }

    // ============ RENDER ============
    function renderCourtList() {
        const container = dom.courtList;

        if (state.filteredCourts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="11" cy="11" r="8"/>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    </svg>
                    <p>No courts match your filters.<br>Try adjusting your search.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = state.filteredCourts.map(court => {
            const typeClass = court.type;
            const typeLabel = court.type === 'both' ? 'Both' : court.type.charAt(0).toUpperCase() + court.type.slice(1);
            const amenityIcons = getAmenityIcons(court.amenities);

            return `
                <div class="court-card ${typeClass}" data-id="${court.id}" id="court-card-${court.id}">
                    <div class="court-card-top">
                        <span class="court-card-name">${court.name}</span>
                        <span class="court-type-badge ${typeClass}">${typeLabel}</span>
                    </div>
                    <div class="court-card-address">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                            <circle cx="12" cy="10" r="3"/>
                        </svg>
                        ${court.address}
                    </div>
                    <div class="court-card-meta">
                        ${amenityIcons}
                    </div>
                    <div class="court-card-courts">${court.numCourts} court${court.numCourts > 1 ? 's' : ''} · ${court.surface} · ${court.access}</div>
                </div>
            `;
        }).join('');

        // Bind card clicks
        container.querySelectorAll('.court-card').forEach(card => {
            card.addEventListener('click', () => {
                const id = parseInt(card.dataset.id);
                openCourtOnMap(id);
            });
        });
    }

    function getAmenityIcons(amenities) {
        const icons = {
            lights: '🔦 Lights',
            washrooms: '🚻 Washrooms',
            parking: '🅿️ Parking',
            dropin: '🎾 Drop-in',
            coaching: '🏋️ Coaching',
            pro_shop: '🛒 Pro Shop'
        };
        return amenities.map(a => `<span class="meta-tag">${icons[a] || a}</span>`).join('');
    }

    function updateResultsCount() {
        dom.resultsCount.textContent = `${state.filteredCourts.length} court${state.filteredCourts.length !== 1 ? 's' : ''} found`;
    }

    function updateStats() {
        const total = state.courts.length;
        const indoor = state.courts.filter(c => c.type === 'indoor' || c.type === 'both').length;
        const outdoor = state.courts.filter(c => c.type === 'outdoor' || c.type === 'both').length;

        dom.statTotal.textContent = total;
        dom.statIndoor.textContent = indoor;
        dom.statOutdoor.textContent = outdoor;
    }

    function animateStatsIn() {
        const counters = [dom.statTotal, dom.statIndoor, dom.statOutdoor];
        counters.forEach(el => {
            const target = parseInt(el.textContent);
            el.textContent = '0';
            animateCounter(el, target, 800);
        });
    }

    function animateCounter(el, target, duration) {
        const start = performance.now();
        function step(now) {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(eased * target);
            if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    // ============ INTERACTIONS ============
    function openCourtOnMap(id) {
        const marker = state.markers[id];
        if (!marker) return;

        state.map.flyTo(marker.getLatLng(), 15, { duration: 0.8 });
        setTimeout(() => marker.openPopup(), 400);
        highlightCourtCard(id);
    }

    function highlightCourtCard(id) {
        // Clear previous
        $$('.court-card.active').forEach(c => c.classList.remove('active'));
        const card = $(`#court-card-${id}`);
        if (card) {
            card.classList.add('active');
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
        state.selectedCourtId = id;
    }

    // ============ MODAL ============
    function openModal(id) {
        const court = state.courts.find(c => c.id === id);
        if (!court) return;

        const typeLabel = court.type === 'both' ? 'Indoor & Outdoor' : court.type.charAt(0).toUpperCase() + court.type.slice(1);
        const badgeClass = court.type;

        dom.modalBadge.textContent = typeLabel;
        dom.modalBadge.className = `modal-badge ${badgeClass}`;
        dom.modalTitle.textContent = court.name;
        dom.modalAddress.textContent = court.address;

        dom.modalInfoGrid.innerHTML = `
            <div class="info-card">
                <div class="info-card-label">Courts</div>
                <div class="info-card-value cyan">${court.numCourts}</div>
            </div>
            <div class="info-card">
                <div class="info-card-label">Surface</div>
                <div class="info-card-value">${court.surface}</div>
            </div>
            <div class="info-card">
                <div class="info-card-label">Access</div>
                <div class="info-card-value green" style="font-size: 0.85rem;">${court.access}</div>
            </div>
            <div class="info-card">
                <div class="info-card-label">Hours</div>
                <div class="info-card-value" style="font-size: 0.85rem;">${court.hours}</div>
            </div>
        `;

        const amenityNames = {
            lights: '🔦 Lights',
            washrooms: '🚻 Washrooms',
            parking: '🅿️ Parking',
            dropin: '🎾 Drop-in',
            coaching: '🏋️ Coaching',
            pro_shop: '🛒 Pro Shop'
        };
        const allAmenities = Object.keys(amenityNames);
        dom.modalAmenities.innerHTML = allAmenities.map(a => {
            const has = court.amenities.includes(a);
            return `<span class="amenity-tag ${has ? 'has' : ''}">${amenityNames[a]}</span>`;
        }).join('');

        if (court.notes) {
            dom.modalNotesSection.classList.remove('hidden');
            dom.modalNotes.textContent = court.notes;
        } else {
            dom.modalNotesSection.classList.add('hidden');
        }

        dom.modalDirections.href = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(court.address)}`;

        dom.modalShare.onclick = () => {
            const text = `Check out ${court.name} — ${court.numCourts} pickleball courts at ${court.address}!`;
            if (navigator.share) {
                navigator.share({ title: court.name, text, url: window.location.href });
            } else {
                navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard!'));
            }
        };

        dom.modalOverlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        dom.modalOverlay.classList.add('hidden');
        document.body.style.overflow = '';
    }

    // Global for popup links
    window.__openCourtModal = openModal;

    // ============ TOAST ============
    function showToast(msg) {
        dom.toastMsg.textContent = msg;
        dom.toast.classList.remove('hidden');
        clearTimeout(state._toastTimer);
        state._toastTimer = setTimeout(() => dom.toast.classList.add('hidden'), 2500);
    }

    // ============ EVENTS ============
    function bindEvents() {
        // Type filters
        dom.typeFilters.addEventListener('click', (e) => {
            const btn = e.target.closest('.chip');
            if (!btn) return;
            dom.typeFilters.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            state.activeTypeFilter = btn.dataset.filter;
            applyFilters();
        });

        // City filters
        dom.cityFilters.addEventListener('click', (e) => {
            const btn = e.target.closest('.chip');
            if (!btn) return;
            dom.cityFilters.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            state.activeCityFilter = btn.dataset.city;
            applyFilters();

            // Zoom to city if not "all"
            if (btn.dataset.city !== 'all') {
                const cityCourts = state.filteredCourts;
                if (cityCourts.length > 0) {
                    const bounds = L.latLngBounds(cityCourts.map(c => [c.lat, c.lng]));
                    state.map.flyToBounds(bounds.pad(0.2), { duration: 0.8 });
                }
            } else {
                state.map.flyTo([43.72, -79.42], 10, { duration: 0.8 });
            }
        });

        // Amenity filters
        dom.amenityFilters.addEventListener('click', (e) => {
            const btn = e.target.closest('.chip');
            if (!btn) return;
            btn.classList.toggle('active');
            const amenity = btn.dataset.amenity;
            if (state.activeAmenityFilters.has(amenity)) {
                state.activeAmenityFilters.delete(amenity);
            } else {
                state.activeAmenityFilters.add(amenity);
            }
            applyFilters();
        });

        // Access (Free) filter
        dom.accessFilters.addEventListener('click', (e) => {
            const btn = e.target.closest('.chip');
            if (!btn) return;
            btn.classList.toggle('active');
            state.freeOnly = btn.classList.contains('active');
            applyFilters();
        });

        // Search
        let searchDebounce;
        dom.searchInput.addEventListener('input', () => {
            clearTimeout(searchDebounce);
            const val = dom.searchInput.value.trim();
            dom.searchClear.classList.toggle('hidden', !val);
            searchDebounce = setTimeout(() => {
                state.searchQuery = val;
                applyFilters();
            }, 200);
        });

        dom.searchClear.addEventListener('click', () => {
            dom.searchInput.value = '';
            dom.searchClear.classList.add('hidden');
            state.searchQuery = '';
            applyFilters();
            dom.searchInput.focus();
        });

        // Sort
        dom.sortBtn.addEventListener('click', () => {
            const orders = ['name', 'courts', 'city'];
            const idx = orders.indexOf(state.sortOrder);
            state.sortOrder = orders[(idx + 1) % orders.length];
            showToast(`Sorted by ${state.sortOrder === 'courts' ? 'court count' : state.sortOrder}`);
            applyFilters();
        });

        // Modal
        dom.modalClose.addEventListener('click', closeModal);
        dom.modalOverlay.addEventListener('click', (e) => {
            if (e.target === dom.modalOverlay) closeModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeModal();
        });

        // Mobile toggle
        dom.mobileToggle.addEventListener('click', () => {
            const isOpen = dom.sidebar.classList.toggle('open');
            dom.toggleIconList.classList.toggle('hidden', isOpen);
            dom.toggleIconMap.classList.toggle('hidden', !isOpen);
        });

        // Map controls
        dom.btnResetView.addEventListener('click', () => {
            state.map.flyTo([43.72, -79.42], 10, { duration: 0.8 });
        });

        dom.btnMyLocation.addEventListener('click', () => {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        state.map.flyTo([pos.coords.latitude, pos.coords.longitude], 13, { duration: 0.8 });
                        L.circleMarker([pos.coords.latitude, pos.coords.longitude], {
                            radius: 8,
                            fillColor: '#ff1d8e',
                            fillOpacity: 1,
                            color: '#fff',
                            weight: 3
                        }).addTo(state.map).bindPopup('You are here');
                        showToast('Found your location!');
                    },
                    () => showToast('Unable to get your location'),
                    { enableHighAccuracy: true }
                );
            } else {
                showToast('Geolocation not supported');
            }
        });

        // Update button — runs server-side scraper and refreshes data
        if (dom.btnUpdate) {
            dom.btnUpdate.addEventListener('click', async () => {
                dom.btnUpdate.disabled = true;
                showToast('Updating courts — this may take a moment...');
                try {
                    const resp = await fetch('/update', { method: 'POST' });
                    const body = await resp.json().catch(() => ({}));
                    if (resp.ok && body.ok) {
                        showToast('Update complete — reloading');
                        setTimeout(() => location.reload(), 800);
                    } else {
                        const msg = body.error || body.output || 'Update failed';
                        showToast(msg);
                        dom.btnUpdate.disabled = false;
                    }
                } catch (e) {
                    console.error('Update error', e);
                    showToast('Update request failed');
                    dom.btnUpdate.disabled = false;
                }
            });
        }

        // Resize handler
        window.addEventListener('resize', () => {
            state.map.invalidateSize();
        });
    }

    // ============ BOOT ============
    document.addEventListener('DOMContentLoaded', init);
})();
