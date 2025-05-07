import pytest
import json
import datetime
from unittest.mock import patch, MagicMock
from firebase_admin import firestore
import pytz

# Test reservation creation
def test_create_reservation_success(client, auth_token):
    # Mock authenticated user
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Sample reservation data
    reservation_data = {
        'court_id': 'test-court-id',
        'start_time': (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)).isoformat(),
        'end_time': (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1, hours=1)).isoformat()
    }
    
    # Mock Firestore transaction and document references
    mock_transaction = MagicMock()
    mock_court_doc = MagicMock()
    mock_reservation_doc = MagicMock()
    
    # Configure court document mock
    mock_court_doc.get.return_value.exists = True
    mock_court_doc.get.return_value.to_dict.return_value = {
        'name': 'Test Court',
        'status': 'active'
    }
    
    # Configure reservation document mock to indicate no overlapping reservations
    mock_reservation_query = MagicMock()
    mock_reservation_query.get.return_value = []
    
    # Mock Firestore client
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data), \
         patch('firebase_admin.firestore.transaction') as mock_transaction_ctx:
        
        # Configure mock database
        mock_db.return_value.collection.side_effect = lambda collection_name: {
            'courts': MagicMock(document=lambda _: mock_court_doc),
            'reservations': MagicMock(
                document=lambda _: mock_reservation_doc,
                where=lambda *args: mock_reservation_query
            ),
            'maintenance': MagicMock(where=lambda *args: MagicMock(get=lambda: []))
        }[collection_name]
        
        # Configure transaction mock
        mock_transaction_ctx.return_value.__enter__.return_value = mock_transaction
        
        # Make request
        response = client.post(
            '/api/reservations',
            data=json.dumps(reservation_data),
            content_type='application/json',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 201
        response_data = json.loads(response.data)
        assert 'id' in response_data
        assert response_data['status'] == 'confirmed'

# Test concurrent bookings (double booking prevention)
def test_concurrent_bookings_prevention(client, auth_token):
    # Mock authenticated user
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Sample reservation data
    reservation_data = {
        'court_id': 'test-court-id',
        'start_time': (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)).isoformat(),
        'end_time': (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1, hours=1)).isoformat()
    }
    
    # Mock existing overlapping reservation
    mock_overlapping_reservation = MagicMock()
    mock_overlapping_reservation.to_dict.return_value = {
        'court_id': 'test-court-id',
        'user_id': 'other-user-id',
        'start_time': datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1),
        'end_time': datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1, hours=2),
        'status': 'confirmed'
    }
    
    # Mock Firestore transaction and document references
    mock_transaction = MagicMock()
    mock_court_doc = MagicMock()
    mock_reservation_doc = MagicMock()
    
    # Configure court document mock
    mock_court_doc.get.return_value.exists = True
    mock_court_doc.get.return_value.to_dict.return_value = {
        'name': 'Test Court',
        'status': 'active'
    }
    
    # Configure reservation document mock to indicate overlapping reservations
    mock_reservation_query = MagicMock()
    mock_reservation_query.get.return_value = [mock_overlapping_reservation]
    
    # Mock Firestore client
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data), \
         patch('firebase_admin.firestore.transaction') as mock_transaction_ctx:
        
        # Configure mock database
        mock_db.return_value.collection.side_effect = lambda collection_name: {
            'courts': MagicMock(document=lambda _: mock_court_doc),
            'reservations': MagicMock(
                document=lambda _: mock_reservation_doc,
                where=lambda *args: mock_reservation_query
            ),
            'maintenance': MagicMock(where=lambda *args: MagicMock(get=lambda: []))
        }[collection_name]
        
        # Configure transaction mock
        mock_transaction_ctx.return_value.__enter__.return_value = mock_transaction
        
        # Make request
        response = client.post(
            '/api/reservations',
            data=json.dumps(reservation_data),
            content_type='application/json',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 409  # Conflict
        response_data = json.loads(response.data)
        assert 'message' in response_data
        assert 'overlapping' in response_data['message'].lower()

# Test cancellation with >= 48h notice
def test_cancel_reservation_with_sufficient_notice(client, auth_token):
    # Mock authenticated user
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock reservation data
    reservation_id = 'test-reservation-id'
    start_time = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=3)
    
    mock_reservation_doc = MagicMock()
    mock_reservation_doc.get.return_value.exists = True
    mock_reservation_doc.get.return_value.to_dict.return_value = {
        'court_id': 'test-court-id',
        'user_id': 'test-user-id',  # Same as authenticated user
        'start_time': start_time,
        'end_time': start_time + datetime.timedelta(hours=1),
        'status': 'confirmed'
    }
    
    # Mock waitlist
    mock_waitlist_docs = []
    mock_waitlist_query = MagicMock()
    mock_waitlist_query.get.return_value = mock_waitlist_docs
    
    # Mock Firestore client
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data):
        
        # Configure mock database
        mock_db.return_value.collection.side_effect = lambda collection_name: {
            'reservations': MagicMock(
                document=lambda _: mock_reservation_doc,
                where=lambda *args: mock_waitlist_query
            )
        }[collection_name]
        
        # Make request
        response = client.post(
            f'/api/reservations/{reservation_id}/cancel',
            content_type='application/json',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['status'] == 'cancelled'
        assert not response_data.get('penalty', False)

# Test cancellation with < 48h notice
def test_cancel_reservation_with_insufficient_notice(client, auth_token):
    # Mock authenticated user
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock reservation data
    reservation_id = 'test-reservation-id'
    start_time = datetime.datetime.now(pytz.UTC) + datetime.timedelta(hours=12)
    
    mock_reservation_doc = MagicMock()
    mock_reservation_doc.get.return_value.exists = True
    mock_reservation_doc.get.return_value.to_dict.return_value = {
        'court_id': 'test-court-id',
        'user_id': 'test-user-id',  # Same as authenticated user
        'start_time': start_time,
        'end_time': start_time + datetime.timedelta(hours=1),
        'status': 'confirmed'
    }
    
    # Mock waitlist
    mock_waitlist_docs = []
    mock_waitlist_query = MagicMock()
    mock_waitlist_query.get.return_value = mock_waitlist_docs
    
    # Mock Firestore client
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data):
        
        # Configure mock database
        mock_db.return_value.collection.side_effect = lambda collection_name: {
            'reservations': MagicMock(
                document=lambda _: mock_reservation_doc,
                where=lambda *args: mock_waitlist_query
            )
        }[collection_name]
        
        # Make request
        response = client.post(
            f'/api/reservations/{reservation_id}/cancel',
            content_type='application/json',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['status'] == 'cancelled'
        assert response_data.get('penalty', False)

# Test waitlist promotion after cancellation
def test_waitlist_promotion_after_cancellation(client, auth_token):
    # Mock authenticated user
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock reservation data
    reservation_id = 'test-reservation-id'
    court_id = 'test-court-id'
    start_time = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=3)
    end_time = start_time + datetime.timedelta(hours=1)
    
    mock_reservation_doc = MagicMock()
    mock_reservation_doc.get.return_value.exists = True
    mock_reservation_doc.get.return_value.to_dict.return_value = {
        'court_id': court_id,
        'user_id': 'test-user-id',  # Same as authenticated user
        'start_time': start_time,
        'end_time': end_time,
        'status': 'confirmed'
    }
    
    # Mock waitlist entries
    waitlist_user_id = 'waitlist-user-id'
    mock_waitlist_doc = MagicMock()
    mock_waitlist_doc.id = 'waitlist-entry-id'
    mock_waitlist_doc.to_dict.return_value = {
        'court_id': court_id,
        'user_id': waitlist_user_id,
        'start_time': start_time,
        'end_time': end_time,
        'created_at': datetime.datetime.now(pytz.UTC),
    }
    
    mock_waitlist_query = MagicMock()
    mock_waitlist_query.get.return_value = [mock_waitlist_doc]
    
    # Mock waitlist user
    mock_user_doc = MagicMock()
    mock_user_doc.get.return_value.exists = True
    mock_user_doc.get.return_value.to_dict.return_value = {
        'email': 'waitlist-user@example.com',
        'name': 'Waitlist User'
    }
    
    # Mock Firestore client
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data), \
         patch('firebase_admin.firestore.transaction') as mock_transaction_ctx:
        
        # Configure mock database
        mock_db.return_value.collection.side_effect = lambda collection_name: {
            'reservations': MagicMock(
                document=lambda _: mock_reservation_doc,
                where=lambda field, op, value: mock_waitlist_query if field == 'status' and value == 'waitlist' else MagicMock(get=lambda: [])
            ),
            'users': MagicMock(document=lambda _: mock_user_doc)
        }[collection_name]
        
        # Configure transaction mock
        mock_transaction = MagicMock()
        mock_transaction_ctx.return_value.__enter__.return_value = mock_transaction
        
        # Make request
        response = client.post(
            f'/api/reservations/{reservation_id}/cancel',
            content_type='application/json',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['status'] == 'cancelled'
        
        # Verify that waitlist user was promoted
        mock_transaction.delete.assert_called_with(mock_waitlist_doc.reference)
        mock_transaction.set.assert_called()  # New reservation created for waitlist user

# Test recurring reservation
def test_create_recurring_reservation(client, auth_token):
    # Mock authenticated user
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Sample recurring reservation data
    start_date = datetime.datetime.now(pytz.UTC).replace(hour=14, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    end_date = start_date + datetime.timedelta(hours=1)
    
    reservation_data = {
        'court_id': 'test-court-id',
        'start_time': start_date.isoformat(),
        'end_time': end_date.isoformat(),
        'recurring': {
            'pattern': 'weekly',
            'end_date': (start_date + datetime.timedelta(days=28)).isoformat()
        }
    }
    
    # Mock Firestore transaction and document references
    mock_transaction = MagicMock()
    mock_court_doc = MagicMock()
    mock_reservation_doc = MagicMock()
    
    # Configure court document mock
    mock_court_doc.get.return_value.exists = True
    mock_court_doc.get.return_value.to_dict.return_value = {
        'name': 'Test Court',
        'status': 'active'
    }
    
    # Configure reservation document mock to indicate no overlapping reservations
    mock_reservation_query = MagicMock()
    mock_reservation_query.get.return_value = []
    
    # Mock Firestore client
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data), \
         patch('firebase_admin.firestore.transaction') as mock_transaction_ctx, \
         patch('uuid.uuid4', return_value=MagicMock(hex='recurring-group-id')):
        
        # Configure mock database
        mock_db.return_value.collection.side_effect = lambda collection_name: {
            'courts': MagicMock(document=lambda _: mock_court_doc),
            'reservations': MagicMock(
                document=lambda _: mock_reservation_doc,
                where=lambda *args: mock_reservation_query
            ),
            'maintenance': MagicMock(where=lambda *args: MagicMock(get=lambda: []))
        }[collection_name]
        
        # Configure transaction mock
        mock_transaction_ctx.return_value.__enter__.return_value = mock_transaction
        
        # Make request
        response = client.post(
            '/api/reservations',
            data=json.dumps(reservation_data),
            content_type='application/json',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 201
        response_data = json.loads(response.data)
        assert 'recurring_group_id' in response_data
        assert response_data['recurring_group_id'] == 'recurring-group-id'

# Test maintenance override
def test_maintenance_override_blocks_reservations(client, auth_token):
    # Mock authenticated admin user
    admin_user_data = {
        'id': 'admin-user-id',
        'email': 'admin@example.com',
        'role': 'admin'
    }
    
    # Create maintenance window
    maintenance_data = {
        'court_id': 'test-court-id',
        'start_time': (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)).isoformat(),
        'end_time': (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1, hours=4)).isoformat(),
        'reason': 'Court resurfacing'
    }
    
    # Mock maintenance document
    mock_maintenance_doc = MagicMock()
    mock_maintenance_doc.id = 'test-maintenance-id'
    
    # Mock Firestore client for maintenance creation
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=admin_user_data):
        
        # Configure mock database
        mock_db.return_value.collection.side_effect = lambda collection_name: {
            'maintenance': MagicMock(document=lambda _: mock_maintenance_doc)
        }[collection_name]
        
        # Create maintenance window
        response = client.post(
            '/api/maintenance',
            data=json.dumps(maintenance_data),
            content_type='application/json',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assert maintenance creation
        assert response.status_code == 201
    
    # Now try to create a reservation during maintenance window
    # Mock regular user
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Sample reservation data during maintenance window
    reservation_data = {
        'court_id': 'test-court-id',
        'start_time': (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1, hours=1)).isoformat(),
        'end_time': (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1, hours=2)).isoformat()
    }
    
    # Mock existing maintenance document
    mock_maintenance_record = MagicMock()
    mock_maintenance_record.to_dict.return_value = {
        'court_id': 'test-court-id',
        'start_time': datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1),
        'end_time': datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1, hours=4),
        'reason': 'Court resurfacing'
    }
    
    # Mock Firestore transaction and document references
    mock_transaction = MagicMock()
    mock_court_doc = MagicMock()
    mock_reservation_doc = MagicMock()
    
    # Configure court document mock
    mock_court_doc.get.return_value.exists = True
    mock_court_doc.get.return_value.to_dict.return_value = {
        'name': 'Test Court',
        'status': 'active'
    }
    
    # Configure maintenance query to return existing maintenance
    mock_maintenance_query = MagicMock()
    mock_maintenance_query.get.return_value = [mock_maintenance_record]
    
    # Mock Firestore client
    with patch('firebase_admin.firestore.client') as mock_db, \
         patch('routes.auth.verify_token', return_value=user_data), \
         patch('firebase_admin.firestore.transaction') as mock_transaction_ctx:
        
        # Configure mock database
        mock_db.return_value.collection.side_effect = lambda collection_name: {
            'courts': MagicMock(document=lambda _: mock_court_doc),
            'reservations': MagicMock(
                document=lambda _: mock_reservation_doc,
                where=lambda *args: MagicMock(get=lambda: [])
            ),
            'maintenance': MagicMock(where=lambda *args: mock_maintenance_query)
        }[collection_name]
        
        # Configure transaction mock
        mock_transaction_ctx.return_value.__enter__.return_value = mock_transaction
        
        # Make request
        response = client.post(
            '/api/reservations',
            data=json.dumps(reservation_data),
            content_type='application/json',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 409  # Conflict
        response_data = json.loads(response.data)
        assert 'message' in response_data
        assert 'maintenance' in response_data['message'].lower() 