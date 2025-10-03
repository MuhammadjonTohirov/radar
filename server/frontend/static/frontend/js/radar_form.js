// Radar form map interaction JavaScript
let map;
let draw;
let currentPolygon = null;
let radarMarker = null;
// Location search functionality with dropdown
let searchResultsDiv = null;
let searchMarker = null;
// Enhanced controls
let circleControl = null;
let sectorControl = null;
let sectorModeActive = false;
let sectorDragActive = false;
let sectorDragStart = null; // [lon, lat]
let pinControl = null;
let polygonControl = null;
let trashControl = null;
let pinModeActive = false;
let polygonModeActive = false;
let sectorPreview = {
    lineSource: 'sector-preview-line',
    rectSource: 'sector-preview-rect',
    arrowSource: 'sector-preview-arrow',
    lineLayer: 'sector-preview-line-layer',
    rectFillLayer: 'sector-preview-rect-fill-layer',
    rectLineLayer: 'sector-preview-rect-line-layer',
    arrowFillLayer: 'sector-preview-arrow-fill-layer'
};

// Helper: parse a coordinate string accepting "lat,lon" or "lon,lat"
function parseCoordString(v) {
    if (!v || v.indexOf(',') === -1) return null;
    const cleaned = v.replace(/[^0-9.,\-\s]/g, '');
    const parts = cleaned.split(',').map(s => s.trim()).filter(Boolean);
    if (parts.length !== 2) return null;
    let a = parseFloat(parts[0]);
    let b = parseFloat(parts[1]);
    if (Number.isNaN(a) || Number.isNaN(b)) return null;
    // Determine order by plausible ranges
    let lat, lon;
    if (Math.abs(a) <= 90 && Math.abs(b) <= 180) { lat = a; lon = b; }
    else if (Math.abs(b) <= 90 && Math.abs(a) <= 180) { lat = b; lon = a; }
    else return null;
    return { lon, lat };
}

// Helper: place radar pin and update hidden fields, recenter map (keep current zoom)
function placeRadarPin(lon, lat) {
    if (radarMarker) { radarMarker.remove(); }
    const markerEl = document.createElement('div');
    markerEl.textContent = '📡';
    markerEl.title = 'Radar';
    markerEl.style.cssText = `
        font-size: 18px;
        line-height: 1;
        filter: drop-shadow(0 1px 2px rgba(0,0,0,0.4));
        cursor: pointer;
    `;
    radarMarker = new maplibregl.Marker({ element: markerEl })
        .setLngLat([lon, lat])
        .setPopup(new maplibregl.Popup().setHTML('<div><strong>Radar Location</strong></div>'))
        .addTo(map);

    // Update hidden form fields
    if (typeof radarData !== 'undefined' && !radarData.hasGIS) {
        document.getElementById(radarData.centerLatId).value = Number(lat).toFixed(6);
        document.getElementById(radarData.centerLonId).value = Number(lon).toFixed(6);
    }
    try { map.easeTo({ center: [lon, lat], duration: 600 }); } catch(_) {}
}

