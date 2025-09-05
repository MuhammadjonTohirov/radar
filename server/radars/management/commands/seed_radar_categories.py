from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files import File

from radars.models import RadarCategory


class Command(BaseCommand):
    help = "Seed default radar categories with icons and colors from resources/"

    def add_arguments(self, parser):
        parser.add_argument('--reset-icons', action='store_true', help='Replace existing icons if present')

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)  # points to server/
        resources_dir = base_dir.parent / 'resources'
        if not resources_dir.exists():
            self.stderr.write(self.style.ERROR(f"Resources directory not found: {resources_dir}"))
            return

        green = '#2ECC71'
        yellow = '#F1C40F'
        gray = '#95A5A6'

        # Define categories to seed
        items = [
            # Stationary hazards
            dict(code='speed_control', name='Speed control camera', groups=['stationary'], color=green, icon='icon_speed_control.png', order=10),
            dict(code='control_camera', name='Control camera', groups=['stationary'], color=green, icon='icon_control_camera.png', order=20),
            dict(code='red_light_control', name='Red light control camera', groups=['stationary'], color=yellow, icon='icon_red_light_control.png', order=30),
            dict(code='traffic_post_camera', name='Traffic post camera', groups=['stationary'], color=green, icon='icon_traffic_post_camera.png', order=40),
            dict(code='variety_speed_camera', name='Variety speed camera', groups=['stationary'], color=green, icon='icon_variety_speed_cam.png', order=50),
            dict(code='parking_control', name='Parking control', groups=['stationary'], color=green, icon='icon_parking_control.png', order=60),
            dict(code='average_speed_check', name='Average speed check camera', groups=['stationary'], color=gray, icon='icon_avg_speed_check.png', order=70),
            # Safe cameras
            dict(code='dummy_camera', name='Dummy camera', groups=['safe'], color=yellow, icon='icon_dummy_cam.png', order=80),
            dict(code='video_control_camera', name='Video control camera', groups=['safe'], color=yellow, icon='icon_video_control.png', order=90),
            # Default fallback
            dict(code='default_camera', name='Default camera', groups=['other'], color=green, icon='icon_default_camera.png', order=100),
        ]

        reset_icons = options.get('reset-icons', False)
        created = 0
        updated = 0

        for it in items:
            code = it['code']
            defaults = {
                'name': it['name'],
                'groups': it.get('groups') or [],
                'color': it['color'],
                'order': it.get('order', 0),
                'is_active': True,
            }
            obj, was_created = RadarCategory.objects.update_or_create(
                code=code,
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

            # Assign icon from resources
            icon_filename = it.get('icon')
            if icon_filename:
                src = resources_dir / icon_filename
                if src.exists():
                    should_set = reset_icons or not bool(obj.icon)
                    if should_set:
                        # Delete old icon file reference (if any) without removing file from storage
                        try:
                            if obj.icon:
                                obj.icon.delete(save=False)
                        except Exception:
                            pass
                        with open(src, 'rb') as fh:
                            obj.icon.save(icon_filename, File(fh), save=False)
                        obj.save(update_fields=['icon'])
                else:
                    self.stderr.write(self.style.WARNING(f"Icon not found for {code}: {src}"))

        self.stdout.write(self.style.SUCCESS(f"Seed complete. Created: {created}, Updated: {updated}"))
