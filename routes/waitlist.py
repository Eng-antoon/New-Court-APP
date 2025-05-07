from flask import Blueprint, request, jsonify
from firebase_admin import firestore
import pytz
from datetime import datetime
from routes.auth import token_required

# Create the blueprint
waitlist_bp = Blueprint('waitlist', __name__)
db = firestore.client()

@waitlist_bp.route('/', methods=['GET'])
@token_required
def get_waitlist_entries(current_user):
    """Get waitlist entries, optionally filtered by court_id or user_id"""
    try:
        # Query parameters
        court_id = request.args.get('court_id')
        user_id = request.args.get('user_id')
        date = request.args.get('date')
        status = request.args.get('status')  # 'active', 'fulfilled', 'cancelled'

        # Start building the query
        query = db.collection('waitlist')

        # Apply filters if provided
        if court_id:
            query = query.where('court_id', '==', court_id)
        if user_id:
            query = query.where('user_id', '==', user_id)
        if date:
            try:
                # Validate date format
                datetime.strptime(date, '%Y-%m-%d')
                # Use the date string directly for the query
                query = query.where('preferred_date', '==', date)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        if status:
            query = query.where('status', '==', status)

        # Execute query
        waitlist_entries = []
        for doc in query.stream():
            entry = doc.to_dict()
            entry['id'] = doc.id
            waitlist_entries.append(entry)

        return jsonify({
            'waitlist_entries': waitlist_entries,
            'total': len(waitlist_entries)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@waitlist_bp.route('/', methods=['POST'])
@token_required
def add_to_waitlist(current_user):
    """Add a user to a court's waitlist for a specific date and time range"""
    try:
        data = request.json
        required_fields = ['court_id', 'date', 'start_time', 'end_time']
        
        # Validate required fields
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Format and validate date and times
        try:
            # Validate date format
            date_obj = datetime.strptime(data['date'], '%Y-%m-%d')
            # Keep date as string for storage
            date_str = data['date']
            
            # Validate time formats
            start_time_obj = datetime.strptime(data['start_time'], '%H:%M').time()
            end_time_obj = datetime.strptime(data['end_time'], '%H:%M').time()
            
            # Keep time as strings for storage
            start_time_str = data['start_time']
            end_time_str = data['end_time']
        except ValueError:
            return jsonify({'error': 'Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time'}), 400
        
        # Get court's timezone if available
        court_timezone = 'UTC'
        court_ref = db.collection('courts').document(data['court_id']).get()
        if court_ref.exists:
            court_data = court_ref.to_dict()
            if 'timezone' in court_data:
                court_timezone = court_data['timezone']
        
        # Create waitlist entry
        waitlist_entry = {
            'user_id': current_user['uid'],
            'court_id': data['court_id'],
            'preferred_date': date_str,
            'start_time': start_time_str,
            'end_time': end_time_str,
            'preferred_time': start_time_str,  # For backward compatibility
            'status': 'active',
            'created_at': datetime.now(pytz.UTC),
            'updated_at': datetime.now(pytz.UTC),
            'notes': data.get('notes', ''),
            'notification_preference': data.get('notification_preference', 'email'),
            'timezone': court_timezone
        }
        
        # Add to Firestore
        new_entry_ref = db.collection('waitlist').document()
        new_entry_id = new_entry_ref.id
        waitlist_entry['id'] = new_entry_id
        
        new_entry_ref.set(waitlist_entry)
        
        return jsonify({
            'message': 'Successfully added to waitlist',
            'waitlist_entry_id': new_entry_id,
            'waitlist_entry': waitlist_entry
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@waitlist_bp.route('/<waitlist_id>', methods=['GET'])
@token_required
def get_waitlist_entry(current_user, waitlist_id):
    """Get a specific waitlist entry"""
    try:
        doc_ref = db.collection('waitlist').document(waitlist_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return jsonify({'error': 'Waitlist entry not found'}), 404
        
        entry = doc.to_dict()
        entry['id'] = waitlist_id
        
        # Check if user is allowed to view this entry
        if entry['user_id'] != current_user['uid'] and current_user['role'] != 'admin':
            return jsonify({'error': 'Unauthorized to view this waitlist entry'}), 403
        
        return jsonify(entry), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@waitlist_bp.route('/<waitlist_id>', methods=['PUT'])
@token_required
def update_waitlist_entry(current_user, waitlist_id):
    """Update a waitlist entry (cancel, change preferences, etc.)"""
    try:
        data = request.json
        doc_ref = db.collection('waitlist').document(waitlist_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return jsonify({'error': 'Waitlist entry not found'}), 404
        
        entry = doc.to_dict()
        
        # Check if user is allowed to update this entry
        if entry['user_id'] != current_user['uid'] and current_user['role'] != 'admin':
            return jsonify({'error': 'Unauthorized to update this waitlist entry'}), 403
        
        # Update allowed fields
        allowed_updates = ['status', 'notes', 'notification_preference', 'preferred_date', 'start_time', 'end_time', 'preferred_time']
        update_data = {}
        
        for field in allowed_updates:
            if field in data:
                # If date or time fields are updated, validate format
                if field == 'preferred_date':
                    try:
                        datetime.strptime(data['preferred_date'], '%Y-%m-%d')
                        update_data['preferred_date'] = data['preferred_date']
                    except ValueError:
                        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
                elif field in ['start_time', 'end_time', 'preferred_time']:
                    try:
                        datetime.strptime(data[field], '%H:%M')
                        update_data[field] = data[field]
                    except ValueError:
                        return jsonify({'error': f'Invalid time format for {field}. Use HH:MM'}), 400
                else:
                    update_data[field] = data[field]
        
        # Add updated timestamp
        update_data['updated_at'] = datetime.now(pytz.UTC)
        
        # Update document
        doc_ref.update(update_data)
        
        # Get updated document
        updated_doc = doc_ref.get()
        updated_entry = updated_doc.to_dict()
        updated_entry['id'] = waitlist_id
        
        return jsonify({
            'message': 'Waitlist entry updated successfully',
            'waitlist_entry': updated_entry
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@waitlist_bp.route('/<waitlist_id>', methods=['DELETE'])
@token_required
def delete_waitlist_entry(current_user, waitlist_id):
    """Delete a waitlist entry"""
    try:
        doc_ref = db.collection('waitlist').document(waitlist_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return jsonify({'error': 'Waitlist entry not found'}), 404
        
        entry = doc.to_dict()
        
        # Check if user is allowed to delete this entry
        if entry['user_id'] != current_user['uid'] and current_user['role'] != 'admin':
            return jsonify({'error': 'Unauthorized to delete this waitlist entry'}), 403
        
        # Delete document
        doc_ref.delete()
        
        return jsonify({
            'message': 'Waitlist entry deleted successfully'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@waitlist_bp.route('/notify', methods=['POST'])
@token_required
def notify_waitlist(current_user):
    """Notify users on the waitlist about availability (admin only)"""
    if current_user['role'] != 'admin':
        return jsonify({'error': 'Unauthorized. Admin access required'}), 403
    
    try:
        data = request.json
        required_fields = ['court_id', 'date', 'available_slots']
        
        # Validate required fields
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate date format
        try:
            datetime.strptime(data['date'], '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Find matching waitlist entries
        query = db.collection('waitlist')\
                .where('court_id', '==', data['court_id'])\
                .where('preferred_date', '==', data['date'])\
                .where('status', '==', 'active')
        
        waitlist_entries = []
        for doc in query.stream():
            entry = doc.to_dict()
            entry['id'] = doc.id
            waitlist_entries.append(entry)
        
        # Process notification logic here
        # This would typically involve sending emails or SMS
        # For this example, we'll just mark them as notified
        
        for entry in waitlist_entries:
            db.collection('waitlist').document(entry['id']).update({
                'notified_at': datetime.now(pytz.UTC),
                'available_slots': data['available_slots'],
                'updated_at': datetime.now(pytz.UTC)
            })
        
        return jsonify({
            'message': f'Notified {len(waitlist_entries)} users on the waitlist',
            'notified_entries': [entry['id'] for entry in waitlist_entries]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500 