// Initialize map
function initMap() {
    // Try one of these public style JSONs (pick the one that shows desired map detail):
    // - Carto Positron (clean, good labels): https://basemaps.cartocdn.com/gl/positron-gl-style/style.json
    // - Stadia OSM Bright (OSM-based): https://tiles.stadiamaps.com/styles/osm-bright.json
    // - Klokantech basic (OpenMapTiles demo): https://openmaptiles.github.io/klokantech-basic-gl-style/style-cdn.json
    // If a style requires an API key, you'll see 401/CORS errors in the Network tab.
    const STYLE_URL = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

    map = new maplibregl.Map({
        container: 'map',
        style: STYLE_URL,
        center: [71.7761, 40.3836], // Fergana, Uzbekistan (lon, lat)
        zoom: 12
    });

    // Wait until the style is loaded before instantiating Draw and interacting with style sources
    map.on('load', function () {
        // Defensive logging to help debug missing layers/sources
        console.log('Map loaded. style:', map.getStyle && map.getStyle().name);

        // Re-apply the intended initial view after the style fully loads.
        // Some styles or tiles can shift the rendered view until the style is ready,
        // and if the container had layout changes this ensures the correct zoom/center.
        // try {
        //     // enforce the intended initial view
        //     map.jumpTo({ center: [71.7761, 40.3836], zoom: 12 });
        //     map.resize();
        // } catch (err) {
        //     // Non-fatal — keep original behavior but log for debugging
        //     console.warn('Failed to enforce initial center/zoom:', err);
        // }
        map.on('error', (err) => {
            console.error('Map error event:', err);
        });

        // Control state variables already declared globally; reset here
        pinModeActive = false;
        polygonModeActive = false;

        // Add radar location pin control
        pinControl = document.createElement('div');
        pinControl.className = 'radar-pin-control';
        pinControl.title = 'Click to place radar location';

        // Add polygon drawing control
        polygonControl = document.createElement('div');
        polygonControl.className = 'radar-polygon-control';
        polygonControl.title = 'Click to draw detection area';

        // Add trash/clear control
        trashControl = document.createElement('div');
        trashControl.className = 'radar-trash-control';
        trashControl.title = 'Clear all drawings';

        // Event handlers (after all controls are created)
        pinControl.addEventListener('click', () => {
            pinModeActive = !pinModeActive;
            pinControl.classList.toggle('active', pinModeActive);
            pinControl.title = pinModeActive ? 'Click on map to place radar' : 'Click to place radar location';
            
            if (pinModeActive) {
                // Deactivate polygon mode - don't call changeMode to avoid recursion
                polygonModeActive = false;
                polygonControl.classList.remove('active');
                polygonControl.title = 'Click to draw detection area';
            }
        });

        polygonControl.addEventListener('click', () => {
            polygonModeActive = !polygonModeActive;
            polygonControl.classList.toggle('active', polygonModeActive);
            
            if (polygonModeActive) {
                // Deactivate pin mode
                pinModeActive = false;
                pinControl.classList.remove('active');
                pinControl.title = 'Click to place radar location';
                
                // Start drawing polygon
                draw.changeMode('draw_polygon');
                polygonControl.title = 'Drawing polygon - left-click to add points, double-click last point to finish, Esc or click button to cancel';
                console.log('Polygon drawing mode activated');
                // Prevent panning while drawing to avoid collisions with drag
                try { map.dragPan.disable(); } catch(_){}
                try { map.getCanvas().style.cursor = 'crosshair'; } catch(_){}
            } else {
                // Exit drawing mode safely
                try {
                    // Use a timeout to avoid immediate recursion
                    setTimeout(() => {
                        draw.changeMode('simple_select');
                    }, 10);
                } catch (error) {
                    console.warn('Error switching to simple_select mode:', error);
                }
                polygonControl.title = 'Click to draw detection area';
                console.log('Polygon drawing mode deactivated');
                // Re-enable panning when exiting polygon mode
                try { map.dragPan.enable(); } catch(_){}
                try { map.getCanvas().style.cursor = ''; } catch(_){}
            }
        });

        trashControl.addEventListener('click', () => {
            if (confirm('Clear all drawings on the map?')) {
                // Clear all drawings
                draw.deleteAll();
                clearPolygon();
                
                // Remove radar marker
                if (radarMarker) {
                    radarMarker.remove();
                    radarMarker = null;
                }
                
                // Remove search marker
                if (searchMarker) {
                    searchMarker.remove();
                    searchMarker = null;
                }
                
                // Reset modes - don't call changeMode to avoid recursion
                polygonModeActive = false;
                pinModeActive = false;
                polygonControl.classList.remove('active');
                pinControl.classList.remove('active');
                
                // Reset titles
                polygonControl.title = 'Click to draw detection area';
                pinControl.title = 'Click to place radar location';
            }
        });

        // Optional enhanced tools: circle and sector (behind feature flag)
        if (typeof radarData !== 'undefined' && radarData.enhancedDrawing) {
            circleControl = document.createElement('div');
            circleControl.className = 'radar-circle-control';
            circleControl.title = 'Create circle coverage from pin';

            sectorControl = document.createElement('div');
            sectorControl.className = 'radar-sector-control';
            sectorControl.title = 'Click and drag to set sector direction';

            circleControl.addEventListener('click', onCreateCircleFromPin);
            // Toggle sector drag drawing mode
            sectorControl.addEventListener('click', () => {
                sectorModeActive = !sectorModeActive;
                sectorControl.classList.toggle('active', sectorModeActive);
                if (sectorModeActive) {
                    enterSectorDragMode();
                } else {
                    exitSectorDragMode();
                }
            });
        }

        // Add controls to map container
        const mapContainer = document.getElementById('map');
        if (mapContainer) {
            mapContainer.appendChild(pinControl);
            mapContainer.appendChild(polygonControl);
            if (circleControl) mapContainer.appendChild(circleControl);
            if (sectorControl) mapContainer.appendChild(sectorControl);
            mapContainer.appendChild(trashControl);
        }

        // Handle right-click - just prevent context menu
        map.on('contextmenu', (e) => {
            e.preventDefault(); // Prevent browser context menu
            if (polygonModeActive) {
                console.log('Right-click detected during polygon drawing - use double-click on last point to finish');
            }
        });

        // Handle Escape key to cancel polygon drawing
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && polygonModeActive) {
                // Cancel polygon drawing
                polygonModeActive = false;
                polygonControl.classList.remove('active');
                polygonControl.title = 'Click to draw detection area';
                
                try {
                    setTimeout(() => {
                        draw.changeMode('simple_select');
                    }, 10);
                } catch (error) {
                    console.warn('Error switching to simple_select mode:', error);
                }
                
                console.log('Polygon drawing cancelled with Escape key');
                // Re-enable panning on cancel
                try { map.dragPan.enable(); } catch(_){}
                try { map.getCanvas().style.cursor = ''; } catch(_){}
            }
            if (e.key === 'Escape' && sectorDragActive) {
                // Cancel sector drag
                exitSectorDragMode();
                console.log('Sector drag cancelled with Escape key');
            }
        });

        // Handle map clicks for radar location placement
        map.on('click', (e) => {
            if (!pinModeActive) return;
            
            const lng = e.lngLat.lng;
            const lat = e.lngLat.lat;

            // Remove existing radar marker
            if (radarMarker) {
                radarMarker.remove();
            }

            // Create radar marker element (📡 emoji for clarity)
            const markerEl = document.createElement('div');
            markerEl.textContent = '📡';
            markerEl.title = 'Radar';
            markerEl.style.cssText = `
                font-size: 18px;
                line-height: 1;
                filter: drop-shadow(0 1px 2px rgba(0,0,0,0.4));
                cursor: pointer;
            `;

            // Add radar marker to map
            radarMarker = new maplibregl.Marker({ element: markerEl })
                .setLngLat([lng, lat])
                .setPopup(new maplibregl.Popup().setHTML('<div><strong>Radar Location</strong></div>'))
                .addTo(map);

            // Update center coordinates in form fields
            if (typeof radarData !== 'undefined' && !radarData.hasGIS) {
                document.getElementById(radarData.centerLatId).value = lat.toFixed(6);
                document.getElementById(radarData.centerLonId).value = lng.toFixed(6);
            }

            // Deactivate pin mode after placing marker
            pinModeActive = false;
            pinControl.classList.remove('active');
            pinControl.title = 'Click to place radar location';
        });

        // Initialize drawing controls
        if (typeof MapboxDraw === 'undefined') {
            console.error('MapboxDraw not loaded. Drawing controls will be disabled.');
            return;
        }

        draw = new MapboxDraw({
            displayControlsDefault: false,
            controls: {
                polygon: false,
                trash: false
            },
            defaultMode: 'simple_select'
        });

        map.addControl(draw);

        // Handle drawing events
        map.on('draw.create', (e) => {
            try {
                const feature = e && e.features && e.features[0];
                if (!feature || !feature.geometry) { updatePolygon(); return; }
                const geomType = feature.geometry.type;

                // Handle polygon finalize
                if (geomType === 'Polygon') {
                    updatePolygon();
                    polygonModeActive = false;
                    polygonControl.classList.remove('active');
                    polygonControl.title = 'Click to draw detection area';
                    // Re-enable panning after finishing polygon
                    try { map.dragPan.enable(); } catch(_){}
                    try { map.getCanvas().style.cursor = ''; } catch(_){}
                    return;
                }

                // Default behavior
                updatePolygon();
            } catch (err) {
                console.warn('draw.create handler error', err);
                updatePolygon();
            }
        });
        map.on('draw.delete', clearPolygon);
        map.on('draw.update', updatePolygon);

        // Load existing polygon if editing (only after draw exists)
        if (typeof radarData !== 'undefined' && radarData.isEditing) {
            loadExistingPolygon();
            loadExistingRadarLocation();
        }
    });
}

