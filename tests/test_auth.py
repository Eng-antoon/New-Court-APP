import pytest
import json
from unittest.mock import patch, MagicMock

# Test user registration
def test_user_registration(client):
    # Sample user data
    user_data = {
        'email': 'test@example.com',
        'password': 'Password123!',
        'name': 'Test User',
        'phone': '123-456-7890'
    }
    
    # Mock Firebase auth response
    mock_user = MagicMock()
    mock_user.uid = 'test-user-id'
    mock_user.email = user_data['email']
    
    # Mock the Firebase admin SDK methods
    with patch('firebase_admin.auth.create_user', return_value=mock_user), \
         patch('firebase_admin.firestore.client') as mock_db:
        
        # Configure mock firestore client
        mock_collection = MagicMock()
        mock_doc = MagicMock()
        mock_db.return_value.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc
        
        # Make request
        response = client.post(
            '/api/auth/register',
            data=json.dumps(user_data),
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 201
        response_data = json.loads(response.data)
        assert response_data['message'] == 'User registered successfully'
        assert 'user_id' in response_data
        
        # Verify that create_user was called with correct data
        from firebase_admin import auth
        auth.create_user.assert_called_once()
        
        # Verify that user document was created in Firestore
        mock_collection.document.assert_called_once_with(mock_user.uid)
        mock_doc.set.assert_called_once()

# Test user login
def test_user_login(client):
    # Login credentials
    credentials = {
        'email': 'test@example.com',
        'password': 'Password123!'
    }
    
    # Mock Firebase auth token
    mock_token = 'mock-auth-token'
    
    # Mock auth service verify_password_sign_in method
    with patch('routes.auth.verify_password_sign_in', return_value=mock_token):
        # Make request
        response = client.post(
            '/api/auth/login',
            data=json.dumps(credentials),
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'token' in response_data
        assert response_data['token'] == mock_token

# Test protected route access with valid token
def test_protected_route_with_valid_token(client, auth_token):
    # Mock user data that would be decoded from token
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock verify_token method
    with patch('routes.auth.verify_token', return_value=user_data):
        # Make request to a protected endpoint
        response = client.get(
            '/api/users/profile',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertion depends on the endpoint, but status should be successful
        assert response.status_code in [200, 204]

# Test protected route access with invalid token
def test_protected_route_with_invalid_token(client):
    # Make request to a protected endpoint with invalid token
    response = client.get(
        '/api/users/profile',
        headers={'Authorization': 'Bearer invalid-token'}
    )
    
    # Should get unauthorized response
    assert response.status_code == 401

# Test admin-only route with admin token
def test_admin_route_with_admin_token(client, auth_token):
    # Mock admin user data
    admin_data = {
        'id': 'admin-user-id',
        'email': 'admin@example.com',
        'role': 'admin'
    }
    
    # Mock verify_token method
    with patch('routes.auth.verify_token', return_value=admin_data):
        # Make request to an admin-only endpoint
        response = client.get(
            '/api/users',  # Listing all users is typically admin-only
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Should get successful response
        assert response.status_code == 200

# Test admin-only route with non-admin token
def test_admin_route_with_non_admin_token(client, auth_token):
    # Mock regular user data
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock verify_token method
    with patch('routes.auth.verify_token', return_value=user_data):
        # Make request to an admin-only endpoint
        response = client.get(
            '/api/users',  # Listing all users is typically admin-only
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Should get forbidden response
        assert response.status_code == 403

# Test password reset flow
def test_password_reset_request(client):
    # Email for password reset
    email_data = {
        'email': 'test@example.com'
    }
    
    # Mock send password reset email
    with patch('firebase_admin.auth.generate_password_reset_link') as mock_generate_link:
        mock_generate_link.return_value = 'https://example.com/reset-password?token=test-token'
        
        # Make request
        response = client.post(
            '/api/auth/reset-password',
            data=json.dumps(email_data),
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'message' in response_data
        assert 'success' in response_data['message'].lower()
        
        # Verify that generate_password_reset_link was called with correct email
        mock_generate_link.assert_called_once_with(email_data['email'], action_code_settings=None)

# Test token refresh
def test_token_refresh(client, auth_token):
    # Mock user data
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock new token
    new_token = 'new-auth-token'
    
    # Mock verify_token and refresh_token methods
    with patch('routes.auth.verify_token', return_value=user_data), \
         patch('routes.auth.refresh_token', return_value=new_token):
        
        # Make request
        response = client.post(
            '/api/auth/refresh-token',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'token' in response_data
        assert response_data['token'] == new_token

# Test logout
def test_logout(client, auth_token):
    # Mock user data
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock Firebase auth token revocation
    with patch('routes.auth.verify_token', return_value=user_data), \
         patch('firebase_admin.auth.revoke_refresh_tokens') as mock_revoke:
        
        # Make request
        response = client.post(
            '/api/auth/logout',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'message' in response_data
        assert 'logged out' in response_data['message'].lower()
        
        # Verify token was revoked
        mock_revoke.assert_called_once_with(user_data['id'])

# Test multi-factor authentication
def test_mfa_setup(client, auth_token):
    # Mock user data
    user_data = {
        'id': 'test-user-id',
        'email': 'test@example.com',
        'role': 'user'
    }
    
    # Mock phone number for MFA
    phone_data = {
        'phone_number': '+1234567890'
    }
    
    # Mock verification code
    verification_id = 'verification-id'
    
    # Mock Firebase auth MFA enrollment
    with patch('routes.auth.verify_token', return_value=user_data), \
         patch('firebase_admin.auth.get_user_by_email', return_value=MagicMock(uid=user_data['id'])), \
         patch('routes.auth.generate_mfa_verification_id', return_value=verification_id):
        
        # Make request
        response = client.post(
            '/api/auth/mfa/setup',
            data=json.dumps(phone_data),
            content_type='application/json',
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'verification_id' in response_data
        assert response_data['verification_id'] == verification_id 