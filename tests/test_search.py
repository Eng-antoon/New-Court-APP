import pytest
import json
import datetime
from unittest.mock import patch, MagicMock
import pytz

# Test basic court search
def test_court_search_basic(client, auth_token):
    # Mock user data
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock court data
    mock_court1 = MagicMock()
    mock_court1.id = 'court-1'
    mock_court1.to_dict.return_value = {
        'name': 'Beach Volleyball Court 1',
        'surface': 'sand',
        'indoor': False,
        'status': 'active',
        'address': {
            'street': '123 Beach St',
            'city': 'Miami',
            'state': 'FL',
            'country': 'USA',
            'zip': '33101',
            'geo': {'lat': 25.7617, 'lng': -80.1918}
        },
        'amenities': ['showers', 'restrooms', 'parking']
    }
    
    mock_court2 = MagicMock()
    mock_court2.id = 'court-2'
    mock_court2.to_dict.return_value = {
        'name': 'Indoor Volleyball Center',
        'surface': 'wood',
        'indoor': True,
        'status': 'active',
        'address': {
            'street': '456 Sports Ave',
            'city': 'Miami',
            'state': 'FL',
            'country': 'USA',
            'zip': '33125',
            'geo': {'lat': 25.7863, 'lng': -80.2091}
        },
        'amenities': ['showers', 'restrooms', 'water_fountain', 'wifi']
    }
    
    # Mock Firestore query
    mock_query = MagicMock()
    mock_query.get.return_value = [mock_court1, mock_court2]
    
    # Mock the Firestore client
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data):
        
        # Configure mock database
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.return_value.collection.return_value = mock_collection
        
        # Make request
        response = client.get(
            '/api/courts?city=Miami',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'courts' in response_data
        assert len(response_data['courts']) == 2
        
        # Check that the courts were properly returned
        courts = response_data['courts']
        assert any(court['id'] == 'court-1' for court in courts)
        assert any(court['id'] == 'court-2' for court in courts)
        
        # Verify that the filter was applied
        mock_collection.where.assert_called_with('address.city', '==', 'Miami')

# Test search with multiple filter criteria
def test_court_search_multiple_filters(client, auth_token):
    # Mock user data
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock court data
    mock_court = MagicMock()
    mock_court.id = 'court-1'
    mock_court.to_dict.return_value = {
        'name': 'Beach Volleyball Court 1',
        'surface': 'sand',
        'indoor': False,
        'status': 'active',
        'address': {
            'street': '123 Beach St',
            'city': 'Miami',
            'state': 'FL',
            'country': 'USA',
            'zip': '33101',
            'geo': {'lat': 25.7617, 'lng': -80.1918}
        },
        'amenities': ['showers', 'restrooms', 'parking']
    }
    
    # Mock Firestore query for multiple filters
    mock_query1 = MagicMock()
    mock_query2 = MagicMock()
    mock_query3 = MagicMock()
    mock_query1.where.return_value = mock_query2
    mock_query2.where.return_value = mock_query3
    mock_query3.get.return_value = [mock_court]
    
    # Mock the Firestore client
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data):
        
        # Configure mock database
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query1
        mock_db.return_value.collection.return_value = mock_collection
        
        # Make request with multiple filters
        response = client.get(
            '/api/courts?surface=sand&indoor=false&amenities=showers',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'courts' in response_data
        assert len(response_data['courts']) == 1
        assert response_data['courts'][0]['id'] == 'court-1'
        
        # Verify that all filters were applied
        mock_collection.where.assert_called_with('surface', '==', 'sand')
        mock_query1.where.assert_called_with('indoor', '==', False)
        mock_query2.where.assert_called_with('amenities', 'array_contains', 'showers')

# Test search with geo-based filtering (nearby courts)
def test_court_search_by_location(client, auth_token):
    # Mock user data
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock court data with distance info
    mock_court1 = MagicMock()
    mock_court1.id = 'court-1'
    mock_court1.to_dict.return_value = {
        'name': 'Nearby Court',
        'surface': 'sand',
        'status': 'active',
        'address': {
            'street': '123 Close St',
            'city': 'Miami',
            'state': 'FL',
            'zip': '33101',
            'geo': {'lat': 25.7617, 'lng': -80.1918}
        }
    }
    
    mock_court2 = MagicMock()
    mock_court2.id = 'court-2'
    mock_court2.to_dict.return_value = {
        'name': 'Far Away Court',
        'surface': 'sand',
        'status': 'active',
        'address': {
            'street': '456 Distant Ave',
            'city': 'Orlando',
            'state': 'FL',
            'zip': '32801',
            'geo': {'lat': 28.5383, 'lng': -81.3792}
        }
    }
    
    # Mock Firestore query
    mock_query = MagicMock()
    mock_query.get.return_value = [mock_court1, mock_court2]
    
    # Mock geo functions
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data), \
         patch('routes.courts.calculate_distance') as mock_calculate_distance:
        
        # Configure distance calculation to make court1 nearby and court2 far away
        mock_calculate_distance.side_effect = lambda lat1, lng1, lat2, lng2: 5.0 if lat2 == 25.7617 else 200.0
        
        # Configure mock database
        mock_db.return_value.collection.return_value.get.return_value = [mock_court1, mock_court2]
        
        # Make request with location parameters
        response = client.get(
            '/api/courts/nearby?lat=25.7743&lng=-80.1937&radius=10',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'courts' in response_data
        
        # Should only return the nearby court
        assert len(response_data['courts']) == 1
        assert response_data['courts'][0]['id'] == 'court-1'
        assert 'distance' in response_data['courts'][0]
        assert response_data['courts'][0]['distance'] == 5.0

# Test search for available time slots
def test_search_available_time_slots(client, auth_token):
    # Mock user data
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Create search parameters
    court_id = 'test-court-id'
    date = datetime.datetime.now(pytz.UTC).strftime('%Y-%m-%d')
    
    # Mock court data
    mock_court = MagicMock()
    mock_court.id = court_id
    mock_court.get.return_value.exists = True
    mock_court.get.return_value.to_dict.return_value = {
        'name': 'Test Court',
        'hours': {
            'monday': {'open': '08:00', 'close': '22:00'},
            'tuesday': {'open': '08:00', 'close': '22:00'},
            'wednesday': {'open': '08:00', 'close': '22:00'},
            'thursday': {'open': '08:00', 'close': '22:00'},
            'friday': {'open': '08:00', 'close': '22:00'},
            'saturday': {'open': '09:00', 'close': '20:00'},
            'sunday': {'open': '09:00', 'close': '20:00'}
        },
        'slot_duration_minutes': 60
    }
    
    # Mock existing reservations
    mock_reservation1 = MagicMock()
    mock_reservation1.to_dict.return_value = {
        'court_id': court_id,
        'start_time': datetime.datetime.strptime(f'{date} 10:00:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC),
        'end_time': datetime.datetime.strptime(f'{date} 11:00:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC),
        'status': 'confirmed'
    }
    
    mock_reservation2 = MagicMock()
    mock_reservation2.to_dict.return_value = {
        'court_id': court_id,
        'start_time': datetime.datetime.strptime(f'{date} 14:00:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC),
        'end_time': datetime.datetime.strptime(f'{date} 15:00:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC),
        'status': 'confirmed'
    }
    
    # Mock maintenance
    mock_maintenance = MagicMock()
    mock_maintenance.to_dict.return_value = {
        'court_id': court_id,
        'start_time': datetime.datetime.strptime(f'{date} 18:00:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC),
        'end_time': datetime.datetime.strptime(f'{date} 20:00:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC)
    }
    
    # Mock Firestore queries
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data):
        
        # Configure mock database
        mock_db.return_value.collection.side_effect = lambda collection_name: {
            'courts': MagicMock(document=lambda _: mock_court),
            'reservations': MagicMock(where=lambda *args: MagicMock(get=lambda: [mock_reservation1, mock_reservation2])),
            'maintenance': MagicMock(where=lambda *args: MagicMock(get=lambda: [mock_maintenance]))
        }[collection_name]
        
        # Make request
        response = client.get(
            f'/api/courts/{court_id}/availability?date={date}',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'slots' in response_data
        
        # Check that the correct number of available slots is returned
        # Court is open 8AM-10PM (14 hours), minus 2 hours for reservations and 2 hours for maintenance
        # So we should have 10 available slots
        available_slots = [slot for slot in response_data['slots'] if slot['status'] == 'available']
        assert len(available_slots) == 10
        
        # Verify that reserved slots are marked correctly
        reserved_slots = [slot for slot in response_data['slots'] if slot['status'] == 'reserved']
        assert len(reserved_slots) == 2
        assert any(slot['start_time'].endswith('10:00:00') for slot in reserved_slots)
        assert any(slot['start_time'].endswith('14:00:00') for slot in reserved_slots)
        
        # Verify that maintenance slots are marked correctly
        maintenance_slots = [slot for slot in response_data['slots'] if slot['status'] == 'maintenance']
        assert len(maintenance_slots) == 2
        assert any(slot['start_time'].endswith('18:00:00') for slot in maintenance_slots)
        assert any(slot['start_time'].endswith('19:00:00') for slot in maintenance_slots)

# Test search with text query (including typo tolerance)
def test_court_search_with_text_query(client, auth_token):
    # Mock user data
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock court data
    mock_court1 = MagicMock()
    mock_court1.id = 'court-1'
    mock_court1.to_dict.return_value = {
        'name': 'Beach Volleyball Court',
        'description': 'Sandy beach volleyball court for professionals and amateurs',
        'surface': 'sand',
        'status': 'active'
    }
    
    mock_court2 = MagicMock()
    mock_court2.id = 'court-2'
    mock_court2.to_dict.return_value = {
        'name': 'Indoor Volleyball Center',
        'description': 'Professional indoor court with wood flooring',
        'surface': 'wood',
        'status': 'active'
    }
    
    # Mock Firestore query
    mock_query = MagicMock()
    mock_query.get.return_value = [mock_court1, mock_court2]
    
    # Mock the Firestore client
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data), \
         patch('routes.courts.text_search_courts') as mock_text_search:
        
        # Configure mock text search to handle typo tolerance
        # "beech" should match "beach" despite the typo
        mock_text_search.return_value = [mock_court1]
        
        # Configure mock database
        mock_db.return_value.collection.return_value = MagicMock(get=lambda: [mock_court1, mock_court2])
        
        # Make request with a search query containing a typo
        response = client.get(
            '/api/courts/search?q=beech+volleyball',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'courts' in response_data
        assert len(response_data['courts']) == 1
        assert response_data['courts'][0]['id'] == 'court-1'
        
        # Verify that text search was called with the query
        mock_text_search.assert_called_with('beech volleyball', [mock_court1, mock_court2]) 