function updatePolygon() {
    const data = draw.getAll();
    if (data.features.length > 0) {
        const polygon = data.features[0];
        currentPolygon = polygon;
        
        // Calculate center point
        const coordinates = polygon.geometry.coordinates[0];
        let centerLat = 0, centerLon = 0;
        for (let coord of coordinates) {
            centerLon += coord[0];
            centerLat += coord[1];
        }
        centerLat /= coordinates.length;
        centerLon /= coordinates.length;
        
        // Update form fields
        if (!radarData.hasGIS) {
            document.getElementById(radarData.sectorJsonId).value = JSON.stringify(polygon.geometry);
            
            // Only set center coordinates if they haven't been set by pin placement
            // The center coordinates should represent the actual radar location (pin), not polygon center
            const centerLatEl = document.getElementById(radarData.centerLatId);
            const centerLonEl = document.getElementById(radarData.centerLonId);
            if (!centerLatEl.value || !centerLonEl.value) {
                console.warn('No radar pin location set. Please place a radar pin on the map to set the radar location.');
            }
        }
        
        // Show polygon info
        document.getElementById('polygon-info').style.display = 'block';
        document.getElementById('polygon-coords').textContent = 
            `Polygon with ${coordinates.length - 1} points`;
        document.getElementById('polygon-center').textContent = 
            `Center: ${centerLat.toFixed(6)}, ${centerLon.toFixed(6)}`;
    }
}

function clearPolygon() {
    currentPolygon = null;
    document.getElementById('polygon-info').style.display = 'none';
    
    if (!radarData.hasGIS) {
        document.getElementById(radarData.sectorJsonId).value = '';
        // Don't clear center coordinates here - they represent radar pin location, not polygon center
        // Only clear them if there's no radar pin marker
        if (!radarMarker) {
            document.getElementById(radarData.centerLatId).value = '';
            document.getElementById(radarData.centerLonId).value = '';
        }
    }
}

