from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status


class RouteApiTests(APITestCase):
    def test_route_requires_params(self):
        url = reverse('route')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_route_returns_linestring(self):
        url = reverse('route')
        res = self.client.get(url, {'from': '71.0,40.0', 'to': '71.01,40.02'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data.get('type'), 'Feature')
        geom = data.get('geometry')
        self.assertIsNotNone(geom)
        self.assertEqual(geom.get('type'), 'LineString')
        coords = geom.get('coordinates')
        self.assertIsInstance(coords, list)
        self.assertEqual(len(coords), 2)
