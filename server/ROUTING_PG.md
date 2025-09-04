# PostgreSQL Routing (pgRouting + OSM)

This app can generate on-road routes using your local PostgreSQL database with PostGIS and pgRouting, backed by the Uzbekistan OSM extract in `server-map/uzbekistan-250901.osm.pbf`.

## Prerequisites
- PostgreSQL 14+ with PostGIS and pgRouting extensions.
- `osm2pgrouting` installed (package provided by most distros/brews).

## Configure Django
Set these env vars (e.g., in `server/.env` or shell):

- `DATABASE_URL=postgres://...` or `DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT`
- `ROUTING_USE_PGROUTING=true`
- `ROUTING_PG_SCHEMA=public` (or custom schema)
- `ROUTING_SNAP_TOLERANCE_M=2000` (snap radius)

## Load OSM into PostGIS
Run the management command (uses `osm2pgrouting`):

```
python server/manage.py load_osm_uzbekistan --pbf server-map/uzbekistan-250901.osm.pbf --schema public
```

This creates `ways` and `ways_vertices_pgr` and enables `postgis` and `pgrouting` extensions.

## Generate Routes
Use the Django API:

```
GET /api/route?from=69.2401,41.2995&to=69.2047,41.3111
```

- Input format: `lon,lat` (WGS84).
- Response: GeoJSON LineString following real roads from OSM.

Notes:
- No Docker required; connects directly to your local PostgreSQL.
- If pgRouting isn’t available, the API falls back to other providers or a straight line.

