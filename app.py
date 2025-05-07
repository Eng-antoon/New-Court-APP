import os
from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# Apply CORS
CORS(app)

# Fix for proper IP handling behind proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configure app
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'volleyball-reservation-secret-key')
app.config['DEBUG'] = os.getenv('FLASK_ENV', 'development') == 'development'
app.config['TESTING'] = os.getenv('TESTING', 'False').lower() == 'true'

# Initialize Firebase
try:
    cred = credentials.Certificate('firebase-key.json')
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', 'ohda-john.appspot.com')
    })
    db = firestore.client()
    bucket = storage.bucket()
    print("Firebase initialized successfully")
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    if app.config['DEBUG']:
        # In development, we might want to proceed even with Firebase issues
        pass
    else:
        # In production, exit if Firebase fails to initialize
        raise e

# Import routes after app initialization to avoid circular imports
from routes.auth import auth_bp
from routes.courts import courts_bp
from routes.reservations import reservations_bp
from routes.users import users_bp
from routes.maintenance import maintenance_bp
from routes.waitlist import waitlist_bp

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(courts_bp, url_prefix='/api/courts')
app.register_blueprint(reservations_bp, url_prefix='/api/reservations')
app.register_blueprint(users_bp, url_prefix='/api/users')
app.register_blueprint(maintenance_bp, url_prefix='/api/maintenance')
app.register_blueprint(waitlist_bp, url_prefix='/api/waitlist')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "version": "1.0.0"})

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/api/init-test-data')
def init_test_data():
    try:
        # Create test users if they don't exist
        test_users = [
            {
                'email': 'admin@example.com',
                'password': 'password123',
                'name': 'Admin User',
                'role': 'admin'
            },
            {
                'email': 'user@example.com',
                'password': 'password123',
                'name': 'Regular User',
                'role': 'user'
            }
        ]
        
        for user_data in test_users:
            # Check if user already exists
            users_ref = db.collection('users').where('email', '==', user_data['email']).limit(1)
            users = users_ref.get()
            
            if len(users) == 0:
                try:
                    # Create user in Firebase Auth
                    user = auth.create_user(
                        email=user_data['email'],
                        password=user_data['password'],
                        display_name=user_data['name'],
                        email_verified=False
                    )
                    
                    # Store additional user data in Firestore
                    db.collection('users').document(user.uid).set({
                        'name': user_data['name'],
                        'email': user_data['email'],
                        'role': user_data['role'],
                        'created_at': firestore.SERVER_TIMESTAMP,
                        'profile_complete': True
                    })
                except Exception as e:
                    print(f"Error creating test user {user_data['email']}: {e}")
        
        # Create test courts if they don't exist
        test_courts = [
            {
                'name': 'Sunny Beach Volleyball',
                'address': {
                    'street': '123 Beach Blvd',
                    'city': 'Miami',
                    'state': 'FL',
                    'zip': '33101'
                },
                'is_indoor': False,
                'surface_type': 'sand',
                'description': 'Beautiful beachfront volleyball courts with a stunning ocean view. Perfect for professional play and casual games.',
                'amenities': ['showers', 'restrooms', 'parking', 'food vendors'],
                'images': ['https://images.unsplash.com/photo-1544991185-13ad84f36404?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80'],
                'operating_hours': {
                    'monday': {'is_open': True, 'open': '08:00', 'close': '22:00'},
                    'tuesday': {'is_open': True, 'open': '08:00', 'close': '22:00'},
                    'wednesday': {'is_open': True, 'open': '08:00', 'close': '22:00'},
                    'thursday': {'is_open': True, 'open': '08:00', 'close': '22:00'},
                    'friday': {'is_open': True, 'open': '08:00', 'close': '23:00'},
                    'saturday': {'is_open': True, 'open': '09:00', 'close': '23:00'},
                    'sunday': {'is_open': True, 'open': '09:00', 'close': '21:00'}
                },
                'coordinates': {'latitude': 25.7617, 'longitude': -80.1918},
                'status': 'active',
                'featured': True
            },
            {
                'name': 'Indoor Pro Arena',
                'address': {
                    'street': '456 Sports Way',
                    'city': 'Chicago',
                    'state': 'IL',
                    'zip': '60614'
                },
                'is_indoor': True,
                'surface_type': 'wood',
                'description': 'Professional-grade indoor volleyball courts with state-of-the-art facilities. Host to regional tournaments.',
                'amenities': ['locker rooms', 'showers', 'pro shop', 'gym', 'restaurant'],
                'images': ['https://images.unsplash.com/photo-1577412647305-991150c7d163?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80'],
                'operating_hours': {
                    'monday': {'is_open': True, 'open': '06:00', 'close': '23:00'},
                    'tuesday': {'is_open': True, 'open': '06:00', 'close': '23:00'},
                    'wednesday': {'is_open': True, 'open': '06:00', 'close': '23:00'},
                    'thursday': {'is_open': True, 'open': '06:00', 'close': '23:00'},
                    'friday': {'is_open': True, 'open': '06:00', 'close': '00:00'},
                    'saturday': {'is_open': True, 'open': '08:00', 'close': '00:00'},
                    'sunday': {'is_open': True, 'open': '08:00', 'close': '22:00'}
                },
                'coordinates': {'latitude': 41.8781, 'longitude': -87.6298},
                'status': 'active',
                'featured': True
            }
        ]
        
        for court_data in test_courts:
            # Check for existing courts with the same name and location
            courts_ref = db.collection('courts').where('name', '==', court_data['name']).limit(1)
            courts = courts_ref.get()
            
            if len(courts) == 0:
                try:
                    # Add timestamps
                    court_data['created_at'] = firestore.SERVER_TIMESTAMP
                    court_data['updated_at'] = firestore.SERVER_TIMESTAMP
                    
                    # Add to Firestore
                    db.collection('courts').add(court_data)
                except Exception as e:
                    print(f"Error creating test court {court_data['name']}: {e}")
        
        return jsonify({
            'success': True, 
            'message': 'Test data initialized successfully'
        })
    
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error initializing test data: {str(e)}'
        }), 500

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Context processors
@app.context_processor
def utility_processor():
    def format_date(date):
        if isinstance(date, datetime):
            return date.strftime('%Y-%m-%d')
        return date
    
    def format_time(time):
        if isinstance(time, datetime):
            return time.strftime('%I:%M %p')
        return time
    
    def current_year():
        return datetime.now().year
    
    return dict(
        format_date=format_date,
        format_time=format_time,
        current_year=current_year
    )

# Print all registered routes for debugging
print("\nRegistered Routes:")
for rule in app.url_map.iter_rules():
    print(f"{rule.endpoint}: {rule.rule}")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 