function loadExistingPolygon() {
    if (!draw) {
        console.warn('Attempted to load existing polygon before draw was initialized.');
        return;
    }
    if (radarData.isEditing && !radarData.hasGIS && radarData.sectorJson) {
        const existingPolygon = {
            type: 'Feature',
            geometry: radarData.sectorJson,
            properties: {}
        };
        // Add feature to draw
        draw.add(existingPolygon);
        
        // Center map on existing polygon
        const coords = existingPolygon.geometry.coordinates[0];
        let centerLat = 0, centerLon = 0;
        for (let coord of coords) {
            centerLon += coord[0];
            centerLat += coord[1];
        }
        centerLat /= coords.length;
        centerLon /= coords.length;
        
        map.setCenter([centerLon, centerLat]);
        // Trigger UI update
        updatePolygon();
    }
}

function loadExistingRadarLocation() {
    if (typeof radarData !== 'undefined' && radarData.isEditing && !radarData.hasGIS) {
        const centerLatEl = document.getElementById(radarData.centerLatId);
        const centerLonEl = document.getElementById(radarData.centerLonId);
        
        if (centerLatEl && centerLonEl && centerLatEl.value && centerLonEl.value) {
            const lat = parseFloat(centerLatEl.value);
            const lng = parseFloat(centerLonEl.value);
            
            if (!isNaN(lat) && !isNaN(lng)) {
                // Remove existing marker
                if (radarMarker) {
                    radarMarker.remove();
                }
                
                // Create radar marker element (📡 emoji for clarity)
                const markerEl = document.createElement('div');
                markerEl.textContent = '📡';
                markerEl.title = 'Radar';
                markerEl.style.cssText = `
                    font-size: 18px;
                    line-height: 1;
                    filter: drop-shadow(0 1px 2px rgba(0,0,0,0.4));
                    cursor: pointer;
                `;
                
                // Add radar marker to map
                radarMarker = new maplibregl.Marker({ element: markerEl })
                    .setLngLat([lng, lat])
                    .setPopup(new maplibregl.Popup().setHTML('<div><strong>Radar Location</strong></div>'))
                    .addTo(map);
            }
        }
    }
}

// ------------------------------------------------------------
// Enhanced tools (circle/sector) with graceful fallback
// ------------------------------------------------------------

function getRadarCenterFromFormOrMarker() {
    // Prefer marker position if available
    if (radarMarker && typeof radarMarker.getLngLat === 'function') {
        const c = radarMarker.getLngLat();
        return [c.lng, c.lat];
    }
    // Fallback to hidden fields (non-GIS mode)
    if (!radarData.hasGIS) {
        try {
            const lat = parseFloat(document.getElementById(radarData.centerLatId).value);
            const lon = parseFloat(document.getElementById(radarData.centerLonId).value);
            if (!Number.isNaN(lat) && !Number.isNaN(lon)) return [lon, lat];
        } catch (_) {}
    }
    return null;
}

function metersToDegrees(lat, meters) {
    const degLat = meters / 111320;
    const degLon = meters / (111320 * Math.max(0.000001, Math.cos(lat * Math.PI / 180)));
    return [degLon, degLat];
}

function makeCircleGeometryApprox(center, radiusM, steps = 64) {
    const [lon, lat] = center;
    const [dLon, dLat] = metersToDegrees(lat, radiusM);
    const coords = [];
    for (let i = 0; i < steps; i++) {
        const theta = (i / steps) * 2 * Math.PI;
        const x = lon + dLon * Math.cos(theta);
        const y = lat + dLat * Math.sin(theta);
        coords.push([x, y]);
    }
    coords.push(coords[0]);
    return { type: 'Polygon', coordinates: [coords] };
}

function projectFrom(centerLonLat, distanceM, bearingDeg) {
    const [lon, lat] = centerLonLat;
    const mPerDegLat = 111320.0;
    const mPerDegLon = 111320.0 * Math.max(0.000001, Math.cos(lat * Math.PI / 180));
    const rad = bearingDeg * Math.PI / 180;
    const dx = Math.sin(rad) * distanceM; // east component
    const dy = Math.cos(rad) * distanceM; // north component
    const dLon = dx / mPerDegLon;
    const dLat = dy / mPerDegLat;
    return [lon + dLon, lat + dLat];
}

