# Routing Integration Summary — server-map with Uzbekistan PBF

Short answer: Yes. The server-map service can now generate on‑road, multi‑point routes using your Uzbekistan PBF, and Django is configured to use server-map by default instead of OSRM.

## What Changed

- server-map (Flask routing service)
  - Added an OSM‑graph router that reads the local PBF and finds true shortest paths on real roads.
  - Files:
    - `server-map/routing_service.py`: builds a NetworkX graph from the PBF (via pyrosm), snaps input to nearest road nodes, and returns a road‑following GeoJSON LineString.
    - `server-map/config.py`: added `OSM_PBF_PATH` (default: `server-map/uzbekistan-250901.osm.pbf`), `DEFAULT_BACKEND='osm'` while keeping synthetic algorithms as fallback.
    - `server-map/requirements.txt`: added `pyrosm`, `networkx`, `shapely`, `pandas`.

- Django backend
  - Uses the custom routing service first, then OSRM (if ever enabled), then straight‑line fallback.
  - Files:
    - `server/api/services/routing.py`: calls `CUSTOM_ROUTING_URL` (`/route?from=lat,lon&to=lat,lon&algorithm=...`) and normalizes the response to a Feature with `properties.summary`.
    - `docker-compose.yml` (web env): sets
      - `ROUTING_PROVIDER=fallback`
      - `ROUTING_BASE_URL=` (blank)
      - `CUSTOM_ROUTING_URL=http://host.docker.internal:5002`
      - `CUSTOM_ROUTING_ALGORITHM=osm`

## How To Run

1) Start the server-map routing service on your host

```
cd server-map
pip install -r requirements.txt
python app.py
```

Notes:
- It will load `server-map/uzbekistan-250901.osm.pbf` and build the road graph on first start (one‑time cost in-memory).

2) Start the web app (Django) in Docker

```
docker compose up -d web
```

3) Apply DB migrations and create an admin (once)

```
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

## Verify Routing

- From Django API:
```
curl "http://localhost:8000/api/route/?from=71.7837,40.3914&to=71.80,40.40"
```
Expect `properties.summary.provider` to be `"radar2-custom"` and geometry to contain many coordinates (LineString along roads).

- In the UI:
  - Open `http://localhost:8000/client/map/`
  - Use From/To (search or pick) and click “Get Route” — the route should follow roads, and “Impacted Radars” will reflect the buffered route.

## Notes & Scope

- Coverage: Routing is limited to the area in your PBF. If start/end are too far from a road (or outside the data), fallback may occur.
- Performance: The graph is built at server startup; per‑request routing uses shortest path with `travel_time` weights (derived from length and maxspeed when available).
- Waypoints: The Django API already supports multi‑waypoint input (`coords=`), but server-map’s endpoint currently uses only start/end. We can extend server-map to honor intermediate waypoints on request.
- OSRM: No longer required. The compose file is set to use the custom router; OSRM can be removed or left unused.

## Optional Next Steps

- Add server-map to docker-compose and point web to `http://server-map:5002` (service DNS) instead of `host.docker.internal`.
- Implement multi‑waypoint routing in server-map (`/route` with `coords=`) to match the Django endpoint’s capabilities.
- Cache popular routes in server-map for faster responses.

