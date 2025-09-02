// Radar form map interaction JavaScript
let map;
let draw;
let currentPolygon = null;
let radarMarker = null;
// Location search functionality with dropdown
let searchResultsDiv = null;
let searchMarker = null;

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

        // Control state variables
        let pinModeActive = false;
        let polygonModeActive = false;

        // Add radar location pin control
        const pinControl = document.createElement('div');
        pinControl.className = 'radar-pin-control';
        pinControl.title = 'Click to place radar location';

        // Add polygon drawing control
        const polygonControl = document.createElement('div');
        polygonControl.className = 'radar-polygon-control';
        polygonControl.title = 'Click to draw detection area';

        // Add trash/clear control
        const trashControl = document.createElement('div');
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

        // Add controls to map container
        const mapContainer = document.getElementById('map');
        if (mapContainer) {
            mapContainer.appendChild(pinControl);
            mapContainer.appendChild(polygonControl);
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
            updatePolygon();
            // Exit polygon drawing mode after creating a polygon - don't call changeMode to avoid recursion
            polygonModeActive = false;
            polygonControl.classList.remove('active');
            polygonControl.title = 'Click to draw detection area';
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
            document.getElementById('location-search').value = result.display_name.split(',')[0];
            
            // Hide results
            resultsDiv.style.display = 'none';
            
            // Fly to location
            map.flyTo({
                center: [lon, lat],
                zoom: 15,
                duration: 2000
            });
            
            // Add a marker for the searched location
            addSearchMarker(lon, lat, result.display_name.split(',')[0]);
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
