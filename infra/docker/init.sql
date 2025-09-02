-- PostgreSQL initialization script for Radar2 application
-- This script runs when the database container is first created

-- Connect to radar_db
\c radar_db;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE radar_db TO radar_user;
GRANT ALL ON SCHEMA public TO radar_user;

-- Set timezone
SET timezone = 'UTC';

-- Basic database configuration for Django
ALTER DATABASE radar_db SET default_transaction_isolation TO 'read committed';
ALTER DATABASE radar_db SET client_encoding TO 'utf8';
ALTER DATABASE radar_db SET timezone TO 'UTC';

-- Log initialization completion
SELECT 'PostgreSQL database initialized successfully for Radar2 application' AS status;