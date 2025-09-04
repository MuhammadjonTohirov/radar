#!/usr/bin/env python3
"""
OSM to PostgreSQL loader for pgRouting (no Docker).

Imports the Uzbekistan PBF into a local PostgreSQL database using osm2pgrouting.
Uses configuration from config.py by default.

Usage:
  python pg_loader.py [--setup-db] [--load-osm] [--verify]
  
  or with custom parameters:
  python pg_loader.py --pbf uzbekistan-250901.osm.pbf \
      --host localhost --port 5432 --db radar_db --user radar_user \
      --password radar_pass_dev --schema public --clean
"""

import argparse
import os
import shlex
import subprocess
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Try to import config, fall back to defaults
try:
    import config
    DEFAULT_PBF = config.OSM_PBF_PATH
    DEFAULT_HOST = config.PG_HOST
    DEFAULT_PORT = str(config.PG_PORT)
    DEFAULT_DB = config.PG_DB
    DEFAULT_USER = config.PG_USER
    DEFAULT_PASSWORD = config.PG_PASSWORD
    DEFAULT_SCHEMA = config.PG_SCHEMA
except ImportError:
    print("Warning: config.py not found, using defaults")
    DEFAULT_PBF = 'uzbekistan-250901.osm.pbf'
    DEFAULT_HOST = 'localhost'
    DEFAULT_PORT = '5432'
    DEFAULT_DB = 'radar_db'
    DEFAULT_USER = 'radar_user'
    DEFAULT_PASSWORD = 'radar_pass_dev'
    DEFAULT_SCHEMA = 'public'