function makeTrapezoidSector(centerLonLat, radiusM, bearingDeg) {
    const [lon, lat] = centerLonLat;
    if (!Number.isFinite(radiusM) || radiusM <= 0) {
        radiusM = 1;
    }
    const rad = bearingDeg * Math.PI / 180;
    const mPerDegLatCenter = 111320.0;
    const mPerDegLonCenter = 111320.0 * Math.max(0.000001, Math.cos(lat * Math.PI / 180));

    const outerCenter = projectFrom(centerLonLat, radiusM, bearingDeg);
    const mPerDegLonOuter = 111320.0 * Math.max(0.000001, Math.cos(outerCenter[1] * Math.PI / 180));

    const dirPerpEast = Math.cos(rad);      // east component for perpendicular vector
    const dirPerpNorth = -Math.sin(rad);    // north component for perpendicular vector

    const baseWidthRaw = (typeof radarData !== 'undefined' && radarData && radarData.sectorBaseWidthM !== undefined)
        ? Number(radarData.sectorBaseWidthM)
        : 20;
    const baseWidth = Math.max(baseWidthRaw || 20, 1);
    const innerHalfWidthM = baseWidth / 2;
    const outerHalfWidthM = innerHalfWidthM * 1.1; // 10% wider at the far end

    const innerLonOffset = (dirPerpEast * innerHalfWidthM) / mPerDegLonCenter;
    const innerLatOffset = (dirPerpNorth * innerHalfWidthM) / mPerDegLatCenter;
    const outerLonOffset = (dirPerpEast * outerHalfWidthM) / mPerDegLonOuter;
    const outerLatOffset = (dirPerpNorth * outerHalfWidthM) / mPerDegLatCenter;

    const innerRight = [lon + innerLonOffset, lat + innerLatOffset];
    const innerLeft = [lon - innerLonOffset, lat - innerLatOffset];
    const outerRight = [outerCenter[0] + outerLonOffset, outerCenter[1] + outerLatOffset];
    const outerLeft = [outerCenter[0] - outerLonOffset, outerCenter[1] - outerLatOffset];

    return {
        type: 'Polygon',
        coordinates: [[innerRight, outerRight, outerLeft, innerLeft, innerRight]]
    };
}

function makeArrowTriangle(startLonLat, endLonLat, lengthM = 12, widthM = 8) {
    // Returns a small triangle polygon at the end, pointing from start->end
    const [lon1, lat1] = startLonLat;
    const [lon2, lat2] = endLonLat;
    const midLat = (lat1 + lat2) / 2;
    const mPerDegLat = 111320.0;
    const mPerDegLon = 111320.0 * Math.max(0.000001, Math.cos(midLat * Math.PI / 180));
    // Direction vector in meters (from start to end)
    const vx = (lon2 - lon1) * mPerDegLon;
    const vy = (lat2 - lat1) * mPerDegLat;
    const len = Math.hypot(vx, vy);
    if (!isFinite(len) || len === 0) return null;
    const ux = vx / len;
    const uy = vy / len;
    const halfW = widthM / 2;
    // Base center behind the tip by lengthM
    const bx = (lon2 - (lengthM * ux) / mPerDegLon);
    const by = (lat2 - (lengthM * uy) / mPerDegLat);
    // Perpendicular unit
    const px = -uy;
    const py = ux;
    const left = [bx + (halfW * px) / mPerDegLon, by + (halfW * py) / mPerDegLat];
    const right = [bx - (halfW * px) / mPerDegLon, by - (halfW * py) / mPerDegLat];
    const tip = [lon2, lat2];
    return { type: 'Polygon', coordinates: [[tip, left, right, tip]] };
}

