-- Initialize PostGIS extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Create indexes for spatial queries
-- These will be added after Django creates the tables