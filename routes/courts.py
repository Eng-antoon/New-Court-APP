from flask import Blueprint, request, jsonify, current_app
from firebase_admin import firestore, storage
import uuid
from datetime import datetime, timedelta
import pytz
from routes.auth import token_required, admin_required
import validators
import re
import math
import difflib

courts_bp = Blueprint('courts', __name__)
db = firestore.client()
bucket = storage.bucket()

@courts_bp.route('', methods=['GET'])
def get_courts():
    try:
        # Get query parameters
        search_query = request.args.get('search', '').lower()
        surface_type = request.args.get('surface')
        is_indoor = request.args.get('indoor')
        has_amenities = request.args.get('amenities')
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))
        
        # Base query
        query = db.collection('courts')
        
        # Apply filters if provided
        if surface_type:
            query = query.where('surface_type', '==', surface_type)
        
        if is_indoor and is_indoor.lower() in ['true', 'false']:
            is_indoor_bool = is_indoor.lower() == 'true'
            query = query.where('is_indoor', '==', is_indoor_bool)
        
        if has_amenities:
            amenities_list = has_amenities.split(',')
            # Firestore doesn't support OR queries directly, so we'll filter after fetching
            
        # Execute query
        courts = []
        court_docs = query.limit(limit).offset(offset).get()
        
        for doc in court_docs:
            court_data = doc.to_dict()
            court_data['id'] = doc.id
            
            # Filter by search query if provided
            if search_query:
                name = court_data.get('name', '').lower()
                address = court_data.get('address', {}).get('formatted', '').lower()
                description = court_data.get('description', '').lower()
                
                if not (search_query in name or search_query in address or search_query in description):
                    continue
            
            # Filter by amenities if provided
            if has_amenities:
                court_amenities = set(court_data.get('amenities', []))
                if not all(amenity in court_amenities for amenity in amenities_list):
                    continue
            
            courts.append(court_data)
        
        # Get total count for pagination
        # Note: This is inefficient for large collections
        total_query = db.collection('courts')
        total = len(list(total_query.get()))
        
        return jsonify({
            'courts': courts,
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving courts: {str(e)}'}), 500

@courts_bp.route('/<court_id>', methods=['GET'])
def get_court(court_id):
    try:
        court_ref = db.collection('courts').document(court_id)
        court_doc = court_ref.get()
        
        if not court_doc.exists:
            return jsonify({'message': 'Court not found'}), 404
        
        court_data = court_doc.to_dict()
        court_data['id'] = court_id
        
        # Fetch court availability for the next week
        today = datetime.now(pytz.UTC)
        end_date = today + timedelta(days=7)
        
        availability_ref = (
            db.collection('reservations')
            .where('court_id', '==', court_id)
            .where('start_time', '>=', today)
            .where('start_time', '<=', end_date)
            .get()
        )
        
        reservations = []
        for res_doc in availability_ref:
            res_data = res_doc.to_dict()
            res_data['id'] = res_doc.id
            reservations.append(res_data)
        
        court_data['reservations'] = reservations
        
        # Fetch maintenance windows for the court
        maintenance_ref = (
            db.collection('maintenance')
            .where('court_id', '==', court_id)
            .where('end_time', '>=', today)
            .get()
        )
        
        maintenance_windows = []
        for maint_doc in maintenance_ref:
            maint_data = maint_doc.to_dict()
            maint_data['id'] = maint_doc.id
            maintenance_windows.append(maint_data)
        
        court_data['maintenance'] = maintenance_windows
        
        return jsonify(court_data), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving court: {str(e)}'}), 500

@courts_bp.route('', methods=['POST'])
@admin_required
def create_court():
    try:
        data = request.json
        
        if not data:
            return jsonify({'message': 'No input data provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'address', 'is_indoor', 'surface_type']
        for field in required_fields:
            if field not in data:
                return jsonify({'message': f'Missing required field: {field}'}), 400
        
        # Validate address structure
        address = data.get('address', {})
        if not isinstance(address, dict) or 'formatted' not in address:
            return jsonify({'message': 'Address must include formatted string'}), 400
        
        # Generate court data
        court_data = {
            'name': data['name'],
            'address': address,
            'is_indoor': data['is_indoor'],
            'surface_type': data['surface_type'],
            'description': data.get('description', ''),
            'amenities': data.get('amenities', []),
            'images': data.get('images', []),
            'operating_hours': data.get('operating_hours', {}),
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'status': 'active'
        }
        
        # Add coordinates if provided
        if 'coordinates' in data and 'latitude' in data['coordinates'] and 'longitude' in data['coordinates']:
            court_data['coordinates'] = {
                'latitude': data['coordinates']['latitude'],
                'longitude': data['coordinates']['longitude']
            }
        
        # Create the court in Firestore
        court_ref = db.collection('courts').document()
        court_ref.set(court_data)
        
        # Return the created court
        court_data['id'] = court_ref.id
        
        return jsonify({
            'message': 'Court created successfully',
            'court': court_data
        }), 201
        
    except Exception as e:
        return jsonify({'message': f'Error creating court: {str(e)}'}), 500

@courts_bp.route('/<court_id>', methods=['PUT'])
@admin_required
def update_court(court_id):
    try:
        data = request.json
        
        if not data:
            return jsonify({'message': 'No input data provided'}), 400
        
        # Check if court exists
        court_ref = db.collection('courts').document(court_id)
        court_doc = court_ref.get()
        
        if not court_doc.exists:
            return jsonify({'message': 'Court not found'}), 404
        
        # Update court data
        update_data = {}
        allowed_fields = [
            'name', 'address', 'is_indoor', 'surface_type', 'description',
            'amenities', 'images', 'operating_hours', 'status', 'coordinates'
        ]
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        # Always update the updated_at timestamp
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        
        # Update the court
        court_ref.update(update_data)
        
        # Return the updated court
        updated_court = court_ref.get().to_dict()
        updated_court['id'] = court_id
        
        return jsonify({
            'message': 'Court updated successfully',
            'court': updated_court
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error updating court: {str(e)}'}), 500

@courts_bp.route('/<court_id>', methods=['DELETE'])
@admin_required
def delete_court(court_id):
    try:
        # Check if court exists
        court_ref = db.collection('courts').document(court_id)
        court_doc = court_ref.get()
        
        if not court_doc.exists:
            return jsonify({'message': 'Court not found'}), 404
        
        # Check if there are future reservations for this court
        today = datetime.now(pytz.UTC)
        reservations_ref = (
            db.collection('reservations')
            .where('court_id', '==', court_id)
            .where('start_time', '>=', today)
            .get()
        )
        
        if len(list(reservations_ref)) > 0:
            return jsonify({
                'message': 'Cannot delete court with future reservations',
                'reservations_count': len(list(reservations_ref))
            }), 400
        
        # Delete the court
        court_ref.delete()
        
        return jsonify({
            'message': 'Court deleted successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error deleting court: {str(e)}'}), 500

@courts_bp.route('/<court_id>/images', methods=['POST'])
@admin_required
def upload_court_image(court_id):
    try:
        # Check if court exists
        court_ref = db.collection('courts').document(court_id)
        court_doc = court_ref.get()
        
        if not court_doc.exists:
            return jsonify({'message': 'Court not found'}), 404
        
        # Check if image is in request
        if 'image' not in request.files:
            return jsonify({'message': 'No image provided'}), 400
        
        image_file = request.files['image']
        
        # Validate file type
        if not image_file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            return jsonify({'message': 'Invalid file type. Only PNG, JPG, JPEG, and GIF are allowed'}), 400
        
        # Generate unique filename
        filename = f"courts/{court_id}/{str(uuid.uuid4())}-{image_file.filename}"
        
        # Upload to Firebase Storage
        blob = bucket.blob(filename)
        blob.upload_from_file(image_file)
        
        # Make file publicly accessible
        blob.make_public()
        
        # Get the public URL
        image_url = blob.public_url
        
        # Update court with new image URL
        court_data = court_doc.to_dict()
        images = court_data.get('images', [])
        images.append(image_url)
        
        court_ref.update({
            'images': images,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({
            'message': 'Image uploaded successfully',
            'image_url': image_url
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error uploading image: {str(e)}'}), 500

@courts_bp.route('/<court_id>/images/<image_id>', methods=['DELETE'])
@admin_required
def delete_court_image(court_id, image_id):
    try:
        # Check if court exists
        court_ref = db.collection('courts').document(court_id)
        court_doc = court_ref.get()
        
        if not court_doc.exists:
            return jsonify({'message': 'Court not found'}), 404
        
        # Get the court data
        court_data = court_doc.to_dict()
        images = court_data.get('images', [])
        
        # Find the image URL
        image_urls = [url for url in images if image_id in url]
        
        if not image_urls:
            return jsonify({'message': 'Image not found'}), 404
        
        image_url = image_urls[0]
        
        # Delete from Firebase Storage
        try:
            # Extract filename from URL
            filename = image_url.split('/')[-1]
            storage_path = f"courts/{court_id}/{filename}"
            
            blob = bucket.blob(storage_path)
            blob.delete()
        except Exception as e:
            # Continue even if storage deletion fails
            print(f"Error deleting image from storage: {str(e)}")
        
        # Update court data
        images.remove(image_url)
        court_ref.update({
            'images': images,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({
            'message': 'Image deleted successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error deleting image: {str(e)}'}), 500

@courts_bp.route('/availability', methods=['GET'])
def get_courts_availability():
    try:
        # Get query parameters
        date_str = request.args.get('date')
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')
        
        if not date_str:
            return jsonify({'message': 'Date parameter is required'}), 400
        
        # Parse date and times
        try:
            date_parts = date_str.split('-')
            year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
            
            # Default times if not provided
            start_hour, start_minute = 0, 0
            if start_time_str:
                start_time_parts = start_time_str.split(':')
                start_hour, start_minute = int(start_time_parts[0]), int(start_time_parts[1])
            
            end_hour, end_minute = 23, 59
            if end_time_str:
                end_time_parts = end_time_str.split(':')
                end_hour, end_minute = int(end_time_parts[0]), int(end_time_parts[1])
            
            # Create datetime objects
            start_datetime = datetime(year, month, day, start_hour, start_minute, tzinfo=pytz.UTC)
            end_datetime = datetime(year, month, day, end_hour, end_minute, tzinfo=pytz.UTC)
            
        except (ValueError, IndexError):
            return jsonify({'message': 'Invalid date or time format'}), 400
        
        # Get all courts
        courts_ref = db.collection('courts').get()
        
        # Get reservations for the given time range
        reservations_ref = (
            db.collection('reservations')
            .where('start_time', '>=', start_datetime)
            .where('start_time', '<=', end_datetime)
            .get()
        )
        
        # Get maintenance windows
        maintenance_ref = (
            db.collection('maintenance')
            .where('start_time', '<=', end_datetime)
            .where('end_time', '>=', start_datetime)
            .get()
        )
        
        # Create a dict of court IDs to their availability
        court_availability = {}
        
        # Initialize availability for all courts
        for court_doc in courts_ref:
            court_id = court_doc.id
            court_data = court_doc.to_dict()
            
            # Check operating hours for this day of week
            day_of_week = start_datetime.strftime('%A').lower()
            operating_hours = court_data.get('operating_hours', {}).get(day_of_week, {})
            
            is_open = True
            if operating_hours:
                if not operating_hours.get('is_open', True):
                    is_open = False
            
            court_availability[court_id] = {
                'court_id': court_id,
                'name': court_data.get('name', ''),
                'is_open': is_open,
                'reservations': [],
                'maintenance': [],
                'available_slots': []
            }
        
        # Add reservations to courts
        for res_doc in reservations_ref:
            res_data = res_doc.to_dict()
            court_id = res_data.get('court_id')
            
            if court_id in court_availability:
                court_availability[court_id]['reservations'].append({
                    'id': res_doc.id,
                    'start_time': res_data.get('start_time'),
                    'end_time': res_data.get('end_time'),
                    'status': res_data.get('status')
                })
        
        # Add maintenance windows to courts
        for maint_doc in maintenance_ref:
            maint_data = maint_doc.to_dict()
            court_id = maint_data.get('court_id')
            
            if court_id in court_availability:
                court_availability[court_id]['maintenance'].append({
                    'id': maint_doc.id,
                    'start_time': maint_data.get('start_time'),
                    'end_time': maint_data.get('end_time'),
                    'description': maint_data.get('description', '')
                })
        
        # Calculate available slots for each court
        for court_id, availability in court_availability.items():
            if not availability['is_open']:
                continue
            
            # Get the court data to determine slot duration
            court_ref = db.collection('courts').document(court_id)
            court_data = court_ref.get().to_dict()
            
            # Default slot duration is 60 minutes (1 hour)
            slot_duration_minutes = court_data.get('slot_duration_minutes', 60)
            slot_duration = timedelta(minutes=slot_duration_minutes)
            
            # Get day's operating hours
            day_of_week = start_datetime.strftime('%A').lower()
            operating_hours = court_data.get('operating_hours', {}).get(day_of_week, {})
            
            # Default operating hours is 8 AM to 8 PM
            default_open = datetime(year, month, day, 8, 0, tzinfo=pytz.UTC)
            default_close = datetime(year, month, day, 20, 0, tzinfo=pytz.UTC)
            
            open_time = default_open
            close_time = default_close
            
            if operating_hours:
                # Parse operating hours
                if 'open' in operating_hours and operating_hours['open']:
                    open_parts = operating_hours['open'].split(':')
                    if len(open_parts) == 2:
                        open_hour, open_minute = int(open_parts[0]), int(open_parts[1])
                        open_time = datetime(year, month, day, open_hour, open_minute, tzinfo=pytz.UTC)
                
                if 'close' in operating_hours and operating_hours['close']:
                    close_parts = operating_hours['close'].split(':')
                    if len(close_parts) == 2:
                        close_hour, close_minute = int(close_parts[0]), int(close_parts[1])
                        close_time = datetime(year, month, day, close_hour, close_minute, tzinfo=pytz.UTC)
            
            # Adjust for the requested time range
            open_time = max(open_time, start_datetime)
            close_time = min(close_time, end_datetime)
            
            if open_time >= close_time:
                continue
            
            # Generate all possible slots
            current_time = open_time
            slots = []
            
            while current_time + slot_duration <= close_time:
                slot_end = current_time + slot_duration
                slot_available = True
                
                # Check if slot overlaps with any reservation
                for reservation in availability['reservations']:
                    res_start = reservation['start_time']
                    res_end = reservation['end_time']
                    
                    if (current_time < res_end and slot_end > res_start and 
                        reservation['status'] in ['confirmed', 'pending']):
                        slot_available = False
                        break
                
                # Check if slot overlaps with any maintenance window
                for maintenance in availability['maintenance']:
                    maint_start = maintenance['start_time']
                    maint_end = maintenance['end_time']
                    
                    if current_time < maint_end and slot_end > maint_start:
                        slot_available = False
                        break
                
                if slot_available:
                    slots.append({
                        'start_time': current_time,
                        'end_time': slot_end
                    })
                
                # Move to next slot
                current_time += slot_duration
            
            court_availability[court_id]['available_slots'] = slots
        
        # Convert to list and return
        availability_list = list(court_availability.values())
        
        return jsonify({
            'date': date_str,
            'courts': availability_list
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving availability: {str(e)}'}), 500

@courts_bp.route('/search', methods=['GET'])
def search_courts():
    try:
        # Get query parameters
        query = request.args.get('q', '')
        
        if not query:
            return jsonify({'message': 'Search query is required'}), 400
        
        # Get all courts
        courts_ref = db.collection('courts')
        courts = list(courts_ref.get())
        
        # Perform text search with typo tolerance
        search_results = text_search_courts(query, courts)
        
        # Format results
        formatted_results = []
        for court in search_results:
            court_data = court.to_dict()
            court_data['id'] = court.id
            formatted_results.append(court_data)
        
        return jsonify({
            'courts': formatted_results,
            'total': len(formatted_results),
            'query': query
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error searching courts: {str(e)}'}), 500

def text_search_courts(query, courts):
    """
    Search courts with typo tolerance using fuzzy matching
    
    Args:
        query (str): The search query
        courts (list): List of court documents
        
    Returns:
        list: Matching court documents
    """
    # Normalize query
    query = query.lower()
    query_terms = re.findall(r'\w+', query)
    
    # Store courts with their match scores
    matches = []
    
    for court in courts:
        court_data = court.to_dict()
        
        # Skip inactive courts
        if court_data.get('status') != 'active':
            continue
        
        # Prepare court text for searching
        court_text = ''
        
        # Add court name
        if 'name' in court_data:
            court_text += court_data['name'] + ' '
            
        # Add court description
        if 'description' in court_data:
            court_text += court_data['description'] + ' '
            
        # Add surface type
        if 'surface' in court_data:
            court_text += court_data['surface'] + ' '
            
        # Add address information
        if 'address' in court_data:
            address = court_data['address']
            if isinstance(address, dict):
                for key, value in address.items():
                    if key != 'geo' and value:  # Skip geo coordinates
                        court_text += str(value) + ' '
        
        # Add amenities
        if 'amenities' in court_data and isinstance(court_data['amenities'], list):
            for amenity in court_data['amenities']:
                court_text += amenity + ' '
        
        # Normalize court text
        court_text = court_text.lower()
        
        # Calculate match score
        match_score = calculate_text_match_score(query_terms, court_text)
        
        # Add to matches if score is above threshold
        if match_score > 0.3:  # 30% match threshold
            matches.append((court, match_score))
    
    # Sort by match score (descending)
    matches.sort(key=lambda x: x[1], reverse=True)
    
    # Return just the courts in order of match score
    return [court for court, score in matches]

def calculate_text_match_score(query_terms, text):
    """
    Calculate a match score between query terms and text
    
    Args:
        query_terms (list): List of query terms
        text (str): Text to match against
        
    Returns:
        float: Match score between 0 and 1
    """
    if not query_terms or not text:
        return 0
    
    # Extract text terms
    text_terms = re.findall(r'\w+', text)
    
    # Check for exact matches first
    exact_match_count = 0
    for q_term in query_terms:
        if q_term in text_terms:
            exact_match_count += 1
    
    exact_match_score = exact_match_count / len(query_terms)
    
    # Use fuzzy matching for typo tolerance
    fuzzy_match_scores = []
    for q_term in query_terms:
        best_match = 0
        for t_term in text_terms:
            # Skip very short terms for fuzzy matching
            if len(q_term) < 3 or len(t_term) < 3:
                if q_term == t_term:
                    best_match = 1
                continue
            
            # Calculate similarity ratio
            similarity = difflib.SequenceMatcher(None, q_term, t_term).ratio()
            
            # Consider close matches (>70% similar) as potential typo corrections
            if similarity > 0.7:
                best_match = max(best_match, similarity)
        
        fuzzy_match_scores.append(best_match)
    
    fuzzy_match_score = sum(fuzzy_match_scores) / len(query_terms)
    
    # Combine exact and fuzzy scores, prioritizing exact matches
    final_score = (exact_match_score * 0.7) + (fuzzy_match_score * 0.3)
    
    return final_score

def calculate_distance(lat1, lng1, lat2, lng2):
    """
    Calculate distance between two points using Haversine formula
    
    Args:
        lat1 (float): Latitude of first point
        lng1 (float): Longitude of first point
        lat2 (float): Latitude of second point
        lng2 (float): Longitude of second point
        
    Returns:
        float: Distance in kilometers
    """
    # Radius of the Earth in kilometers
    R = 6371.0
    
    # Convert degrees to radians
    lat1_rad = math.radians(float(lat1))
    lng1_rad = math.radians(float(lng1))
    lat2_rad = math.radians(float(lat2))
    lng2_rad = math.radians(float(lng2))
    
    # Difference in coordinates
    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad
    
    # Haversine formula
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance

@courts_bp.route('/nearby', methods=['GET'])
def find_nearby_courts():
    try:
        # Get query parameters
        lat = request.args.get('lat')
        lng = request.args.get('lng')
        radius = float(request.args.get('radius', 10.0))  # Default 10km radius
        
        if not lat or not lng:
            return jsonify({'message': 'Latitude and longitude are required'}), 400
        
        try:
            lat = float(lat)
            lng = float(lng)
        except ValueError:
            return jsonify({'message': 'Invalid latitude or longitude'}), 400
        
        # Get all courts
        courts_ref = db.collection('courts')
        courts = list(courts_ref.get())
        
        # Calculate distance for each court and filter by radius
        nearby_courts = []
        
        for court in courts:
            court_data = court.to_dict()
            
            # Skip courts without geo coordinates or inactive courts
            if ('address' not in court_data or 
                'geo' not in court_data['address'] or 
                court_data.get('status') != 'active'):
                continue
            
            geo = court_data['address']['geo']
            court_lat = geo.get('lat')
            court_lng = geo.get('lng')
            
            if court_lat is None or court_lng is None:
                continue
            
            # Calculate distance
            distance = calculate_distance(lat, lng, court_lat, court_lng)
            
            # Check if within radius
            if distance <= radius:
                court_data['id'] = court.id
                court_data['distance'] = round(distance, 1)  # Round to 1 decimal place
                nearby_courts.append(court_data)
        
        # Sort by distance
        nearby_courts.sort(key=lambda x: x['distance'])
        
        return jsonify({
            'courts': nearby_courts,
            'total': len(nearby_courts),
            'center': {'lat': lat, 'lng': lng},
            'radius': radius
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error finding nearby courts: {str(e)}'}), 500 