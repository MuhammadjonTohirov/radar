from django import forms
from django.conf import settings
from radars.models import Radar
import json


class RadarForm(forms.ModelForm):
    class Meta:
        model = Radar
        if getattr(settings, 'HAS_GIS', False):
            fields = ['type', 'sector', 'speed_limit', 'direction', 'notes']
        else:
            fields = ['type', 'sector_json', 'center_lat', 'center_lon', 'speed_limit', 'direction', 'notes']
        
        widgets = {
            'type': forms.Select(attrs={'class': 'form-control'}),
            'speed_limit': forms.NumberInput(attrs={'class': 'form-control', 'min': '10', 'max': '200'}),
            'direction': forms.Select(attrs={'class': 'form-control'}),
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
                raise forms.ValidationError('Please draw a detection area polygon on the map.')
            
            if center_lat is None or center_lon is None:
                raise forms.ValidationError('Center coordinates are required.')
        
        return cleaned_data