/* Client route planner map logic
 * - Search from/to via Nominatim
 * - Load all radars via paginated API
 * - Get route via API (straight line placeholder)
 * - Or draw a polyline manually
 * - Buffer route and count impacted radars using Turf
 */

(function () {
  let map;
  let draw;
  let fromMarker = null;
  let toMarker = null;
  let routeFeatureId = null;
  let radarMarkers = [];
  const radars = []; // {id, type(category_code), center, speed_limit, verified, marker, el, sector, icon_url, icon_color}
  let polygonsInitialized = false;
  let pickMode = null; // 'from' | 'to' | null
  let apiRouteFeature = null; // Feature from routing API
  let sidebarMode = 'nearby'; // 'nearby' | 'impacted'

  const cfg = window.CLIENT_CONFIG || {};
  const RADARS_URL = cfg.apiRadarsUrl || '/api/radars/';
  const ROUTE_URL = cfg.apiRouteUrl || '/api/route/';
  const RADARS_IMPACTED_URL = cfg.apiRadarsImpactedUrl || '/api/radars/impacted/';
  let lastImpactedIds = new Set();
  const CLUSTER_SOURCE_ID = 'radar-points';
  const CLUSTER_LAYER_ID = 'radar-clusters';
  const CLUSTER_COUNT_LAYER_ID = 'radar-cluster-count';
  const CLUSTER_UNCLUSTERED_LAYER_ID = 'radar-unclustered';
  const CLUSTER_THRESHOLD_Z = 14; // show clusters below this zoom

  function initMap() {
    const STYLE_URL = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
    map = new maplibregl.Map({
      container: 'client-map',
      style: STYLE_URL,
      center: [71.7761, 40.3836],
      zoom: 12
    });
    map.on('load', onMapLoad);
  }

  function onMapLoad() {
    if (typeof MapboxDraw === 'undefined') {
      console.error('MapboxDraw not loaded.');
      return;
    }
    draw = new MapboxDraw({
      displayControlsDefault: false,
      controls: { line_string: false, trash: false },
      defaultMode: 'simple_select'
    });
    map.addControl(draw);

    // Wire UI
    document.getElementById('btn-clear').addEventListener('click', clearAll);
    document.getElementById('from-pick-btn').addEventListener('click', () => togglePickMode('from'));
    document.getElementById('to-pick-btn').addEventListener('click', () => togglePickMode('to'));

    // Fetch radars in background
    fetchAllRadars().then((list) => {
      list.forEach(addRadarToMap);
      computeImpactedRadars();
      // Add/update radar polygons layer
      updateRadarPolygonsLayer(new Set());
      renderNearbyList();
    }).catch(err => console.error('Failed loading radars', err));

    // Update counts on draw events
    map.on('draw.create', onDrawChanged);
    map.on('draw.update', onDrawChanged);
    map.on('draw.delete', onDrawDeleted);

    initSearch('from-input', 'from-results', setFromLocation);
    initSearch('to-input', 'to-results', setToLocation);

    map.on('click', onMapClickForPick);

    // Try query params auto-fill and auto-route
    tryAutoPopulateFromQuery();

    // Update nearby list on map move if no active route
    map.on('moveend', () => { if (!apiRouteFeature) renderNearbyList(); });

    // Ensure correct sizing on large screens
    setTimeout(() => { try { map.resize(); } catch(_){} }, 50);
    window.addEventListener('resize', () => { try { map.resize(); } catch(_){} });

    // Update live map view info (zoom/bearing/pitch)
    const updateView = () => updateMapViewInfo();
    map.on('move', updateView);
    map.on('zoom', updateView);
    map.on('rotate', updateView);
    map.on('pitch', updateView);
    updateMapViewInfo();

    // Clusters disabled
  }

  function onDrawChanged(e) {
    // Keep only a single route feature
    const all = draw.getAll();
    const line = all.features.find(f => f.geometry && f.geometry.type === 'LineString');
    if (line) {
      // Remove others
      all.features.filter(f => f.id !== line.id).forEach(f => draw.delete(f.id));
      routeFeatureId = line.id;
    }
    computeImpactedRadars();
  }

  function onDrawDeleted() {
    routeFeatureId = null;
    computeImpactedRadars();
  }

  // Manual draw mode is disabled in current UX (auto-routing). Keep function in case needed later.

  function setPickMode(kind) {
    pickMode = kind; // 'from' | 'to' | null
    const fromBtn = document.getElementById('from-pick-btn');
    const toBtn = document.getElementById('to-pick-btn');
    fromBtn.classList.toggle('active', pickMode === 'from');
    toBtn.classList.toggle('active', pickMode === 'to');
    map.getCanvas().style.cursor = pickMode ? 'crosshair' : '';
    // Ensure draw not in drawing mode during pick
    try { if (draw && pickMode) draw.changeMode('simple_select'); } catch (_) {}
  }

  function togglePickMode(kind) {
    setPickMode(pickMode === kind ? null : kind);
  }

  function onMapClickForPick(e) {
    if (!pickMode) return;
    const coord = [e.lngLat.lng, e.lngLat.lat];
    if (pickMode === 'from') {
      setFromLocation({ coord, name: `Pin: ${coord[1].toFixed(6)}, ${coord[0].toFixed(6)}` });
      document.getElementById('from-input').value = `Pin: ${coord[1].toFixed(6)}, ${coord[0].toFixed(6)}`;
    } else if (pickMode === 'to') {
      setToLocation({ coord, name: `Pin: ${coord[1].toFixed(6)}, ${coord[0].toFixed(6)}` });
      document.getElementById('to-input').value = `Pin: ${coord[1].toFixed(6)}, ${coord[0].toFixed(6)}`;
    }
    setPickMode(null);
  }

  function clearAll() {
    // Clear draw
    draw.deleteAll();
    routeFeatureId = null;
    clearApiRoute();
    lastImpactedIds = new Set();
    // Clear markers
    if (fromMarker) { fromMarker.remove(); fromMarker = null; }
    if (toMarker) { toMarker.remove(); toMarker = null; }
    document.getElementById('from-input').value = '';
    document.getElementById('to-input').value = '';
    computeImpactedRadars();
    updateRouteStats();
  }

  async function fetchAllRadars() {
    const results = [];
    let page = 1;
    while (true) {
      const url = new URL(RADARS_URL, window.location.origin);
      url.searchParams.set('page', page);
      // Only verified radars are returned to anonymous; this is fine for client use.
      const res = await fetch(url.toString(), { headers: { 'Accept': 'application/json' } });
      if (!res.ok) throw new Error('Failed radar list');
      const payload = await res.json();
      const items = payload.results || payload; // if pagination disabled
      if (!items || items.length === 0) break;
      for (const item of items) {
        // Non-GIS serializer includes center as {latitude, longitude}
        let center = null;
        if (item.center && item.center.longitude != null && item.center.latitude != null) {
          const lon = parseFloat(item.center.longitude);
          const lat = parseFloat(item.center.latitude);
          if (!Number.isNaN(lon) && !Number.isNaN(lat)) {
            center = [lon, lat];
          }
        }
        // Parse sector polygon if present (can be a serialized string)
        let sector = null;
        if (item.sector) {
          try {
            sector = (typeof item.sector === 'string') ? JSON.parse(item.sector) : item.sector;
            if (!(sector && sector.type === 'Polygon' && Array.isArray(sector.coordinates))) {
              sector = null;
            }
          } catch (_) { sector = null; }
        }
        results.push({
          id: item.id,
          type: item.category_code || item.type || null,
          speed_limit: item.speed_limit,
          verified: item.verified,
          center,
          sector,
          icon_url: item.icon_url || null,
          icon_color: item.icon_color || null,
        });
      }
      if (!payload.next) break;
      page += 1;
      if (page > 20) break; // safety cap
    }
    return results;
  }

  function addRadarToMap(radar) {
    radars.push(radar);
    if (!radar.center) return;
    let el;
    if (radar.icon_url) {
      el = document.createElement('img');
      el.src = radar.icon_url;
      el.alt = 'radar';
      el.style.cssText = 'width:20px;height:20px;object-fit:contain;display:block;';
      el.className = 'radar-marker';
      el.title = 'Radar';
    } else {
      el = document.createElement('span');
      el.textContent = '📹';
      el.className = 'radar-marker';
      el.title = 'Radar';
      el.style.cssText = 'font-size:18px;line-height:1;filter:drop-shadow(0 1px 2px rgba(0,0,0,0.4));';
    }
    const m = new maplibregl.Marker({ element: el })
      .setLngLat(radar.center)
      .setPopup(new maplibregl.Popup().setHTML(`<div><strong>Radar #${radar.id}</strong><br>Category: ${typeLabel(radar.type)}${radar.speed_limit ? `<br>Speed: ${radar.speed_limit} km/h` : ''}</div>`))
      .addTo(map);
    radar.marker = m;
    radar.el = el;
    // If we have a known impacted set, set initial opacity accordingly
    if (lastImpactedIds && lastImpactedIds.size) {
      el.style.opacity = lastImpactedIds.has(radar.id) ? '1' : '0.35';
    }
    radarMarkers.push(m);
    // clustering disabled
  }

  function ensurePolygonsLayers() {
    if (polygonsInitialized) return;
    const srcId = 'radar-polygons';
    if (!map.getSource(srcId)) {
      map.addSource(srcId, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    }
    if (!map.getLayer('radar-polygons-fill')) {
      map.addLayer({
        id: 'radar-polygons-fill',
        type: 'fill',
        source: srcId,
        paint: {
          'fill-color': '#dc3545',
          'fill-opacity': [
            'case', ['==', ['get', 'impacted'], true], 0.35, 0.15
          ]
        }
      });
    }
    if (!map.getLayer('radar-polygons-outline')) {
      map.addLayer({
        id: 'radar-polygons-outline',
        type: 'line',
        source: srcId,
        paint: {
          'line-color': '#b02a37',
          'line-width': 1.5,
          'line-opacity': [
            'case', ['==', ['get', 'impacted'], true], 0.9, 0.5
          ]
        }
      });
    }
    polygonsInitialized = true;
  }

  function updateRadarPolygonsLayer(impactedIdsSet) {
    ensurePolygonsLayers();
    const src = map.getSource('radar-polygons');
    if (!src) return;
    const features = radars
      .filter(r => r.sector)
      .map(r => ({
        type: 'Feature',
        properties: {
          id: r.id,
          impacted: impactedIdsSet.has(r.id)
        },
        geometry: r.sector
      }));
    const fc = { type: 'FeatureCollection', features };
    src.setData(fc);
  }

  // Clustering feature removed

  function initSearch(inputId, resultsContainerId, onPick) {
    const input = document.getElementById(inputId);
    const container = document.getElementById(resultsContainerId);
    input.addEventListener('input', debounce(async () => {
      const q = input.value.trim();
      if (q.length < 3) { clearDropdown(); return; }
      const parsed = parseCoordString(q);
      if (parsed) {
        // Show a quick option to use coordinates
        const dd = document.createElement('div');
        dd.className = 'dropdown';
        const opt = document.createElement('div');
        opt.className = 'item';
        opt.textContent = `Use coordinates: ${parsed[1].toFixed(6)}, ${parsed[0].toFixed(6)}`;
        opt.addEventListener('click', () => {
          onPick({ name: 'Coordinates', coord: parsed });
          // reflect normalized value in the input for clarity
          input.value = `${parsed[1].toFixed(6)}, ${parsed[0].toFixed(6)}`;
          clearDropdown();
        });
        dd.appendChild(opt);
        clearDropdown();
        container.appendChild(dd);
        return;
      }
      try {
        const searchQuery = `${q}, Uzbekistan`;
        const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}&limit=5&countrycodes=uz&addressdetails=1`);
        const data = await res.json();
        renderDropdown(data);
      } catch (e) {
        renderDropdown([]);
      }
    }, 300));

    function renderDropdown(items) {
      clearDropdown();
      const dd = document.createElement('div');
      dd.className = 'dropdown';
      if (!items || items.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'item';
        empty.textContent = 'No results';
        dd.appendChild(empty);
      } else {
        items.forEach(it => {
          const d = document.createElement('div');
          d.className = 'item';
          d.innerHTML = `<div style="font-weight:600;">${it.display_name.split(',')[0]}</div><div style="font-size:12px;color:#666;">${it.display_name}</div>`;
          d.addEventListener('click', () => {
            input.value = it.display_name.split(',')[0];
            onPick({ name: it.display_name, coord: [parseFloat(it.lon), parseFloat(it.lat)] });
            clearDropdown();
          });
          dd.appendChild(d);
        });
      }
      container.appendChild(dd);
    }
    function clearDropdown() {
      container.innerHTML = '';
    }
    document.addEventListener('click', (e) => {
      if (!container.contains(e.target) && e.target !== input) {
        clearDropdown();
      }
    });

    // Enter to route if both markers present
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const parsed = parseCoordString(input.value.trim());
        if (parsed) {
          onPick({ name: 'Coordinates', coord: parsed });
          input.value = `${parsed[1].toFixed(6)}, ${parsed[0].toFixed(6)}`;
          clearDropdown();
          setTimeout(() => { if (fromMarker && toMarker) getRouteFromApi(); }, 10);
        } else {
          setTimeout(() => { if (fromMarker && toMarker) getRouteFromApi(); }, 10);
        }
      }
    });

    // Accept coordinates on blur as well (paste-and-tab flow)
    input.addEventListener('blur', () => {
      const parsed = parseCoordString(input.value.trim());
      if (parsed) {
        onPick({ name: 'Coordinates', coord: parsed });
        input.value = `${parsed[1].toFixed(6)}, ${parsed[0].toFixed(6)}`;
      }
    });
  }

  function setFromLocation(pick) {
    if (fromMarker) fromMarker.remove();
    const el = document.createElement('div');
    el.textContent = '📍';
    el.title = 'From';
    el.style.cssText = 'font-size: 24px; line-height: 1; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.45));';
    fromMarker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
      .setLngLat(pick.coord)
      .setPopup(new maplibregl.Popup().setHTML('<strong>From</strong>'))
      .addTo(map);
    // Keep current zoom when pinning on map; allow zoom when set via search
    const opts = pickMode ? { center: pick.coord, duration: 600 } : { center: pick.coord, zoom: 13, duration: 800 };
    map.easeTo(opts);
    if (toMarker) { getRouteFromApi(); }
  }
  function setToLocation(pick) {
    if (toMarker) toMarker.remove();
    const el = document.createElement('div');
    el.textContent = '🏁';
    el.title = 'To';
    el.style.cssText = 'font-size: 24px; line-height: 1; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.45));';
    toMarker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
      .setLngLat(pick.coord)
      .setPopup(new maplibregl.Popup().setHTML('<strong>To</strong>'))
      .addTo(map);
    const opts = pickMode ? { center: pick.coord, duration: 600 } : { center: pick.coord, zoom: 13, duration: 800 };
    map.easeTo(opts);
    if (fromMarker) { getRouteFromApi(); }
  }

  async function getRouteFromApi() {
    if (!fromMarker || !toMarker) {
      alert('Please select both From and To locations.');
      return;
    }
    setLoading(true);
    const from = fromMarker.getLngLat();
    const to = toMarker.getLngLat();
    const url = new URL(RADARS_IMPACTED_URL, window.location.origin);
    url.searchParams.set('from', `${from.lng},${from.lat}`);
    url.searchParams.set('to', `${to.lng},${to.lat}`);
    const proxEl = document.getElementById('proximity');
    if (proxEl && proxEl.value) url.searchParams.set('buffer', proxEl.value);
    try {
      const res = await fetch(url.toString());
      if (!res.ok) throw new Error('routing failed');
      const payload = await res.json();
      const feature = payload.route || payload; // support old shape
      setApiRouteFeature(feature);
      draw.deleteAll(); // prefer API route visualization
      applyImpactedFromResponse(payload.radars || [], payload.impacted_count);
      updateRouteStats(feature.properties && feature.properties.summary);
    } catch (e) {
      console.error(e);
      alert('Unable to load route at this time.');
    } finally { setLoading(false); }
  }

  function applyImpactedFromResponse(radarsList, impactedCount) {
    // Ensure base radars are present
    const byId = new Map(radars.map(r => [r.id, r]));
    const impactedIdSet = new Set();
    for (const item of radarsList) {
      impactedIdSet.add(item.id);
      let r = byId.get(item.id);
      let center = null;
      if (item.center && item.center.longitude != null && item.center.latitude != null) {
        const lon = parseFloat(item.center.longitude);
        const lat = parseFloat(item.center.latitude);
        if (!Number.isNaN(lon) && !Number.isNaN(lat)) center = [lon, lat];
      }
      if (!r) {
        r = { id: item.id, type: item.type || item.category_code || null, speed_limit: item.speed_limit, verified: item.verified, center, icon_url: item.icon_url || null, icon_color: item.icon_color || null };
        addRadarToMap(r);
        byId.set(r.id, r);
      }
    }
    lastImpactedIds = impactedIdSet;
    // Update opacity for all markers
    for (const r of radars) {
      if (!r.el) continue;
      r.el.style.opacity = impactedIdSet.size ? (impactedIdSet.has(r.id) ? '1' : '0.35') : '1';
    }
    // Update polygons layer highlighting
    updateRadarPolygonsLayer(impactedIdSet);
    // Update counter
    const outEl = document.getElementById('radar-count');
    if (outEl) outEl.textContent = String(impactedCount != null ? impactedCount : impactedIdSet.size);

    // Update sidebar
    sidebarMode = 'impacted';
    const titleEl = document.getElementById('sidebar-title');
    const subEl = document.getElementById('sidebar-sub');
    if (titleEl) titleEl.textContent = 'Impacted Radars';
    if (subEl) subEl.textContent = `${impactedCount || impactedIdSet.size} on route`;
    renderSidebarList(radarsList || []);
  }

  function setApiRouteFeature(feature) {
    apiRouteFeature = feature;
    ensureRouteLayer();
    const src = map.getSource('active-route');
    if (src) src.setData(feature);
    updateRoutePointsLayer(feature);
    fitBoundsToFeature(feature);
    updateRouteHeading(feature);
  }

  function clearApiRoute() {
    apiRouteFeature = null;
    const src = map.getSource('active-route');
    if (src) src.setData({ type: 'FeatureCollection', features: [] });
    const psrc = map.getSource('route-points');
    if (psrc) psrc.setData({ type: 'FeatureCollection', features: [] });
    // reset heading
    const h = document.getElementById('route-heading'); if (h) h.textContent = '-';
  }

  function fitBoundsToFeature(feature) {
    try {
      const coords = feature.geometry.coordinates;
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      coords.forEach(([x, y]) => { if (x < minX) minX = x; if (y < minY) minY = y; if (x > maxX) maxX = x; if (y > maxY) maxY = y; });
      map.fitBounds([[minX, minY], [maxX, maxY]], { padding: 40, duration: 600 });
    } catch (_) { /* no-op */ }
  }

  function getCurrentRouteFeature() {
    if (!routeFeatureId) return null;
    const f = draw.get(routeFeatureId);
    if (f && f.geometry && f.geometry.type === 'LineString') return f;
    // fallback: the only line in collection
    const all = draw.getAll();
    const line = all.features.find(feat => feat.geometry && feat.geometry.type === 'LineString');
    if (line) return line;
    // fallback to API route
    return apiRouteFeature;
  }

  function computeImpactedRadars() {
    const route = getCurrentRouteFeature();
    const outEl = document.getElementById('radar-count');
    const radiusMeters = parseFloat(document.getElementById('proximity').value || '50');
    // If no route: show all radars at full opacity and set count to 0 (no route to compare)
    if (!route || !Array.isArray(route.geometry.coordinates) || route.geometry.coordinates.length < 2) {
      for (const r of radars) {
        if (r && r.el) r.el.style.opacity = '1';
      }
      outEl.textContent = '0';
      updateRadarPolygonsLayer(new Set());
      return;
    }
    try {
      const line = turf.lineString(route.geometry.coordinates);
      const buffered = turf.buffer(line, radiusMeters, { units: 'meters' });
      let count = 0;
      const impactedIds = new Set();
      for (const r of radars) {
        if (!r.center) continue;
        const pt = turf.point(r.center);
        let inside = turf.booleanPointInPolygon(pt, buffered);
        // If polygon exists, also consider polygon intersection with buffer
        if (!inside && r.sector) {
          try {
            const poly = turf.polygon(r.sector.coordinates);
            if (turf.booleanIntersects(buffered, poly)) inside = true;
          } catch (_) {}
        }
        if (r && r.el) r.el.style.opacity = inside ? '1' : '0.35';
        if (inside) { count += 1; impactedIds.add(r.id); }
      }
      outEl.textContent = String(count);
      updateRadarPolygonsLayer(impactedIds);
    } catch (e) {
      console.warn('buffer/count failed', e);
      outEl.textContent = '0';
      // Reset visibility to safe default
      for (const r of radars) { if (r && r.el) r.el.style.opacity = '1'; }
      updateRadarPolygonsLayer(new Set());
    }
  }

  function ensureRouteLayer() {
    if (!map.getSource('active-route')) {
      map.addSource('active-route', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    }
    if (!map.getLayer('active-route-line')) {
      map.addLayer({
        id: 'active-route-line',
        type: 'line',
        source: 'active-route',
        paint: {
          'line-color': '#2563eb',
          'line-width': 4,
          'line-opacity': 0.9
        }
      });
    }
    if (!map.getSource('route-points')) {
      map.addSource('route-points', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    }
    if (!map.getLayer('route-points')) {
      map.addLayer({
        id: 'route-points',
        type: 'circle',
        source: 'route-points',
        paint: {
          'circle-radius': 3,
          'circle-color': '#dc3545',
          'circle-stroke-width': 0
        }
      });
    }
  }

  function updateRoutePointsLayer(feature) {
    try {
      const coords = (feature && feature.geometry && feature.geometry.coordinates) || [];
      const pts = coords.map(c => ({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: c } }));
      const fc = { type: 'FeatureCollection', features: pts };
      const psrc = map.getSource('route-points');
      if (psrc) psrc.setData(fc);
    } catch (e) {
      // noop
    }
  }

  function updateRouteStats(summary) {
    const distEl = document.getElementById('route-distance');
    const durEl = document.getElementById('route-duration');
    const provEl = document.getElementById('route-provider');
    if (!summary) {
      distEl.textContent = '-'; durEl.textContent = '-'; provEl.textContent = '-';
      // If a manual route is present, compute an approximate distance
      const r = getCurrentRouteFeature();
      if (r && r.geometry && r.geometry.type === 'LineString') {
        try {
          const km = turf.length(turf.lineString(r.geometry.coordinates), { units: 'kilometers' });
          distEl.textContent = `${km.toFixed(2)} km`;
          durEl.textContent = '—';
          provEl.textContent = 'manual';
        } catch (_) {}
      }
      return;
    }
    if (typeof summary.distance_m === 'number') {
      const km = summary.distance_m / 1000;
      distEl.textContent = `${km.toFixed(2)} km`;
    }
    if (typeof summary.duration_s === 'number') {
      const mins = summary.duration_s / 60;
      durEl.textContent = `${mins.toFixed(1)} min`;
    }
    provEl.textContent = summary.provider || 'unknown';
  }

  function updateRouteHeading(feature) {
    try {
      const coords = (feature && feature.geometry && feature.geometry.coordinates) || [];
      const el = document.getElementById('route-heading');
      if (!el) return;
      if (!coords || coords.length < 2) { el.textContent = '-'; return; }
      const a = coords[0];
      const b = coords[coords.length - 1];
      let deg;
      if (window.turf) {
        deg = turf.bearing(turf.point(a), turf.point(b));
      } else {
        // fallback rough bearing
        const toRad = (d) => d * Math.PI / 180, toDeg = (r) => r * 180 / Math.PI;
        const lat1 = toRad(a[1]), lat2 = toRad(b[1]);
        const dLon = toRad(b[0] - a[0]);
        const y = Math.sin(dLon) * Math.cos(lat2);
        const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
        deg = toDeg(Math.atan2(y, x));
      }
      deg = ((deg % 360) + 360) % 360; // normalize 0..360
      const dir = bearingToCardinal(deg);
      el.textContent = `${deg.toFixed(1)}° ${dir}`;
    } catch (_) {}
  }

  function bearingToCardinal(deg) {
    const dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW','N'];
    return dirs[Math.round(deg/22.5)];
  }

  function updateMapViewInfo() {
    try {
      const z = map.getZoom();
      const b = map.getBearing();
      const p = map.getPitch();
      const zEl = document.getElementById('map-zoom'); if (zEl) zEl.textContent = (z!=null? z.toFixed(2):'-');
      const bEl = document.getElementById('map-bearing'); if (bEl) bEl.textContent = (b!=null? b.toFixed(1):'-') + '°';
      const pEl = document.getElementById('map-pitch'); if (pEl) pEl.textContent = (p!=null? p.toFixed(1):'-') + '°';
    } catch(_){}
  }

  function setLoading(isLoading) {
    const overlay = document.getElementById('loading-overlay');
    overlay.style.display = isLoading ? 'flex' : 'none';
    // No explicit route button anymore; just show overlay
  }

  function tryAutoPopulateFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const from = params.get('from');
    const to = params.get('to');
    const parse = (v) => {
      if (!v) return null;
      const parts = v.split(',').map(s => s.trim());
      if (parts.length !== 2) return null;
      let lon = parseFloat(parts[0]);
      let lat = parseFloat(parts[1]);
      // Heuristic: if first looks like latitude, swap
      if (Math.abs(lon) <= 90 && Math.abs(lat) <= 180) {
        const tmp = lon; lon = lat; lat = tmp;
      }
      if (Number.isNaN(lon) || Number.isNaN(lat)) return null;
      return [lon, lat];
    };
    const fromCoord = parse(from);
    const toCoord = parse(to);
    if (fromCoord) setFromLocation({ coord: fromCoord, name: `Pin: ${fromCoord[1].toFixed(6)}, ${fromCoord[0].toFixed(6)}` });
    if (toCoord) setToLocation({ coord: toCoord, name: `Pin: ${toCoord[1].toFixed(6)}, ${toCoord[0].toFixed(6)}` });
    if (fromCoord && toCoord) {
      getRouteFromApi();
    }
  }

  function parseCoordString(v) {
    if (!v || v.indexOf(',') === -1) return null;
    // tolerate labels and parens; keep digits, minus, dot, comma and spaces
    const cleaned = v.replace(/[^0-9.,\-\s]/g, '');
    const parts = cleaned.split(',').map(s => s.trim()).filter(Boolean);
    if (parts.length !== 2) return null;
    let a = parseFloat(parts[0]);
    let b = parseFloat(parts[1]);
    if (Number.isNaN(a) || Number.isNaN(b)) return null;
    // Accept both lat,lon and lon,lat; choose based on plausible ranges
    let lat, lon;
    if (Math.abs(a) <= 90 && Math.abs(b) <= 180) { lat = a; lon = b; }
    else if (Math.abs(b) <= 90 && Math.abs(a) <= 180) { lat = b; lon = a; }
    else return null;
    return [lon, lat];
  }

  // ---------------- Sidebar helpers ----------------
  function typeLabel(type) {
    if (!type) return 'Radar';
    try { return String(type).replace(/_/g, ' ').replace(/\b\w/g, s => s.toUpperCase()); } catch { return 'Radar'; }
  }

  function distanceKm(a, b) {
    const toRad = (d) => d * Math.PI / 180;
    const R = 6371.0;
    const dLat = toRad(b[1] - a[1]);
    const dLon = toRad(b[0] - a[0]);
    const lat1 = toRad(a[1]);
    const lat2 = toRad(b[1]);
    const t = Math.sin(dLat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLon/2)**2;
    return 2 * R * Math.asin(Math.sqrt(t));
  }

  function renderNearbyList() {
    if (!map || !map.getCenter) return;
    const c = map.getCenter();
    const center = [c.lng, c.lat];
    const withDist = radars.filter(r => r.center).map(r => ({ r, d: distanceKm(r.center, center) }));
    withDist.sort((a,b) => a.d - b.d);
    const top = withDist.slice(0, 10).map(x => ({
      id: x.r.id,
      type: x.r.type,
      speed_limit: x.r.speed_limit,
      verified: x.r.verified,
      center: { longitude: x.r.center[0], latitude: x.r.center[1] },
      distance_km: x.d,
      icon_url: x.r.icon_url || null,
      icon_color: x.r.icon_color || null,
    }));
    sidebarMode = 'nearby';
    const titleEl = document.getElementById('sidebar-title');
    const subEl = document.getElementById('sidebar-sub');
    if (titleEl) titleEl.textContent = 'Nearby Radars';
    if (subEl) subEl.textContent = 'Top 10 near map center';
    renderSidebarList(top);
  }

  function renderSidebarList(items) {
    const list = document.getElementById('radar-list');
    if (!list) return;
    list.innerHTML = '';
    if (!items || !items.length) {
      list.innerHTML = '<div class="radar-item"><div class="ri-main"><div class="ri-title">No radars</div><div class="ri-meta">Try changing the route or moving the map</div></div></div>';
      return;
    }
    items.forEach(item => {
      const el = document.createElement('div');
      el.className = 'radar-item';
      const iconHtml = item.icon_url ? `<img src=\"${item.icon_url}\" alt=\"icon\" style=\\\"width:18px;height:18px;object-fit:contain;display:block;\\\"/>` : '📹';
      el.innerHTML = `
        <div class=\"ri-icon\">${iconHtml}</div>
        <div class=\"ri-main\">
          <div class=\"ri-title\">${typeLabel(item.type)} ${item.speed_limit ? `· ${item.speed_limit} km/h` : ''}</div>
          <div class=\"ri-meta\">${item.center ? `${Number(item.center.latitude).toFixed(6)}, ${Number(item.center.longitude).toFixed(6)}` : ''}
            ${typeof item.distance_km === 'number' ? ` · ${(item.distance_km).toFixed(1)} km` : ''}
            ${item.verified ? `<span class=\\"ri-badge ok\\">Verified</span>` : `<span class=\\"ri-badge warn\\">Unverified</span>`}
          </div>
        </div>`;
      el.addEventListener('click', () => {
        let lngLat = null;
        if (item.center) {
          lngLat = [Number(item.center.longitude), Number(item.center.latitude)];
        } else {
          const found = radars.find(r => r.id === item.id && r.center);
          if (found) lngLat = found.center;
        }
        if (lngLat) {
          map.flyTo({ center: lngLat, zoom: 16, duration: 600 });
        }
        const found = radars.find(r => r.id === item.id);
        if (found && found.marker) {
          try { found.marker.togglePopup(); } catch (_) {}
        }
      });
      list.appendChild(el);
    });
  }

  function debounce(fn, wait) {
    let t = null;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  // Boot
  document.addEventListener('DOMContentLoaded', initMap);
})();
