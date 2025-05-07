from flask import Blueprint, request, jsonify, current_app
from firebase_admin import firestore
from datetime import datetime, timedelta
import pytz
from routes.auth import token_required, admin_required
import uuid

reservations_bp = Blueprint('reservations', __name__)
db = firestore.client()

@reservations_bp.route('', methods=['GET'])
@token_required
def get_reservations():
    try:
        # Get query parameters
        user_id = request.args.get('user_id')
        court_id = request.args.get('court_id')
        status = request.args.get('status')
        from_date_str = request.args.get('from_date')
        to_date_str = request.args.get('to_date')
        date_str = request.args.get('date')  # Single date filter
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))
        timezone = request.args.get('timezone', 'UTC')
        
        # Check if user is requesting own reservations or has admin privileges
        if user_id and user_id != request.user['id'] and request.user['role'] not in ['admin', 'owner']:
            return jsonify({'message': 'Not authorized to view other users\' reservations'}), 403
        
        # Base query
        query = db.collection('reservations')
        
        # Apply filters if provided
        if user_id:
            query = query.where('user_id', '==', user_id)
            
        if court_id:
            query = query.where('court_id', '==', court_id)
            
        if status:
            query = query.where('status', '==', status)
        
        # If exact date is provided, use it (more efficient than date range)
        if date_str:
            try:
                # Validate date format
                datetime.strptime(date_str, '%Y-%m-%d')
                # Use the date string field for filtering
                query = query.where('date', '==', date_str)
            except (ValueError, IndexError):
                return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400
        else:
            # Parse date range if provided
            if from_date_str:
                try:
                    from_date_parts = from_date_str.split('-')
                    from_date = datetime(
                        int(from_date_parts[0]), 
                        int(from_date_parts[1]), 
                        int(from_date_parts[2]), 
                        0, 0, 0, 
                        tzinfo=pytz.UTC
                    )
                    query = query.where('start_time', '>=', from_date)
                except (ValueError, IndexError):
                    return jsonify({'message': 'Invalid from_date format. Use YYYY-MM-DD.'}), 400
            
            if to_date_str:
                try:
                    to_date_parts = to_date_str.split('-')
                    to_date = datetime(
                        int(to_date_parts[0]), 
                        int(to_date_parts[1]), 
                        int(to_date_parts[2]), 
                        23, 59, 59, 
                        tzinfo=pytz.UTC
                    )
                    query = query.where('start_time', '<=', to_date)
                except (ValueError, IndexError):
                    return jsonify({'message': 'Invalid to_date format. Use YYYY-MM-DD.'}), 400
        
        # Order by start time (newest first)
        query = query.order_by('start_time', direction=firestore.Query.DESCENDING)
        
        # Execute query with pagination
        reservations = []
        reservation_docs = query.limit(limit).offset(offset).get()
        
        for doc in reservation_docs:
            reservation_data = doc.to_dict()
            reservation_data['id'] = doc.id
            
            # Get court details
            if 'court_id' in reservation_data:
                court_ref = db.collection('courts').document(reservation_data['court_id']).get()
                if court_ref.exists:
                    court_data = court_ref.to_dict()
                    reservation_data['court'] = {
                        'id': reservation_data['court_id'],
                        'name': court_data.get('name', ''),
                        'address': court_data.get('address', {})
                    }
                    
                    # Use court timezone if available and no timezone specified
                    if 'timezone' in court_data and timezone == 'UTC':
                        timezone = court_data.get('timezone')
            
            # Get user details (if admin)
            if 'user_id' in reservation_data and request.user['role'] in ['admin', 'owner']:
                user_ref = db.collection('users').document(reservation_data['user_id']).get()
                if user_ref.exists:
                    user_data = user_ref.to_dict()
                    reservation_data['user'] = {
                        'id': reservation_data['user_id'],
                        'name': user_data.get('name', ''),
                        'email': user_data.get('email', '')
                    }
            
            # Convert times to requested timezone
            if 'start_time' in reservation_data and reservation_data['start_time']:
                try:
                    tz = pytz.timezone(timezone)
                    start_time_utc = reservation_data['start_time']
                    start_time_local = start_time_utc.astimezone(tz)
                    reservation_data['start_time_local'] = start_time_local.isoformat()
                except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
                    reservation_data['start_time_local'] = reservation_data['start_time'].isoformat() if hasattr(reservation_data['start_time'], 'isoformat') else reservation_data['start_time']
            
            if 'end_time' in reservation_data and reservation_data['end_time']:
                try:
                    tz = pytz.timezone(timezone)
                    end_time_utc = reservation_data['end_time']
                    end_time_local = end_time_utc.astimezone(tz)
                    reservation_data['end_time_local'] = end_time_local.isoformat()
                except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
                    reservation_data['end_time_local'] = reservation_data['end_time'].isoformat() if hasattr(reservation_data['end_time'], 'isoformat') else reservation_data['end_time']
            
            reservations.append(reservation_data)
        
        # Get total count for pagination
        # Note: This is inefficient for large collections
        total_query = db.collection('reservations')
        if user_id:
            total_query = total_query.where('user_id', '==', user_id)
        if court_id:
            total_query = total_query.where('court_id', '==', court_id)
        if status:
            total_query = total_query.where('status', '==', status)
        if date_str:
            total_query = total_query.where('date', '==', date_str)
            
        total = len(list(total_query.get()))
        
        return jsonify({
            'reservations': reservations,
            'total': total,
            'limit': limit,
            'offset': offset,
            'timezone': timezone
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving reservations: {str(e)}'}), 500

@reservations_bp.route('/<reservation_id>', methods=['GET'])
@token_required
def get_reservation(current_user, reservation_id):
    try:
        # Get timezone parameter
        timezone = request.args.get('timezone', 'UTC')
        
        # Get reservation
        reservation_ref = db.collection('reservations').document(reservation_id)
        reservation_doc = reservation_ref.get()
        
        if not reservation_doc.exists:
            return jsonify({'message': 'Reservation not found'}), 404
        
        reservation_data = reservation_doc.to_dict()
        reservation_data['id'] = reservation_id
        
        # Check if user is authorized to view this reservation
        if (reservation_data.get('user_id') != current_user['id'] and 
            current_user['role'] not in ['admin', 'owner']):
            return jsonify({'message': 'Not authorized to view this reservation'}), 403
        
        # Get court details
        court_timezone = 'UTC'
        if 'court_id' in reservation_data:
            court_ref = db.collection('courts').document(reservation_data['court_id']).get()
            if court_ref.exists:
                court_data = court_ref.to_dict()
                reservation_data['court'] = {
                    'id': reservation_data['court_id'],
                    'name': court_data.get('name', ''),
                    'address': court_data.get('address', {})
                }
                
                # Use court timezone if available and no timezone specified
                if 'timezone' in court_data and timezone == 'UTC':
                    court_timezone = court_data.get('timezone')
                    timezone = court_timezone
        
        # Get user details (if admin)
        if 'user_id' in reservation_data and current_user['role'] in ['admin', 'owner']:
            user_ref = db.collection('users').document(reservation_data['user_id']).get()
            if user_ref.exists:
                user_data = user_ref.to_dict()
                reservation_data['user'] = {
                    'id': reservation_data['user_id'],
                    'name': user_data.get('name', ''),
                    'email': user_data.get('email', '')
                }
        
        # Convert times to requested timezone
        if 'start_time' in reservation_data and reservation_data['start_time']:
            try:
                tz = pytz.timezone(timezone)
                start_time_utc = reservation_data['start_time']
                start_time_local = start_time_utc.astimezone(tz)
                reservation_data['start_time_local'] = start_time_local.isoformat()
            except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
                reservation_data['start_time_local'] = reservation_data['start_time'].isoformat() if hasattr(reservation_data['start_time'], 'isoformat') else reservation_data['start_time']
        
        if 'end_time' in reservation_data and reservation_data['end_time']:
            try:
                tz = pytz.timezone(timezone)
                end_time_utc = reservation_data['end_time']
                end_time_local = end_time_utc.astimezone(tz)
                reservation_data['end_time_local'] = end_time_local.isoformat()
            except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
                reservation_data['end_time_local'] = reservation_data['end_time'].isoformat() if hasattr(reservation_data['end_time'], 'isoformat') else reservation_data['end_time']
        
        return jsonify(reservation_data), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving reservation: {str(e)}'}), 500

@reservations_bp.route('', methods=['POST'])
@token_required
def create_reservation(current_user):
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['court_id', 'date', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data:
                return jsonify({'message': f'Missing required field: {field}'}), 400
        
        # Validate and parse date and times
        try:
            date_parts = data['date'].split('-')
            date_obj = datetime(
                int(date_parts[0]),
                int(date_parts[1]),
                int(date_parts[2])
            ).date()
            
            # Keep original date string for storage
            date_str = data['date']
            
            start_time_parts = data['start_time'].split(':')
            start_time = datetime.combine(
                date_obj,
                datetime.min.time().replace(
                    hour=int(start_time_parts[0]), 
                    minute=int(start_time_parts[1])
                ),
                tzinfo=pytz.UTC
            )
            
            end_time_parts = data['end_time'].split(':')
            end_time = datetime.combine(
                date_obj,
                datetime.min.time().replace(
                    hour=int(end_time_parts[0]), 
                    minute=int(end_time_parts[1])
                ),
                tzinfo=pytz.UTC
            )
        except (ValueError, IndexError):
            return jsonify({'message': 'Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time.'}), 400
        
        # Get court info
        court_ref = db.collection('courts').document(data['court_id'])
        court_doc = court_ref.get()
        
        if not court_doc.exists:
            return jsonify({'message': 'Court not found'}), 404
        
        court_data = court_doc.to_dict()
        
        # Get court timezone if available
        court_timezone = court_data.get('timezone', 'UTC')
        
        # Create reservation data
        reservation_data = {
            'court_id': data['court_id'],
            'user_id': current_user['id'],
            'date': date_str,  # Store date as string for easy filtering
            'start_time': start_time,
            'end_time': end_time,
            'status': data.get('status', 'pending'),
            'notes': data.get('notes', ''),
            'players': data.get('players', []),
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'timezone': court_timezone
        }
        
        # Create reservation in a transaction to check for conflicts
        reservation_ref = db.collection('reservations').document()
        
        @firestore.transactional
        def create_in_transaction(transaction, reservation_ref):
            # Check for overlapping reservations
            # Get reservations for the same court and date with overlapping times
            overlapping_query = db.collection('reservations')\
                .where('court_id', '==', data['court_id'])\
                .where('date', '==', date_str)\
                .where('status', 'in', ['confirmed', 'pending'])
            
            overlapping_reservations = list(overlapping_query.get())
            
            for res_doc in overlapping_reservations:
                res_data = res_doc.to_dict()
                res_start = res_data.get('start_time')
                res_end = res_data.get('end_time')
                
                # Check for overlap: new start time is before existing end time AND new end time is after existing start time
                if (res_start and res_end and 
                    start_time < res_end and 
                    end_time > res_start):
                    return {
                        'error': 'Reservation time conflicts with an existing reservation',
                        'reservation_id': res_doc.id,
                        'time': f"{res_start.strftime('%H:%M')} - {res_end.strftime('%H:%M')}"
                    }
            
            # Check for maintenance windows
            maintenance_query = db.collection('maintenance')\
                .where('court_id', '==', data['court_id'])\
                .where('date', '==', date_str)\
                .where('status', '==', 'scheduled')
            
            maintenance_windows = list(maintenance_query.get())
            
            for maint_doc in maintenance_windows:
                maint_data = maint_doc.to_dict()
                maint_start = maint_data.get('start_time')
                maint_end = maint_data.get('end_time')
                
                # Check for overlap with maintenance
                if (maint_start and maint_end and 
                    start_time < maint_end and 
                    end_time > maint_start):
                    return {
                        'error': 'Reservation time conflicts with scheduled maintenance',
                        'maintenance_id': maint_doc.id,
                        'time': f"{maint_start.strftime('%H:%M')} - {maint_end.strftime('%H:%M')}"
                    }
            
            # Check court operating hours
            day_of_week = date_obj.strftime('%A').lower()
            operating_hours = court_data.get('operating_hours', {}).get(day_of_week, {})
            
            if operating_hours:
                is_open = operating_hours.get('is_open', True)
                
                if not is_open:
                    return {'error': f'Court is closed on {day_of_week.capitalize()}'}
                
                if 'open' in operating_hours and 'close' in operating_hours:
                    open_parts = operating_hours['open'].split(':')
                    close_parts = operating_hours['close'].split(':')
                    
                    try:
                        open_hour, open_minute = int(open_parts[0]), int(open_parts[1])
                        close_hour, close_minute = int(close_parts[0]), int(close_parts[1])
                        
                        open_time = datetime.combine(
                            date_obj, 
                            datetime.min.time().replace(hour=open_hour, minute=open_minute),
                            tzinfo=pytz.UTC
                        )
                        
                        close_time = datetime.combine(
                            date_obj,
                            datetime.min.time().replace(hour=close_hour, minute=close_minute),
                            tzinfo=pytz.UTC
                        )
                        
                        # Handle closing after midnight
                        if close_hour < open_hour:
                            close_time = close_time + timedelta(days=1)
                        
                        if start_time < open_time or end_time > close_time:
                            return {
                                'error': 'Reservation time is outside court operating hours',
                                'operating_hours': f"{operating_hours['open']} - {operating_hours['close']}"
                            }
                    except (ValueError, IndexError):
                        # If we can't parse the operating hours, don't enforce them
                        pass
            
            # If we get here, it's safe to create the reservation
            transaction.set(reservation_ref, reservation_data)
            return {'success': True}
        
        # Run the transaction
        transaction = db.transaction()
        result = create_in_transaction(transaction, reservation_ref)
        
        if 'error' in result:
            return jsonify({'message': result['error'], 'details': result}), 409
        
        # If successful, return the reservation data
        reservation_data['id'] = reservation_ref.id
        
        return jsonify({
            'message': 'Reservation created successfully',
            'reservation': reservation_data
        }), 201
        
    except Exception as e:
        return jsonify({'message': f'Error creating reservation: {str(e)}'}), 500

@reservations_bp.route('/<reservation_id>', methods=['PUT'])
@token_required
def update_reservation(current_user, reservation_id):
    try:
        data = request.json
        
        # Get existing reservation
        reservation_ref = db.collection('reservations').document(reservation_id)
        reservation_doc = reservation_ref.get()
        
        if not reservation_doc.exists:
            return jsonify({'message': 'Reservation not found'}), 404
        
        reservation_data = reservation_doc.to_dict()
        
        # Check if user is authorized to update this reservation
        if (reservation_data.get('user_id') != current_user['id'] and 
            current_user['role'] not in ['admin', 'owner']):
            return jsonify({'message': 'Not authorized to update this reservation'}), 403
        
        # Determine which fields can be updated
        allowed_updates = ['status', 'notes', 'players']
        
        # Admins can update more fields
        if current_user['role'] in ['admin', 'owner']:
            allowed_updates.extend(['date', 'start_time', 'end_time', 'user_id'])
        
        # Handle updates that require validation
        update_data = {}
        time_updated = False
        
        for field in allowed_updates:
            if field in data:
                if field == 'date':
                    # Validate date format
                    try:
                        datetime.strptime(data['date'], '%Y-%m-%d')
                        update_data['date'] = data['date']
                        time_updated = True
                    except ValueError:
                        return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400
                elif field in ['start_time', 'end_time']:
                    # Handle time updates separately to validate conflict in transaction
                    time_updated = True
                else:
                    update_data[field] = data[field]
        
        # If times are being updated, validate conflicts
        if time_updated and current_user['role'] in ['admin', 'owner']:
            # TODO: Implement conflict validation for time changes
            # This would be similar to the create reservation logic
            pass
        
        # Update the timestamp
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        
        # Update the reservation
        reservation_ref.update(update_data)
        
        # Get the updated data
        updated_reservation = reservation_ref.get().to_dict()
        updated_reservation['id'] = reservation_id
        
        return jsonify({
            'message': 'Reservation updated successfully',
            'reservation': updated_reservation
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error updating reservation: {str(e)}'}), 500

@reservations_bp.route('/<reservation_id>/cancel', methods=['POST'])
@token_required
def cancel_reservation(current_user, reservation_id):
    try:
        # Get the reservation
        reservation_ref = db.collection('reservations').document(reservation_id)
        reservation_doc = reservation_ref.get()
        
        if not reservation_doc.exists:
            return jsonify({'message': 'Reservation not found'}), 404
        
        reservation_data = reservation_doc.to_dict()
        
        # Check if user is authorized to cancel this reservation
        if (reservation_data.get('user_id') != current_user['id'] and 
            current_user['role'] not in ['admin', 'owner']):
            return jsonify({'message': 'Not authorized to cancel this reservation'}), 403
        
        # Check if reservation is already cancelled
        if reservation_data.get('status') == 'cancelled':
            return jsonify({'message': 'Reservation is already cancelled'}), 400
        
        # Get cancellation reason if provided
        data = request.json or {}
        cancellation_reason = data.get('reason', '')
        
        # Update reservation status
        update_data = {
            'status': 'cancelled',
            'cancellation_reason': cancellation_reason,
            'cancelled_at': firestore.SERVER_TIMESTAMP,
            'cancelled_by': current_user['id'],
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        reservation_ref.update(update_data)
        
        # Get updated reservation
        updated_reservation = reservation_ref.get().to_dict()
        updated_reservation['id'] = reservation_id
        
        # Check for waitlist entries for this time slot
        court_id = reservation_data.get('court_id')
        date_str = reservation_data.get('date')
        
        if court_id and date_str:
            # Find active waitlist entries for this court and date
            waitlist_query = db.collection('waitlist')\
                .where('court_id', '==', court_id)\
                .where('preferred_date', '==', date_str)\
                .where('status', '==', 'active')
                
            waitlist_entries = list(waitlist_query.get())
            
            if waitlist_entries:
                # This would be processed by a background job in a real system
                # Here we'll just note that there are waitlist entries to process
                updated_reservation['waitlist_entries'] = len(waitlist_entries)
        
        return jsonify({
            'message': 'Reservation cancelled successfully',
            'reservation': updated_reservation
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error cancelling reservation: {str(e)}'}), 500

@reservations_bp.route('/waitlist', methods=['POST'])
@token_required
def join_waitlist(current_user):
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['court_id', 'date', 'preferred_time']
        for field in required_fields:
            if field not in data:
                return jsonify({'message': f'Missing required field: {field}'}), 400
        
        # Validate date and time formats
        try:
            # Validate date format
            date_obj = datetime.strptime(data['date'], '%Y-%m-%d').date()
            
            # Validate time format
            time_parts = data['preferred_time'].split(':')
            time_obj = datetime.min.time().replace(
                hour=int(time_parts[0]),
                minute=int(time_parts[1])
            )
        except (ValueError, IndexError):
            return jsonify({'message': 'Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time.'}), 400
        
        # Get court info
        court_ref = db.collection('courts').document(data['court_id'])
        court_doc = court_ref.get()
        
        if not court_doc.exists:
            return jsonify({'message': 'Court not found'}), 404
        
        court_data = court_doc.to_dict()
        
        # Get court timezone if available
        court_timezone = court_data.get('timezone', 'UTC')
        
        # Create waitlist entry
        waitlist_data = {
            'court_id': data['court_id'],
            'user_id': current_user['id'],
            'preferred_date': data['date'],
            'preferred_time': data['preferred_time'],
            'status': 'active',
            'notes': data.get('notes', ''),
            'notification_preference': data.get('notification_preference', 'email'),
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'timezone': court_timezone
        }
        
        # Add to Firestore
        waitlist_ref = db.collection('waitlist').document()
        waitlist_ref.set(waitlist_data)
        
        # Return the waitlist entry
        waitlist_data['id'] = waitlist_ref.id
        
        return jsonify({
            'message': 'Added to waitlist successfully',
            'waitlist_entry': waitlist_data
        }), 201
        
    except Exception as e:
        return jsonify({'message': f'Error joining waitlist: {str(e)}'}), 500

@reservations_bp.route('/waitlist', methods=['GET'])
@token_required
def get_waitlist(current_user):
    try:
        # Get query parameters
        court_id = request.args.get('court_id')
        date = request.args.get('date')
        status = request.args.get('status', 'active')
        
        # Base query - filter by current user unless admin
        if current_user['role'] in ['admin', 'owner']:
            query = db.collection('waitlist')
            
            # Apply filters if provided
            if court_id:
                query = query.where('court_id', '==', court_id)
        else:
            # Regular users can only see their own waitlist entries
            query = db.collection('waitlist').where('user_id', '==', current_user['id'])
            
            # Apply additional filters
            if court_id:
                query = query.where('court_id', '==', court_id)
        
        # Apply date filter if provided
        if date:
            query = query.where('preferred_date', '==', date)
        
        # Apply status filter
        if status:
            query = query.where('status', '==', status)
        
        # Execute query
        waitlist_entries = []
        for doc in query.stream():
            entry = doc.to_dict()
            entry['id'] = doc.id
            
            # Get court details
            if 'court_id' in entry:
                court_ref = db.collection('courts').document(entry['court_id']).get()
                if court_ref.exists:
                    court_data = court_ref.to_dict()
                    entry['court'] = {
                        'id': entry['court_id'],
                        'name': court_data.get('name', ''),
                        'address': court_data.get('address', {})
                    }
            
            # Get user details (if admin)
            if 'user_id' in entry and current_user['role'] in ['admin', 'owner']:
                user_ref = db.collection('users').document(entry['user_id']).get()
                if user_ref.exists:
                    user_data = user_ref.to_dict()
                    entry['user'] = {
                        'id': entry['user_id'],
                        'name': user_data.get('name', ''),
                        'email': user_data.get('email', '')
                    }
            
            waitlist_entries.append(entry)
        
        return jsonify({
            'waitlist_entries': waitlist_entries,
            'total': len(waitlist_entries)
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving waitlist: {str(e)}'}), 500 