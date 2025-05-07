import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
from datetime import datetime, timedelta
import pytz
import random
import json

# Initialize Firebase
def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    try:
        cred = credentials.Certificate('firebase-key.json')
        firebase_admin.initialize_app(cred, {
            'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', 'ohda-john.appspot.com')
        })
        db = firestore.client()
        print("Firebase initialized successfully")
        return db
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        raise

def create_users(db):
    """Create sample users with different roles"""
    print("Creating users...")
    
    users = [
        {
            'email': 'admin@example.com',
            'password': 'Admin123!',
            'name': 'Admin User',
            'role': 'admin',
            'phone': '+15551234567',
            'profile_complete': True
        },
        {
            'email': 'owner@example.com',
            'password': 'Owner123!',
            'name': 'Court Owner',
            'role': 'owner',
            'phone': '+15559876543',
            'profile_complete': True
        },
        {
            'email': 'user1@example.com',
            'password': 'User123!',
            'name': 'John Player',
            'role': 'user',
            'phone': '+15551112222',
            'profile_complete': True
        },
        {
            'email': 'user2@example.com',
            'password': 'User123!',
            'name': 'Emma Spiker',
            'role': 'user',
            'phone': '+15553334444',
            'profile_complete': True
        },
        {
            'email': 'user3@example.com',
            'password': 'User123!',
            'name': 'Alex Setter',
            'role': 'user',
            'phone': '+15555556666',
            'profile_complete': False
        }
    ]
    
    created_users = []
    for user_data in users:
        # Check if user already exists
        try:
            existing_user = auth.get_user_by_email(user_data['email'])
            print(f"User {user_data['email']} already exists with ID: {existing_user.uid}")
            created_users.append(existing_user.uid)
            
            # Update the user data in Firestore
            db.collection('users').document(existing_user.uid).set({
                'name': user_data['name'],
                'email': user_data['email'],
                'role': user_data['role'],
                'phone': user_data.get('phone', ''),
                'profile_complete': user_data.get('profile_complete', False),
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
        except auth.UserNotFoundError:
            # Create new user
            try:
                new_user = auth.create_user(
                    email=user_data['email'],
                    password=user_data['password'],
                    display_name=user_data['name'],
                    phone_number=user_data.get('phone', None),
                    email_verified=True
                )
                
                # Store additional user data in Firestore
                db.collection('users').document(new_user.uid).set({
                    'name': user_data['name'],
                    'email': user_data['email'],
                    'role': user_data['role'],
                    'phone': user_data.get('phone', ''),
                    'profile_complete': user_data.get('profile_complete', False),
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                
                print(f"Created user {user_data['email']} with ID: {new_user.uid}")
                created_users.append(new_user.uid)
                
            except Exception as e:
                print(f"Error creating user {user_data['email']}: {e}")
    
    return created_users

def create_courts(db):
    """Create sample volleyball courts"""
    print("Creating courts...")
    
    courts = [
        {
            'name': 'Sunny Beach Volleyball',
            'address': {
                'street': '123 Beach Blvd',
                'city': 'Miami',
                'state': 'FL',
                'zip': '33101',
                'formatted': '123 Beach Blvd, Miami, FL 33101'
            },
            'is_indoor': False,
            'surface_type': 'sand',
            'description': 'Beautiful beachfront volleyball courts with a stunning ocean view. Perfect for professional play and casual games.',
            'amenities': ['showers', 'restrooms', 'parking', 'food vendors'],
            'images': [
                'https://images.unsplash.com/photo-1544991185-13ad84f36404?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80'
            ],
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
            'featured': True,
            'timezone': 'America/New_York'
        },
        {
            'name': 'Indoor Pro Arena',
            'address': {
                'street': '456 Sports Way',
                'city': 'Chicago',
                'state': 'IL',
                'zip': '60614',
                'formatted': '456 Sports Way, Chicago, IL 60614'
            },
            'is_indoor': True,
            'surface_type': 'wood',
            'description': 'Professional-grade indoor volleyball courts with state-of-the-art facilities. Host to regional tournaments.',
            'amenities': ['locker rooms', 'showers', 'pro shop', 'gym', 'restaurant'],
            'images': [
                'https://images.unsplash.com/photo-1577412647305-991150c7d163?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80'
            ],
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
            'featured': True,
            'timezone': 'America/Chicago'
        },
        {
            'name': 'University Recreation Center',
            'address': {
                'street': '200 Campus Drive',
                'city': 'Austin',
                'state': 'TX',
                'zip': '78712',
                'formatted': '200 Campus Drive, Austin, TX 78712'
            },
            'is_indoor': True,
            'surface_type': 'synthetic',
            'description': 'A modern volleyball facility located on the university campus. Available to students and the public.',
            'amenities': ['water fountains', 'restrooms', 'parking', 'equipment rental'],
            'images': [
                'https://images.unsplash.com/photo-1543473246-7ee497b58f59?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80'
            ],
            'operating_hours': {
                'monday': {'is_open': True, 'open': '07:00', 'close': '21:00'},
                'tuesday': {'is_open': True, 'open': '07:00', 'close': '21:00'},
                'wednesday': {'is_open': True, 'open': '07:00', 'close': '21:00'},
                'thursday': {'is_open': True, 'open': '07:00', 'close': '21:00'},
                'friday': {'is_open': True, 'open': '07:00', 'close': '21:00'},
                'saturday': {'is_open': True, 'open': '09:00', 'close': '18:00'},
                'sunday': {'is_open': True, 'open': '09:00', 'close': '18:00'}
            },
            'coordinates': {'latitude': 30.2672, 'longitude': -97.7431},
            'status': 'active',
            'featured': False,
            'timezone': 'America/Chicago'
        },
        {
            'name': 'Santa Monica Beach Courts',
            'address': {
                'street': '1600 Ocean Front Walk',
                'city': 'Santa Monica',
                'state': 'CA',
                'zip': '90401',
                'formatted': '1600 Ocean Front Walk, Santa Monica, CA 90401'
            },
            'is_indoor': False,
            'surface_type': 'sand',
            'description': 'Iconic beach volleyball courts on the Santa Monica shoreline. Popular spot for professionals and amateurs alike.',
            'amenities': ['showers', 'restrooms', 'equipment rental', 'beach access'],
            'images': [
                'https://images.unsplash.com/photo-1610386715166-0e22d3c40832?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80'
            ],
            'operating_hours': {
                'monday': {'is_open': True, 'open': '06:00', 'close': '22:00'},
                'tuesday': {'is_open': True, 'open': '06:00', 'close': '22:00'},
                'wednesday': {'is_open': True, 'open': '06:00', 'close': '22:00'},
                'thursday': {'is_open': True, 'open': '06:00', 'close': '22:00'},
                'friday': {'is_open': True, 'open': '06:00', 'close': '22:00'},
                'saturday': {'is_open': True, 'open': '06:00', 'close': '22:00'},
                'sunday': {'is_open': True, 'open': '06:00', 'close': '22:00'}
            },
            'coordinates': {'latitude': 34.0195, 'longitude': -118.4912},
            'status': 'active',
            'featured': True,
            'timezone': 'America/Los_Angeles'
        },
        {
            'name': 'Green Park Community Center',
            'address': {
                'street': '789 Park Avenue',
                'city': 'Seattle',
                'state': 'WA',
                'zip': '98101',
                'formatted': '789 Park Avenue, Seattle, WA 98101'
            },
            'is_indoor': True,
            'surface_type': 'rubber',
            'description': 'Community volleyball courts designed for all skill levels. Offers programs for youth and adults.',
            'amenities': ['restrooms', 'water fountains', 'parking', 'handicap accessible'],
            'images': [
                'https://images.unsplash.com/photo-1612872087720-bb876e2e67d1?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80'
            ],
            'operating_hours': {
                'monday': {'is_open': True, 'open': '09:00', 'close': '20:00'},
                'tuesday': {'is_open': True, 'open': '09:00', 'close': '20:00'},
                'wednesday': {'is_open': True, 'open': '09:00', 'close': '20:00'},
                'thursday': {'is_open': True, 'open': '09:00', 'close': '20:00'},
                'friday': {'is_open': True, 'open': '09:00', 'close': '20:00'},
                'saturday': {'is_open': True, 'open': '10:00', 'close': '18:00'},
                'sunday': {'is_open': True, 'open': '10:00', 'close': '18:00'}
            },
            'coordinates': {'latitude': 47.6062, 'longitude': -122.3321},
            'status': 'active',
            'featured': False,
            'timezone': 'America/Los_Angeles'
        }
    ]
    
    created_courts = []
    for court_data in courts:
        # Check if court already exists
        existing_courts = db.collection('courts').where('name', '==', court_data['name']).limit(1).get()
        
        if len(list(existing_courts)) > 0:
            court_id = existing_courts[0].id
            print(f"Court '{court_data['name']}' already exists with ID: {court_id}")
            
            # Update the court data
            db.collection('courts').document(court_id).update({
                **court_data,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            created_courts.append(court_id)
        else:
            # Create new court
            court_data['created_at'] = firestore.SERVER_TIMESTAMP
            court_data['updated_at'] = firestore.SERVER_TIMESTAMP
            
            new_court = db.collection('courts').add(court_data)
            court_id = new_court[1].id
            print(f"Created court '{court_data['name']}' with ID: {court_id}")
            
            created_courts.append(court_id)
    
    return created_courts

def create_reservations(db, user_ids, court_ids):
    """Create sample reservations for courts"""
    print("Creating reservations...")
    
    # Only create reservations if we have users and courts
    if not user_ids or not court_ids:
        print("Cannot create reservations: no users or courts available")
        return
    
    # Create reservations for the next 7 days
    now = datetime.now(pytz.UTC)
    
    reservations = []
    for day in range(7):
        # Create 3-5 reservations per day across different courts
        num_reservations = random.randint(3, 5)
        
        for _ in range(num_reservations):
            court_id = random.choice(court_ids)
            user_id = random.choice(user_ids)
            
            # Random hour between 10 AM and 8 PM
            hour = random.randint(10, 20)
            
            reservation_date = now.date() + timedelta(days=day)
            start_time = datetime.combine(reservation_date, datetime.min.time(), tzinfo=pytz.UTC).replace(hour=hour)
            end_time = start_time + timedelta(hours=1)
            
            # Get the court's timezone if available
            court_ref = db.collection('courts').document(court_id).get()
            court_timezone = 'UTC'
            if court_ref.exists:
                court_data = court_ref.to_dict()
                if 'timezone' in court_data:
                    court_timezone = court_data['timezone']
            
            reservation_data = {
                'court_id': court_id,
                'user_id': user_id,
                'start_time': start_time,
                'end_time': end_time,
                'status': 'confirmed',
                'notes': 'Sample reservation created by populate_db.py script',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP,
                'timezone': court_timezone,
                'date': start_time.strftime('%Y-%m-%d')
            }
            
            # Add to Firestore
            new_reservation = db.collection('reservations').add(reservation_data)
            print(f"Created reservation for court {court_id} on {start_time.strftime('%Y-%m-%d %H:%M')}")
            
            reservations.append(new_reservation[1].id)
    
    return reservations

def create_maintenance_windows(db, court_ids):
    """Create sample maintenance windows for courts"""
    print("Creating maintenance windows...")
    
    if not court_ids:
        print("Cannot create maintenance windows: no courts available")
        return
    
    # Create a few maintenance windows for random courts
    now = datetime.now(pytz.UTC)
    
    maintenance_windows = []
    for court_id in random.sample(court_ids, min(2, len(court_ids))):
        # Maintenance starts in the future
        start_day = random.randint(1, 10)
        maintenance_date = now.date() + timedelta(days=start_day)
        
        start_time = datetime.combine(maintenance_date, datetime.min.time(), tzinfo=pytz.UTC).replace(hour=8)
        end_time = start_time + timedelta(hours=random.choice([2, 4, 8]))
        
        # Get the court's timezone if available
        court_ref = db.collection('courts').document(court_id).get()
        court_timezone = 'UTC'
        if court_ref.exists:
            court_data = court_ref.to_dict()
            if 'timezone' in court_data:
                court_timezone = court_data['timezone']
        
        maintenance_data = {
            'court_id': court_id,
            'start_time': start_time,
            'end_time': end_time,
            'description': f'Routine maintenance - {random.choice(["Court cleaning", "Equipment replacement", "Surface repair"])}',
            'status': 'scheduled',
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'timezone': court_timezone,
            'date': start_time.strftime('%Y-%m-%d')
        }
        
        # Add to Firestore
        new_maintenance = db.collection('maintenance').add(maintenance_data)
        print(f"Created maintenance window for court {court_id} from {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")
        
        maintenance_windows.append(new_maintenance[1].id)
    
    return maintenance_windows

def create_waitlist_entries(db, user_ids, court_ids):
    """Create sample waitlist entries for courts"""
    print("Creating waitlist entries...")
    
    if not user_ids or not court_ids:
        print("Cannot create waitlist entries: no users or courts available")
        return
    
    now = datetime.now(pytz.UTC)
    
    waitlist_entries = []
    # Create waitlist entries for some busy times
    for day in range(3):
        court_id = random.choice(court_ids)
        
        # Create entries for popular evening times
        busy_hour = random.choice([17, 18, 19])  # 5 PM, 6 PM, or 7 PM
        busy_time = now + timedelta(days=day)
        busy_time = busy_time.replace(hour=busy_hour, minute=0, second=0, microsecond=0)
        
        # Get the court's timezone if available
        court_ref = db.collection('courts').document(court_id).get()
        court_timezone = 'UTC'
        if court_ref.exists:
            court_data = court_ref.to_dict()
            if 'timezone' in court_data:
                court_timezone = court_data['timezone']
        
        # Add a few users to the waitlist
        for user_id in random.sample(user_ids, min(3, len(user_ids))):
            waitlist_data = {
                'court_id': court_id,
                'user_id': user_id,
                'preferred_date': busy_time.strftime('%Y-%m-%d'),  # Store as string
                'preferred_time': busy_time.strftime('%H:%M'),
                'start_time': busy_time.strftime('%H:%M'),
                'end_time': (busy_time + timedelta(hours=1)).strftime('%H:%M'),
                'status': 'active',
                'notes': f'Preferred duration: {random.choice(["1 hour", "2 hours"])}',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP,
                'timezone': court_timezone,
                'notification_preference': random.choice(['email', 'sms', 'both'])
            }
            
            # Add to Firestore
            new_waitlist = db.collection('waitlist').add(waitlist_data)
            print(f"Created waitlist entry for user {user_id} for court {court_id} on {busy_time.strftime('%Y-%m-%d')} at {busy_time.strftime('%H:%M')}")
            
            waitlist_entries.append(new_waitlist[1].id)
    
    return waitlist_entries

def main():
    """Main function to populate the database"""
    try:
        db = initialize_firebase()
        
        # Create users first
        user_ids = create_users(db)
        
        # Create courts
        court_ids = create_courts(db)
        
        # Create reservations
        create_reservations(db, user_ids, court_ids)
        
        # Create maintenance windows
        create_maintenance_windows(db, court_ids)
        
        # Create waitlist entries
        create_waitlist_entries(db, user_ids, court_ids)
        
        print("\nDatabase population completed successfully!")
        print(f"Created {len(user_ids)} users")
        print(f"Created {len(court_ids)} courts")
        
    except Exception as e:
        print(f"Error populating database: {e}")

if __name__ == "__main__":
    main() 