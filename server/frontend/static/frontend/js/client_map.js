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
  const radars = []; // {id, type, center: [lon,lat], speed_limit, verified, marker, el, sector}
  let polygonsInitialized = false;
  let pickMode = null; // 'from' | 'to' | null

  const cfg = window.CLIENT_CONFIG || {};
  const RADARS_URL = cfg.apiRadarsUrl || '/api/radars/';
  const ROUTE_URL = cfg.apiRouteUrl || '/api/route/';

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
    document.getElementById('btn-draw').addEventListener('click', toggleDrawMode);
    document.getElementById('btn-clear').addEventListener('click', clearAll);
    document.getElementById('btn-route').addEventListener('click', getRouteFromApi);
    document.getElementById('from-pick-btn').addEventListener('click', () => togglePickMode('from'));
    document.getElementById('to-pick-btn').addEventListener('click', () => togglePickMode('to'));

    // Fetch radars in background
    fetchAllRadars().then((list) => {
      list.forEach(addRadarToMap);
      computeImpactedRadars();
      // Add/update radar polygons layer
      updateRadarPolygonsLayer(new Set());
    }).catch(err => console.error('Failed loading radars', err));

    // Update counts on draw events
    map.on('draw.create', onDrawChanged);
    map.on('draw.update', onDrawChanged);
    map.on('draw.delete', onDrawDeleted);

    initSearch('from-input', 'from-results', setFromLocation);
    initSearch('to-input', 'to-results', setToLocation);

    map.on('click', onMapClickForPick);
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

  function toggleDrawMode() {
    try {
      const mode = draw.getMode();
      if (mode !== 'draw_line_string') {
        draw.changeMode('draw_line_string');
        // turn off pick mode while drawing
        setPickMode(null);
      } else {
        draw.changeMode('simple_select');
      }
    } catch (e) {
      console.warn('Failed to toggle draw mode', e);
    }
  }

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
    // Clear markers
    if (fromMarker) { fromMarker.remove(); fromMarker = null; }
    if (toMarker) { toMarker.remove(); toMarker = null; }
    document.getElementById('from-input').value = '';
    document.getElementById('to-input').value = '';
    computeImpactedRadars();
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
          type: item.type,
          speed_limit: item.speed_limit,
          verified: item.verified,
          center,
          sector
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
    const el = document.createElement('div');
    el.className = 'radar-marker';
    el.textContent = '📡';
    el.title = 'Radar';
    el.style.cssText = 'font-size:18px; line-height:1; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.4)); transition: opacity 0.2s;';
    const m = new maplibregl.Marker({ element: el })
      .setLngLat(radar.center)
      .setPopup(new maplibregl.Popup().setHTML(`<div><strong>Radar #${radar.id}</strong><br>Type: ${radar.type}${radar.speed_limit ? `<br>Speed: ${radar.speed_limit} km/h` : ''}</div>`))
      .addTo(map);
    radar.marker = m;
    radar.el = el;
    radarMarkers.push(m);
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

  function initSearch(inputId, resultsContainerId, onPick) {
    const input = document.getElementById(inputId);
    const container = document.getElementById(resultsContainerId);
    input.addEventListener('input', debounce(async () => {
      const q = input.value.trim();
      if (q.length < 3) { clearDropdown(); return; }
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
  }

  function setFromLocation(pick) {
    if (fromMarker) fromMarker.remove();
    fromMarker = new maplibregl.Marker({ color: '#1f6feb' }).setLngLat(pick.coord).setPopup(new maplibregl.Popup().setHTML('<strong>From</strong>')).addTo(map);
    map.flyTo({ center: pick.coord, zoom: 13, duration: 800 });
  }
  function setToLocation(pick) {
    if (toMarker) toMarker.remove();
    toMarker = new maplibregl.Marker({ color: '#2da44e' }).setLngLat(pick.coord).setPopup(new maplibregl.Popup().setHTML('<strong>To</strong>')).addTo(map);
    map.flyTo({ center: pick.coord, zoom: 13, duration: 800 });
  }

  async function getRouteFromApi() {
    if (!fromMarker || !toMarker) {
      alert('Please select both From and To locations.');
      return;
    }
    const from = fromMarker.getLngLat();
    const to = toMarker.getLngLat();
    const url = new URL(ROUTE_URL, window.location.origin);
    url.searchParams.set('from', `${from.lng},${from.lat}`);
    url.searchParams.set('to', `${to.lng},${to.lat}`);
    try {
      const res = await fetch(url.toString());
      if (!res.ok) throw new Error('routing failed');
      const feature = await res.json();
      draw.deleteAll();
      const added = draw.add(feature);
      routeFeatureId = Array.isArray(added) ? added[0] : (added && added.id);
      fitBoundsToFeature(feature);
      computeImpactedRadars();
    } catch (e) {
      console.error(e);
      alert('Unable to load route at this time.');
    }
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
    return line || null;
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
