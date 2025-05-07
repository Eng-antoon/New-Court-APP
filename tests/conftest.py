import os
import pytest
from app import app as flask_app
import firebase_admin
from firebase_admin import credentials, firestore
import tempfile
import json
from unittest.mock import patch

class AuthBypassTestClient:
    """A special test client that bypasses authentication for testing"""
    def __init__(self, app, auth_token='test-auth-token'):
        self.app = app
        self.auth_token = auth_token
        self.client = app.test_client()
    
    def get(self, *args, **kwargs):
        # Add auth header if not provided
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        if 'Authorization' not in kwargs['headers']:
            kwargs['headers']['Authorization'] = f'Bearer {self.auth_token}'
        return self.client.get(*args, **kwargs)
    
    def post(self, *args, **kwargs):
        # Add auth header if not provided
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        if 'Authorization' not in kwargs['headers']:
            kwargs['headers']['Authorization'] = f'Bearer {self.auth_token}'
        return self.client.post(*args, **kwargs)
    
    def put(self, *args, **kwargs):
        # Add auth header if not provided
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        if 'Authorization' not in kwargs['headers']:
            kwargs['headers']['Authorization'] = f'Bearer {self.auth_token}'
        return self.client.put(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Add auth header if not provided
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        if 'Authorization' not in kwargs['headers']:
            kwargs['headers']['Authorization'] = f'Bearer {self.auth_token}'
        return self.client.delete(*args, **kwargs)

@pytest.fixture
def app():
    # Configure app for testing
    flask_app.config.update({
        'TESTING': True,
        'SERVER_NAME': 'localhost',
    })
    
    # Create app context
    with flask_app.app_context():
        yield flask_app

@pytest.fixture
def client(app):
    # Return an AuthBypassTestClient instead of the regular test client
    return AuthBypassTestClient(app)

@pytest.fixture
def firebase_app():
    # Create a mock firebase credentials file
    creds_content = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "mock-key-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK_KEY\n-----END PRIVATE KEY-----\n",
        "client_email": "test@example.com",
        "client_id": "mock-client-id",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test%40example.com"
    }
    
    # Write mock credentials to temp file
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'w') as tmp:
        json.dump(creds_content, tmp)
    
    # Initialize Firebase with mock credentials
    try:
        # Try to initialize firebase app for tests
        app = firebase_admin.initialize_app(
            credentials.Certificate(path),
            {
                'projectId': 'test-project',
                'storageBucket': 'test-bucket.appspot.com'
            },
            name='test-app'
        )
        yield app
    except ValueError:
        # If already initialized, get the existing app
        app = firebase_admin.get_app(name='test-app')
        yield app
    finally:
        # Clean up temp file
        os.unlink(path)
        # Try to delete the app
        try:
            firebase_admin.delete_app(app)
        except:
            pass

@pytest.fixture
def mock_db(firebase_app):
    # Create a mock Firestore client
    return firestore.client(app=firebase_app)

@pytest.fixture
def auth_token():
    # Create a mock auth token for testing
    return "test-auth-token" 