function ensureSectorPreviewLayers() {
    // Create sources/layers if missing
    try {
        if (!map.getSource(sectorPreview.lineSource)) {
            map.addSource(sectorPreview.lineSource, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
            map.addLayer({
                id: sectorPreview.lineLayer,
                type: 'line',
                source: sectorPreview.lineSource,
                paint: { 'line-color': '#1d6fb8', 'line-width': 2, 'line-dasharray': [2, 2] }
            });
        }
        if (!map.getSource(sectorPreview.rectSource)) {
            map.addSource(sectorPreview.rectSource, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
            map.addLayer({
                id: sectorPreview.rectFillLayer,
                type: 'fill',
                source: sectorPreview.rectSource,
                paint: { 'fill-color': '#1d6fb8', 'fill-opacity': 0.15 }
            });
            map.addLayer({
                id: sectorPreview.rectLineLayer,
                type: 'line',
                source: sectorPreview.rectSource,
                paint: { 'line-color': '#1d6fb8', 'line-width': 2 }
            });
        }
        if (!map.getSource(sectorPreview.arrowSource)) {
            map.addSource(sectorPreview.arrowSource, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
            map.addLayer({
                id: sectorPreview.arrowFillLayer,
                type: 'fill',
                source: sectorPreview.arrowSource,
                paint: { 'fill-color': '#1d6fb8', 'fill-opacity': 0.6 }
            });
        }
    } catch (err) { console.warn('ensureSectorPreviewLayers error', err); }
}

function updateSectorPreview(start, current) {
    if (!start || !current) return;
    // Trapezoid preview: center=start, direction to current defines bearing and radius
    const center = start;
    const end = current;
    const midLat = center[1];
    const mPerDegLat = 111320.0;
    const mPerDegLon = 111320.0 * Math.max(0.000001, Math.cos(midLat * Math.PI / 180));
    const vx = (end[0] - center[0]) * mPerDegLon;
    const vy = (end[1] - center[1]) * mPerDegLat;
    let radiusM = Math.hypot(vx, vy);
    // Minimal radius for visibility
    if (!isFinite(radiusM) || radiusM < 1) radiusM = 1;
    const bearingRad = Math.atan2(vx, vy); // from north, clockwise
    const bearingDeg = (bearingRad * 180 / Math.PI + 360) % 360;

    const line = { type: 'Feature', geometry: { type: 'LineString', coordinates: [center, end] }, properties: {} };
    const trapezoid = makeTrapezoidSector(center, radiusM, bearingDeg);
    const trapezoidFeature = { type: 'Feature', geometry: trapezoid, properties: {} };
    const tip = projectFrom(center, radiusM, bearingDeg);
    const arrowGeom = makeArrowTriangle(center, tip, 12, 8);
    const arrowFeatures = arrowGeom ? [{ type: 'Feature', geometry: arrowGeom, properties: {} }] : [];
    try {
        map.getSource(sectorPreview.lineSource).setData({ type: 'FeatureCollection', features: [line] });
        map.getSource(sectorPreview.rectSource).setData({ type: 'FeatureCollection', features: [trapezoidFeature] });
        map.getSource(sectorPreview.arrowSource).setData({ type: 'FeatureCollection', features: arrowFeatures });
    } catch (err) { /* ignore while layers are initializing */ }
}

function clearSectorPreview() {
    try {
        if (map.getSource(sectorPreview.lineSource)) map.getSource(sectorPreview.lineSource).setData({ type: 'FeatureCollection', features: [] });
        if (map.getSource(sectorPreview.rectSource)) map.getSource(sectorPreview.rectSource).setData({ type: 'FeatureCollection', features: [] });
        if (map.getSource(sectorPreview.arrowSource)) map.getSource(sectorPreview.arrowSource).setData({ type: 'FeatureCollection', features: [] });
    } catch (_) {}
}

function enterSectorDragMode() {
    // Deactivate polygon and pin modes
    polygonModeActive = false;
    pinModeActive = false;
    polygonControl && polygonControl.classList.remove('active');
    pinControl && pinControl.classList.remove('active');
    polygonControl && (polygonControl.title = 'Click to draw detection area');
    pinControl && (pinControl.title = 'Click to place radar location');
    try { draw.changeMode('simple_select'); } catch(_){}

    // Prepare preview layers and listeners
    ensureSectorPreviewLayers();
    sectorDragActive = false;
    sectorDragStart = null;
    try { map.dragPan.disable(); } catch(_){}
    try { map.getCanvas().style.cursor = 'crosshair'; } catch(_){}

    const onMouseDown = (e) => {
        sectorDragActive = true;
        sectorDragStart = [e.lngLat.lng, e.lngLat.lat];
        updateSectorPreview(sectorDragStart, sectorDragStart);
    };
    const onMouseMove = (e) => {
        if (!sectorDragActive || !sectorDragStart) return;
        updateSectorPreview(sectorDragStart, [e.lngLat.lng, e.lngLat.lat]);
    };
    const onFinalize = (e) => {
        if (!sectorDragActive || !sectorDragStart) return;
        let lngLat = e && e.lngLat;
        if (!lngLat && e && typeof e.clientX === 'number' && typeof e.clientY === 'number') {
            try {
                const rect = map.getCanvas().getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                if (x >= 0 && y >= 0 && x <= rect.width && y <= rect.height) {
                    const point = map.unproject([x, y]);
                    if (point) lngLat = point;
                }
            } catch (_) {}
        }
        if (!lngLat) {
            exitSectorDragMode();
            return;
        }
        const end = [lngLat.lng, lngLat.lat];
        // Final sector trapezoid: center = start, radius = |start-end|, bearing = start->end
        const midLat = sectorDragStart[1];
        const mPerDegLat = 111320.0;
        const mPerDegLon = 111320.0 * Math.max(0.000001, Math.cos(midLat * Math.PI / 180));
        const vx = (end[0] - sectorDragStart[0]) * mPerDegLon;
        const vy = (end[1] - sectorDragStart[1]) * mPerDegLat;
        let radiusM = Math.hypot(vx, vy);
        if (!isFinite(radiusM) || radiusM < 1) radiusM = Number(radarData.defaultRadiusM || 75);
        const bearingDeg = ((Math.atan2(vx, vy) * 180 / Math.PI) + 360) % 360;
        let trapezoid = makeTrapezoidSector(sectorDragStart, radiusM, bearingDeg);
        trapezoid = simplifyIfPossible(trapezoid, 1);
        updateSectorJsonWithGeometry(trapezoid);
        addPolygonToDraw(trapezoid);
        exitSectorDragMode();
    };

    // Store handlers to remove later
    sectorPreview._onMouseDown = onMouseDown;
    sectorPreview._onMouseMove = onMouseMove;
    sectorPreview._onMouseUp = onFinalize;
    sectorPreview._onMouseLeave = (e) => { if (sectorDragActive) onFinalize(e); };

    map.on('mousedown', onMouseDown);
    map.on('mousemove', onMouseMove);
    map.on('mouseup', onFinalize);
    map.on('mouseleave', sectorPreview._onMouseLeave);
    // Also capture mouseup outside the map canvas
    sectorPreview._onDocMouseUp = onFinalize;
    document.addEventListener('mouseup', sectorPreview._onDocMouseUp);
}

function exitSectorDragMode() {
    try { map.dragPan.enable(); } catch(_){}
    try { map.getCanvas().style.cursor = ''; } catch(_){}
    sectorDragActive = false;
    sectorDragStart = null;
    clearSectorPreview();
    sectorModeActive = false;
    sectorControl && sectorControl.classList.remove('active');
    sectorControl && (sectorControl.title = 'Click and drag to set sector direction');
    try { map.off('mousedown', sectorPreview._onMouseDown); } catch(_){}
    try { map.off('mousemove', sectorPreview._onMouseMove); } catch(_){}
    try { map.off('mouseup', sectorPreview._onMouseUp); } catch(_){}
    try { map.off('mouseleave', sectorPreview._onMouseLeave); } catch(_){}
    try { document.removeEventListener('mouseup', sectorPreview._onDocMouseUp); } catch(_){}
}

function simplifyIfPossible(geometry, toleranceMeters = 5) {
    try {
        if (typeof turf !== 'undefined' && turf && typeof turf.simplify === 'function') {
            const centerLat = getRadarCenterFromFormOrMarker()?.[1] || 0;
            const degTol = metersToDegrees(centerLat, toleranceMeters)[1];
            const simplified = turf.simplify({ type: 'Feature', geometry }, { tolerance: degTol, highQuality: true });
            return simplified.geometry;
        }
    } catch (e) {
        console.warn('Simplify failed, using original geometry', e);
    }
    return geometry;
}

function updateSectorJsonWithGeometry(geometry) {
    if (!radarData.hasGIS) {
        const el = document.getElementById(radarData.sectorJsonId);
        if (el) el.value = JSON.stringify(geometry);
    }
}

function addPolygonToDraw(geometry) {
    try {
        draw.deleteAll();
        const feature = { type: 'Feature', geometry, properties: {} };
        draw.add(feature);
        currentPolygon = feature;
        updatePolygon();
    } catch (e) {
        console.warn('Failed to add polygon to draw. Falling back.', e);
    }
}

function onCreateCircleFromPin() {
    try {
        const center = getRadarCenterFromFormOrMarker();
        if (!center) {
            alert('Place the radar pin first to set center.');
            return;
        }
        let radius = parseFloat(prompt('Circle radius in meters:', String(radarData.defaultRadiusM || 75)));
        if (!Number.isFinite(radius) || radius <= 0) return;
        let geom;
        if (typeof turf !== 'undefined' && turf && typeof turf.circle === 'function') {
            const circle = turf.circle(center, radius, { steps: 64, units: 'meters' });
            geom = circle.geometry;
        } else {
            geom = makeCircleGeometryApprox(center, radius, 64);
        }
        geom = simplifyIfPossible(geom, 5);
        updateSectorJsonWithGeometry(geom);
        addPolygonToDraw(geom);
    } catch (e) {
        console.error('Circle tool unavailable, falling back to manual polygon.', e);
        alert('Circle tool unavailable. Use manual polygon.');
    }
}

function onCreateSectorFromPin() {
    try {
        const center = getRadarCenterFromFormOrMarker();
        if (!center) {
            alert('Place the radar pin first to set center.');
            return;
        }
        const defRadius = radarData.defaultRadiusM || 75;
        const radius = parseFloat(prompt('Sector radius in meters:', String(defRadius)));
        if (!Number.isFinite(radius) || radius <= 0) return;
        const bearing = parseFloat(prompt('Sector direction (degrees, 0=N, 90=E):', '0'));
        if (!Number.isFinite(bearing)) return;

        let geom = makeTrapezoidSector(center, radius, bearing);
        geom = simplifyIfPossible(geom, 5);
        updateSectorJsonWithGeometry(geom);
        addPolygonToDraw(geom);
    } catch (e) {
        console.error('Sector tool unavailable, falling back to manual polygon.', e);
        alert('Sector tool unavailable. Use manual polygon.');
    }
}
function createSearchResultsDiv() {
    if (!searchResultsDiv) {
        searchResultsDiv = document.createElement('div');
        searchResultsDiv.id = 'search-results';
        
        const searchContainer = document.getElementById('location-search').parentNode;
        searchContainer.style.position = 'relative';
        searchContainer.appendChild(searchResultsDiv);
    }
    return searchResultsDiv;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

async function searchLocation(e) {
    const query = e.target.value.trim();
    const resultsDiv = createSearchResultsDiv();
    
    // Accept direct lat,lon input
    const coord = parseCoordString(query);
    if (coord) {
        // Set radar pin directly and normalize the field text
        placeRadarPin(coord.lon, coord.lat);
        e.target.value = `${coord.lat.toFixed(6)}, ${coord.lon.toFixed(6)}`;
        resultsDiv.style.display = 'none';
        return;
    }

    if (query.length < 3) {
        resultsDiv.style.display = 'none';
        return;
    }
    
    try {
        // Using Nominatim for geocoding with Uzbekistan priority
        const searchQuery = `${query}, Uzbekistan`;
        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?` +
            `format=json&q=${encodeURIComponent(searchQuery)}&limit=5&` +
            `countrycodes=uz&addressdetails=1`
        );
        
        if (!response.ok) {
            throw new Error('Search service unavailable');
        }
        
        const results = await response.json();
        
        if (results.length > 0) {
            displaySearchResults(results, resultsDiv);
        } else {
            // Try broader search if no results for Uzbekistan
            const broadResponse = await fetch(
                `https://nominatim.openstreetmap.org/search?` +
                `format=json&q=${encodeURIComponent(query)}&limit=5&addressdetails=1`
            );
            const broadResults = await broadResponse.json();
            displaySearchResults(broadResults, resultsDiv);
        }
    } catch (error) {
        console.error('Search error:', error);
        resultsDiv.innerHTML = `<div style="padding: 10px; color: #dc3545;">Search temporarily unavailable</div>`;
        resultsDiv.style.display = 'block';
    }
}

function displaySearchResults(results, resultsDiv) {
    if (results.length === 0) {
        resultsDiv.innerHTML = `<div style="padding: 10px; color: #666;">No results found</div>`;
        resultsDiv.style.display = 'block';
        return;
    }
    
    resultsDiv.innerHTML = '';
    resultsDiv.style.display = 'block';
    
    results.forEach((result) => {
        const item = document.createElement('div');
        item.innerHTML = `
            <div style="font-weight: bold;">${result.display_name.split(',')[0]}</div>
            <div style="font-size: 12px; color: #666;">${result.display_name}</div>
        `;
        
        item.addEventListener('click', () => {
            const lat = parseFloat(result.lat);
            const lon = parseFloat(result.lon);
            
            // Update search input
            document.getElementById('location-search').value = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
            
            // Hide results
            resultsDiv.style.display = 'none';
            
            // Place radar pin at selected search location
            placeRadarPin(lon, lat);
        });
        
        resultsDiv.appendChild(item);
    });
}

function addSearchMarker(lon, lat, name) {
    // Remove existing search marker
    if (searchMarker) {
        searchMarker.remove();
    }
    
    // Create marker element
    const markerElement = document.createElement('div');
    markerElement.style.cssText = `
        background: #dc3545;
        border: 2px solid white;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    `;
    
    // Add marker to map
    searchMarker = new maplibregl.Marker(markerElement)
        .setLngLat([lon, lat])
        .setPopup(new maplibregl.Popup().setHTML(`<div style="font-weight: bold;">${name}</div>`))
        .addTo(map);
}
// Form validation
function validateRadarForm(e) {
    if (!radarData.hasGIS) {
        const sectorData = document.getElementById(radarData.sectorJsonId).value;
        const centerLat = document.getElementById(radarData.centerLatId).value;
        const centerLon = document.getElementById(radarData.centerLonId).value;
        
        if (!sectorData) {
            e.preventDefault();
            alert('Please draw a detection area polygon on the map.');
            return false;
        }
        
        if (!centerLat || !centerLon) {
            e.preventDefault();
            alert('Please place a radar pin on the map to mark the radar location.');
            return false;
        }
    }
}

// Initialize search functionality and map when page loads
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('location-search');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(searchLocation, 300));
        // Accept coordinates on Enter/blur too
        searchInput.addEventListener('keydown', function(ev) {
            if (ev.key === 'Enter') {
                const c = parseCoordString(searchInput.value.trim());
                if (c) {
                    placeRadarPin(c.lon, c.lat);
                    searchInput.value = `${c.lat.toFixed(6)}, ${c.lon.toFixed(6)}`;
                }
            }
        });
        searchInput.addEventListener('blur', function() {
            const c = parseCoordString(searchInput.value.trim());
            if (c) {
                placeRadarPin(c.lon, c.lat);
                searchInput.value = `${c.lat.toFixed(6)}, ${c.lon.toFixed(6)}`;
            }
        });
        
        // Hide results when clicking outside
        document.addEventListener('click', function(e) {
            const resultsDiv = document.getElementById('search-results');
            if (resultsDiv && !searchInput.contains(e.target) && !resultsDiv.contains(e.target)) {
                resultsDiv.style.display = 'none';
            }
        });
    }

    // Initialize map after DOM ready
    initMap();
    
    // Add form validation
    const form = document.getElementById('radar-form');
    if (form) {
        form.addEventListener('submit', validateRadarForm);
    }
});
