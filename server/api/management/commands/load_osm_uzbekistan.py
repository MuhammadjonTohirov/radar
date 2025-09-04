import os
import shlex
import subprocess
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Load Uzbekistan OSM PBF into PostgreSQL (PostGIS + pgRouting) using osm2pgrouting."

    def add_arguments(self, parser):
        parser.add_argument('--pbf', default='server-map/uzbekistan-250901.osm.pbf', help='Path to Uzbekistan .osm.pbf file')
        parser.add_argument('--schema', default=None, help='Target schema (default from settings.ROUTING_PG_SCHEMA)')
        parser.add_argument('--clean', action='store_true', help='Drop and recreate schema before import')
        parser.add_argument('--conn', default=None, help='psql connection string (overrides Django DB settings)')

    def handle(self, *args, **options):
        pbf_path = options['pbf']
        if not os.path.exists(pbf_path):
            raise CommandError(f"PBF not found: {pbf_path}")

        db = settings.DATABASES['default']
        if options['conn']:
            conn_str = options['conn']
        else:
            if not db.get('ENGINE', '').endswith('postgresql') and 'postgis' not in db.get('ENGINE', ''):
                raise CommandError('Default database is not PostgreSQL/PostGIS')
            conn_parts = []
            if db.get('HOST'): conn_parts.append(f"-h {shlex.quote(db['HOST'])}")
            if db.get('PORT'): conn_parts.append(f"-p {shlex.quote(str(db['PORT']))}")
            if db.get('USER'): conn_parts.append(f"-U {shlex.quote(db['USER'])}")
            conn_parts.append(shlex.quote(db['NAME']))
            conn_str = ' '.join(conn_parts)

        schema = options['schema'] or getattr(settings, 'ROUTING_PG_SCHEMA', 'public')

        # Ensure extensions
        self.stdout.write(self.style.NOTICE('Ensuring extensions postgis, pgrouting...'))
        psql_cmd = f"psql {conn_str} -c \"CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS pgrouting;\""
        self._run(psql_cmd, env=self._env_with_password(db))

        if options['clean'] and schema != 'public':
            self.stdout.write(self.style.WARNING(f'Dropping and recreating schema {schema}'))
            self._run(f"psql {conn_str} -c \"DROP SCHEMA IF EXISTS {schema} CASCADE; CREATE SCHEMA {schema};\"", env=self._env_with_password(db))

        # Run osm2pgrouting import
        self.stdout.write(self.style.NOTICE('Importing OSM with osm2pgrouting (this may take a while)...'))
        imp_cmd = (
            f"osm2pgrouting --file {shlex.quote(pbf_path)} "
            f"--dbname {shlex.quote(db['NAME'])} "
            f"--username {shlex.quote(db.get('USER') or '')} "
            f"--host {shlex.quote(db.get('HOST') or 'localhost')} "
            f"--port {shlex.quote(str(db.get('PORT') or '5432'))} "
            f"--schema {shlex.quote(schema)} --clean --chunk 2000 --conf /usr/share/osm2pgrouting/mapconfig_for_cars.xml"
        )
        self._run(imp_cmd, env=self._env_with_password(db))

        self.stdout.write(self.style.SUCCESS('OSM import complete. Verifying tables...'))
        verify_sql = f"""
            SELECT to_regclass('{schema}.ways') AS ways,
                   to_regclass('{schema}.ways_vertices_pgr') AS vertices;
        """
        self._run(f"psql {conn_str} -c \"{verify_sql}\"", env=self._env_with_password(db))
        self.stdout.write(self.style.SUCCESS('Done. pgRouting is ready for routing.'))

    def _run(self, cmd: str, env=None):
        self.stdout.write(self.style.HTTP_INFO(f"$ {cmd}"))
        try:
            subprocess.check_call(cmd, shell=True, env=env)
        except subprocess.CalledProcessError as e:
            raise CommandError(f"Command failed ({e.returncode}): {cmd}")

    def _env_with_password(self, db):
        env = os.environ.copy()
        if db.get('PASSWORD'):
            env['PGPASSWORD'] = db['PASSWORD']
        return env

