
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from rest_framework.test import APIClient
from rest_framework import status

from rooms.models import Room


class RoomsAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        # create_user on this project requires email (and accepts extra fields)
        self.user = User.objects.create_user(email='test@example.com', password='testpass', full_name='Test User')

        # create some sample rooms
        self.room1 = Room.objects.create(name='Room A', capacity=10, location='First Floor')
        self.room2 = Room.objects.create(name='Room B', capacity=5, location='Second Floor', status=False)

    def test_list_rooms(self):
        url = reverse('room-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # paginated results
        data = resp.data
        results = data.get('results', data)
        self.assertTrue(len(results) >= 2)
        item = results[0]
        for key in ('id', 'name', 'capacity', 'location', 'status', 'actions'):
            self.assertIn(key, item)

    def test_create_room(self):
        url = reverse('room-list')
        payload = {'name': 'Room C', 'capacity': 20, 'location': 'Ground Floor', 'status': True}
        self.client.force_authenticate(self.user)
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Room.objects.filter(name='Room C').count(), 1)

    def test_update_room(self):
        url = reverse('room-detail', args=[self.room1.pk])
        self.client.force_authenticate(self.user)
        resp = self.client.patch(url, {'capacity': 12}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.room1.refresh_from_db()
        self.assertEqual(self.room1.capacity, 12)

    def test_toggle_status(self):
        url = reverse('room-toggle-status', args=[self.room2.pk])
        self.client.force_authenticate(self.user)
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.room2.refresh_from_db()
        self.assertTrue(self.room2.status)

    def test_delete_room(self):
        url = reverse('room-detail', args=[self.room1.pk])
        self.client.force_authenticate(self.user)
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Room.objects.filter(pk=self.room1.pk).exists())