def check_prerequisites(pbf_file):
    """Check if required tools and files are available"""
    print("🔍 Checking prerequisites...")
    
    # Check osm2pgrouting
    try:
        result = subprocess.run(['osm2pgrouting', '--help'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("❌ osm2pgrouting not found. Install with:")
            print("   Ubuntu/Debian: apt install osm2pgrouting")
            print("   macOS: brew install osm2pgrouting")
            return False
        print("✅ osm2pgrouting found")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("❌ osm2pgrouting not found. Install with:")
        print("   Ubuntu/Debian: apt install osm2pgrouting")
        print("   macOS: brew install osm2pgrouting")
        return False
    
    # Check OSM file
    if not os.path.exists(pbf_file):
        print(f"❌ OSM file not found: {pbf_file}")
        print("Please download Uzbekistan OSM extract and place it at the specified path")
        return False
    
    file_size = os.path.getsize(pbf_file) / (1024 * 1024)  # MB
    print(f"✅ OSM file found: {pbf_file} ({file_size:.1f} MB)")
    
    return True


def setup_database(host, port, user, password, db_name):
    """Create database and enable required extensions"""
    print(f"🗄️  Setting up database '{db_name}'...")
    
    # Connect to PostgreSQL server (not specific database)
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname='postgres'  # Default database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Create database if it doesn't exist
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")
        if not cur.fetchone():
            print(f"Creating database '{db_name}'...")
            cur.execute(f'CREATE DATABASE "{db_name}"')
        else:
            print(f"Database '{db_name}' already exists")
            
        cur.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        return False
    
    # Connect to the target database and enable extensions
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=db_name
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Enable PostGIS extension
        print("Enabling PostGIS extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        
        # Enable pgRouting extension
        print("Enabling pgRouting extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgrouting")
        
        # Check extensions
        cur.execute("""
            SELECT extname FROM pg_extension 
            WHERE extname IN ('postgis', 'pgrouting')
        """)
        extensions = [row[0] for row in cur.fetchall()]
        
        if 'postgis' in extensions and 'pgrouting' in extensions:
            print("✅ Extensions enabled successfully")
        else:
            print(f"❌ Missing extensions. Found: {extensions}")
            return False
            
        cur.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Failed to setup database: {e}")
        return False


def verify_setup(host, port, user, password, db_name, schema):
    """Verify that the setup was successful"""
    print("🔍 Verifying setup...")
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=db_name
        )
        cur = conn.cursor()
        
        # Check required tables
        tables_to_check = ['ways', 'ways_vertices_pgr']
        for table in tables_to_check:
            cur.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema='{schema}' AND table_name='{table}'
            """)
            if cur.fetchone()[0] == 0:
                print(f"❌ Table {schema}.{table} not found")
                return False
            
            # Check row count
            cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
            count = cur.fetchone()[0]
            print(f"✅ Table {schema}.{table}: {count:,} rows")
        
        # Test pgRouting functions
        cur.execute("SELECT COUNT(*) FROM pg_proc WHERE proname = 'pgr_dijkstra'")
        if cur.fetchone()[0] > 0:
            print("✅ pgRouting functions available")
        else:
            print("❌ pgRouting functions not found")
            return False
        
        cur.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Verification failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Load OSM PBF into PostgreSQL for pgRouting')
    
    # Action flags
    parser.add_argument('--setup-db', action='store_true', help='Setup database and extensions')
    parser.add_argument('--load-osm', action='store_true', help='Load OSM data using osm2pgrouting')
    parser.add_argument('--verify', action='store_true', help='Verify setup')
    parser.add_argument('--all', action='store_true', help='Run complete setup (db + osm + verify)')
    
    # Connection parameters (with config.py defaults)
    parser.add_argument('--pbf', default=DEFAULT_PBF, help=f'OSM PBF file path (default: {DEFAULT_PBF})')
    parser.add_argument('--host', default=DEFAULT_HOST, help=f'PostgreSQL host (default: {DEFAULT_HOST})')
    parser.add_argument('--port', default=DEFAULT_PORT, help=f'PostgreSQL port (default: {DEFAULT_PORT})')
    parser.add_argument('--db', default=DEFAULT_DB, help=f'Database name (default: {DEFAULT_DB})')
    parser.add_argument('--user', default=DEFAULT_USER, help=f'Database user (default: {DEFAULT_USER})')
    parser.add_argument('--password', default=DEFAULT_PASSWORD, help='Database password')
    parser.add_argument('--schema', default=DEFAULT_SCHEMA, help=f'Schema name (default: {DEFAULT_SCHEMA})')
    parser.add_argument('--clean', action='store_true', help='Clean existing data before import')
    
    args = parser.parse_args()
    
    # If no action specified, show help
    if not any([args.setup_db, args.load_osm, args.verify, args.all]):
        parser.print_help()
        print("\nExample usage:")
        print("  python pg_loader.py --all                # Complete setup using config.py")
        print("  python pg_loader.py --setup-db --load-osm # Setup and load data")
        print("  python pg_loader.py --verify              # Verify existing setup")
        return
    
    print("🚀 Radar2 PostgreSQL Setup")
    print(f"Database: {args.host}:{args.port}/{args.db}")
    print(f"Schema: {args.schema}")
    print(f"OSM file: {args.pbf}")
    print("-" * 50)
    
    success = True
    
    # Check prerequisites
    if args.load_osm or args.all:
        if not check_prerequisites(args.pbf):
            sys.exit(1)
    
    # Setup database
    if args.setup_db or args.all:
        if not setup_database(args.host, args.port, args.user, args.password, args.db):
            success = False
    
    # Load OSM data
    if args.load_osm or args.all:
        if success:
            env = os.environ.copy()
            if args.password:
                env['PGPASSWORD'] = args.password

            conn_str = f"-h {shlex.quote(args.host)} -p {shlex.quote(args.port)} -U {shlex.quote(args.user)} {shlex.quote(args.db)}"

            def run_cmd(cmd: str):
                print(f"$ {cmd}")
                try:
                    subprocess.check_call(cmd, shell=True, env=env)
                    return True
                except subprocess.CalledProcessError as e:
                    print(f"❌ Command failed with exit code {e.returncode}")
                    return False

            print("📥 Loading OSM data with osm2pgrouting...")
            
            # Clean schema if requested
            if args.clean and args.schema != 'public':
                clean_cmd = f'psql {conn_str} -c "DROP SCHEMA IF EXISTS \\"{args.schema}\\" CASCADE; CREATE SCHEMA \\"{args.schema}\\""'
                if not run_cmd(clean_cmd):
                    success = False

            if success:
                # Import using osm2pgrouting
                osm2pg_cmd = (
                    f"osm2pgrouting --file {shlex.quote(args.pbf)} "
                    f"--dbname {shlex.quote(args.db)} --username {shlex.quote(args.user)} "
                    f"--host {shlex.quote(args.host)} --port {shlex.quote(args.port)} "
                    f"--schema {shlex.quote(args.schema)} --clean --chunk 2000"
                )
                
                # Try to find mapconfig file
                config_paths = [
                    '/usr/share/osm2pgrouting/mapconfig_for_cars.xml',
                    '/opt/homebrew/share/osm2pgrouting/mapconfig_for_cars.xml',
                    'mapconfig_for_cars.xml'
                ]
                
                config_file = None
                for path in config_paths:
                    if os.path.exists(path):
                        config_file = path
                        break
                
                if config_file:
                    osm2pg_cmd += f" --conf {shlex.quote(config_file)}"
                    print(f"Using config file: {config_file}")
                else:
                    print("Warning: mapconfig_for_cars.xml not found, using defaults")
                
                if not run_cmd(osm2pg_cmd):
                    success = False

    # Verify setup
    if args.verify or args.all:
        if success:
            if not verify_setup(args.host, args.port, args.user, args.password, args.db, args.schema):
                success = False
    
    # Final status
    if success:
        print("\n🎉 Setup completed successfully!")
        print("\nNext steps:")
        print("1. Start the routing service:")
        print("   cd server-map && python -m flask --app routing_service run --host=0.0.0.0 --port=5002")
        print("2. Test routing:")
        uzbek_coords = "start_lat=41.2995&start_lon=69.2401&end_lat=41.3158&end_lon=69.2785"
        print(f"   curl 'http://localhost:5002/route?{uzbek_coords}&algorithm=pg'")
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)


if __name__ == '__main__':
    main()

