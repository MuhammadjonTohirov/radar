from django import forms
from django.conf import settings
from radars.models import Radar, RadarCategory
import json
import math


class RadarForm(forms.ModelForm):
    class Meta:
        model = Radar
        if getattr(settings, 'HAS_GIS', False):
            fields = ['category', 'sector', 'speed_limit', 'notes']
        else:
            fields = ['category', 'sector_json', 'center_lat', 'center_lon', 'speed_limit', 'notes']
        
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'speed_limit': forms.NumberInput(attrs={'class': 'form-control', 'min': '10', 'max': '200'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        
        # Add non-GIS specific widgets
        if not getattr(settings, 'HAS_GIS', False):
            widgets.update({
                'sector_json': forms.HiddenInput(),
                'center_lat': forms.HiddenInput(),
                'center_lon': forms.HiddenInput(),
            })
    
    def clean_sector_json(self):
        """Validate JSON structure for non-GIS mode"""
        if not getattr(settings, 'HAS_GIS', False):
            sector_json = self.cleaned_data.get('sector_json')
            if sector_json:
                try:
                    # Parse and validate GeoJSON structure
                    geom = json.loads(sector_json) if isinstance(sector_json, str) else sector_json
                    if not isinstance(geom, dict) or geom.get('type') != 'Polygon':
                        raise forms.ValidationError('Invalid polygon geometry.')
                    
                    coordinates = geom.get('coordinates')
                    if not coordinates or not isinstance(coordinates, list) or len(coordinates) == 0:
                        raise forms.ValidationError('Polygon must have coordinates.')
                    
                    # Validate minimum 3 points for polygon (4 including closing point)
                    if len(coordinates[0]) < 4:
                        raise forms.ValidationError('Polygon must have at least 3 points.')
                        
                except (json.JSONDecodeError, KeyError, TypeError):
                    raise forms.ValidationError('Invalid polygon geometry format.')
                    
                return json.dumps(geom) if not isinstance(sector_json, str) else sector_json
        return None
    
    def clean_center_lat(self):
        """Validate latitude range"""
        if not getattr(settings, 'HAS_GIS', False):
            center_lat = self.cleaned_data.get('center_lat')
            if center_lat is not None:
                if center_lat < -90 or center_lat > 90:
                    raise forms.ValidationError('Latitude must be between -90 and 90.')
            return center_lat
        return None
    
    def clean_center_lon(self):
        """Validate longitude range"""
        if not getattr(settings, 'HAS_GIS', False):
            center_lon = self.cleaned_data.get('center_lon')
            if center_lon is not None:
                if center_lon < -180 or center_lon > 180:
                    raise forms.ValidationError('Longitude must be between -180 and 180.')
            return center_lon
        return None
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure polygon data is provided for non-GIS mode
        if not getattr(settings, 'HAS_GIS', False):
            sector_json = cleaned_data.get('sector_json')
            center_lat = cleaned_data.get('center_lat')
            center_lon = cleaned_data.get('center_lon')
            
            if not sector_json:
                # Optional server-side fallback: generate default circle polygon around pin
                if getattr(settings, 'RADAR_ALLOW_DEFAULT_CIRCLE', False) and center_lat is not None and center_lon is not None:
                    try:
                        radius_m = int(getattr(settings, 'RADAR_DEFAULT_RADIUS_M', 75))
                        # approximate meters->degrees conversion at given latitude
                        deg_lat = radius_m / 111320.0
                        cos_lat = math.cos((center_lat or 0) * math.pi / 180.0) or 1e-6
                        deg_lon = radius_m / (111320.0 * cos_lat)
                        steps = 64
                        ring = []
                        for i in range(steps):
                            theta = (i / steps) * 2.0 * math.pi
                            x = center_lon + deg_lon * math.cos(theta)
                            y = center_lat + deg_lat * math.sin(theta)
                            ring.append([x, y])
                        if ring:
                            ring.append(ring[0])
                        geom = {"type": "Polygon", "coordinates": [ring]}
                        cleaned_data['sector_json'] = json.dumps(geom)
                    except Exception:
                        # If fallback fails, keep original validation behavior
                        raise forms.ValidationError('Please draw a detection area polygon on the map.')
                else:
                    raise forms.ValidationError('Please draw a detection area polygon on the map.')
            
            if center_lat is None or center_lon is None:
                raise forms.ValidationError('Center coordinates are required.')
        
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit category choices to active ones, ordered
        try:
            self.fields['category'].queryset = RadarCategory.objects.filter(is_active=True).order_by('order', 'name')
        except Exception:
            pass
