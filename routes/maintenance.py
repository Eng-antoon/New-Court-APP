from flask import Blueprint, request, jsonify, current_app
from firebase_admin import firestore
from datetime import datetime, timedelta
import pytz
from routes.auth import token_required, admin_required

maintenance_bp = Blueprint('maintenance', __name__)
db = firestore.client()

@maintenance_bp.route('', methods=['GET'])
@token_required
def get_maintenance_windows():
    try:
        # Get query parameters
        court_id = request.args.get('court_id')
        from_date_str = request.args.get('from_date')
        to_date_str = request.args.get('to_date')
        include_past = request.args.get('include_past', 'false').lower() == 'true'
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))
        
        # Base query
        query = db.collection('maintenance')
        
        # Apply filters if provided
        if court_id:
            query = query.where('court_id', '==', court_id)
        
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
                query = query.where('end_time', '<=', to_date)
            except (ValueError, IndexError):
                return jsonify({'message': 'Invalid to_date format. Use YYYY-MM-DD.'}), 400
        
        # Exclude past maintenance windows unless explicitly included
        if not include_past:
            now = datetime.now(pytz.UTC)
            query = query.where('end_time', '>=', now)
        
        # Order by start time
        query = query.order_by('start_time')
        
        # Execute query with pagination
        maintenance_windows = []
        maintenance_docs = query.limit(limit).offset(offset).get()
        
        for doc in maintenance_docs:
            maintenance_data = doc.to_dict()
            maintenance_data['id'] = doc.id
            
            # Get court details
            if 'court_id' in maintenance_data:
                court_ref = db.collection('courts').document(maintenance_data['court_id']).get()
                if court_ref.exists:
                    court_data = court_ref.to_dict()
                    maintenance_data['court'] = {
                        'id': maintenance_data['court_id'],
                        'name': court_data.get('name', ''),
                        'address': court_data.get('address', {})
                    }
            
            maintenance_windows.append(maintenance_data)
        
        # Get total count for pagination
        # Note: This is inefficient for large collections
        total_query = db.collection('maintenance')
        if court_id:
            total_query = total_query.where('court_id', '==', court_id)
        if not include_past:
            now = datetime.now(pytz.UTC)
            total_query = total_query.where('end_time', '>=', now)
            
        total = len(list(total_query.get()))
        
        return jsonify({
            'maintenance_windows': maintenance_windows,
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving maintenance windows: {str(e)}'}), 500

@maintenance_bp.route('/<maintenance_id>', methods=['GET'])
@token_required
def get_maintenance_window(maintenance_id):
    try:
        # Get maintenance window
        maintenance_ref = db.collection('maintenance').document(maintenance_id)
        maintenance_doc = maintenance_ref.get()
        
        if not maintenance_doc.exists:
            return jsonify({'message': 'Maintenance window not found'}), 404
        
        maintenance_data = maintenance_doc.to_dict()
        maintenance_data['id'] = maintenance_id
        
        # Get court details
        if 'court_id' in maintenance_data:
            court_ref = db.collection('courts').document(maintenance_data['court_id']).get()
            if court_ref.exists:
                court_data = court_ref.to_dict()
                maintenance_data['court'] = {
                    'id': maintenance_data['court_id'],
                    'name': court_data.get('name', ''),
                    'address': court_data.get('address', {})
                }
        
        # Get affected reservations
        start_time = maintenance_data.get('start_time')
        end_time = maintenance_data.get('end_time')
        court_id = maintenance_data.get('court_id')
        
        if start_time and end_time and court_id:
            affected_reservations_query = (
                db.collection('reservations')
                .where('court_id', '==', court_id)
                .where('status', 'in', ['confirmed', 'pending'])
                .get()
            )
            
            affected_reservations = []
            for res_doc in affected_reservations_query:
                res_data = res_doc.to_dict()
                res_start = res_data.get('start_time')
                res_end = res_data.get('end_time')
                
                # Check for overlap
                if res_start < end_time and res_end > start_time:
                    res_data['id'] = res_doc.id
                    affected_reservations.append(res_data)
            
            maintenance_data['affected_reservations'] = affected_reservations
        
        return jsonify(maintenance_data), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving maintenance window: {str(e)}'}), 500

@maintenance_bp.route('', methods=['POST'])
@admin_required
def create_maintenance_window():
    try:
        data = request.json
        
        if not data:
            return jsonify({'message': 'No input data provided'}), 400
        
        # Validate required fields
        required_fields = ['court_id', 'start_time', 'end_time', 'description']
        for field in required_fields:
            if field not in data:
                return jsonify({'message': f'Missing required field: {field}'}), 400
        
        # Parse dates
        try:
            # Check if dates are provided as strings
            if isinstance(data['start_time'], str):
                start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            else:
                start_time = data['start_time']
            
            if isinstance(data['end_time'], str):
                end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            else:
                end_time = data['end_time']
            
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid date format. Use ISO 8601 format.'}), 400
        
        # Validate that end time is after start time
        if end_time <= start_time:
            return jsonify({'message': 'End time must be after start time'}), 400
        
        # Check if court exists
        court_ref = db.collection('courts').document(data['court_id'])
        court_doc = court_ref.get()
        
        if not court_doc.exists:
            return jsonify({'message': 'Court not found'}), 404
        
        # Create maintenance window
        maintenance_data = {
            'court_id': data['court_id'],
            'start_time': start_time,
            'end_time': end_time,
            'description': data['description'],
            'type': data.get('type', 'general'),
            'status': 'scheduled',
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'created_by': request.user['id']
        }
        
        # Check for affected reservations
        affected_reservations_query = (
            db.collection('reservations')
            .where('court_id', '==', data['court_id'])
            .where('status', 'in', ['confirmed', 'pending'])
            .get()
        )
        
        affected_reservations = []
        for res_doc in affected_reservations_query:
            res_data = res_doc.to_dict()
            res_start = res_data.get('start_time')
            res_end = res_data.get('end_time')
            
            # Check for overlap
            if res_start < end_time and res_end > start_time:
                res_data['id'] = res_doc.id
                affected_reservations.append(res_data)
        
        # Create the maintenance window
        maintenance_ref = db.collection('maintenance').document()
        maintenance_ref.set(maintenance_data)
        
        # Return the created maintenance window with affected reservations
        maintenance_data['id'] = maintenance_ref.id
        maintenance_data['affected_reservations'] = affected_reservations
        
        return jsonify({
            'message': 'Maintenance window created successfully',
            'maintenance': maintenance_data
        }), 201
        
    except Exception as e:
        return jsonify({'message': f'Error creating maintenance window: {str(e)}'}), 500

@maintenance_bp.route('/<maintenance_id>', methods=['PUT'])
@admin_required
def update_maintenance_window(maintenance_id):
    try:
        data = request.json
        
        if not data:
            return jsonify({'message': 'No input data provided'}), 400
        
        # Get the maintenance window
        maintenance_ref = db.collection('maintenance').document(maintenance_id)
        maintenance_doc = maintenance_ref.get()
        
        if not maintenance_doc.exists:
            return jsonify({'message': 'Maintenance window not found'}), 404
        
        # Parse dates if provided
        start_time = None
        end_time = None
        
        if 'start_time' in data:
            try:
                if isinstance(data['start_time'], str):
                    start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
                else:
                    start_time = data['start_time']
            except (ValueError, TypeError):
                return jsonify({'message': 'Invalid start_time format. Use ISO 8601 format.'}), 400
        
        if 'end_time' in data:
            try:
                if isinstance(data['end_time'], str):
                    end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
                else:
                    end_time = data['end_time']
            except (ValueError, TypeError):
                return jsonify({'message': 'Invalid end_time format. Use ISO 8601 format.'}), 400
        
        # Get current values if not provided
        current_data = maintenance_doc.to_dict()
        if not start_time:
            start_time = current_data.get('start_time')
        if not end_time:
            end_time = current_data.get('end_time')
        
        # Validate that end time is after start time
        if end_time <= start_time:
            return jsonify({'message': 'End time must be after start time'}), 400
        
        # Update maintenance data
        update_data = {}
        allowed_fields = ['description', 'type', 'status']
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        # Add time fields if they were updated
        if 'start_time' in data:
            update_data['start_time'] = start_time
        if 'end_time' in data:
            update_data['end_time'] = end_time
        
        # Always update the updated_at timestamp
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        
        # Update the maintenance window
        maintenance_ref.update(update_data)
        
        # Check for affected reservations
        affected_reservations_query = (
            db.collection('reservations')
            .where('court_id', '==', current_data['court_id'])
            .where('status', 'in', ['confirmed', 'pending'])
            .get()
        )
        
        affected_reservations = []
        for res_doc in affected_reservations_query:
            res_data = res_doc.to_dict()
            res_start = res_data.get('start_time')
            res_end = res_data.get('end_time')
            
            # Check for overlap
            if res_start < end_time and res_end > start_time:
                res_data['id'] = res_doc.id
                affected_reservations.append(res_data)
        
        # Return the updated maintenance window
        updated_maintenance = maintenance_ref.get().to_dict()
        updated_maintenance['id'] = maintenance_id
        updated_maintenance['affected_reservations'] = affected_reservations
        
        return jsonify({
            'message': 'Maintenance window updated successfully',
            'maintenance': updated_maintenance
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error updating maintenance window: {str(e)}'}), 500

@maintenance_bp.route('/<maintenance_id>', methods=['DELETE'])
@admin_required
def delete_maintenance_window(maintenance_id):
    try:
        # Get the maintenance window
        maintenance_ref = db.collection('maintenance').document(maintenance_id)
        maintenance_doc = maintenance_ref.get()
        
        if not maintenance_doc.exists:
            return jsonify({'message': 'Maintenance window not found'}), 404
        
        # Check if maintenance window is currently in progress
        maintenance_data = maintenance_doc.to_dict()
        start_time = maintenance_data.get('start_time')
        end_time = maintenance_data.get('end_time')
        now = datetime.now(pytz.UTC)
        
        if start_time <= now <= end_time:
            return jsonify({'message': 'Cannot delete a maintenance window that is currently in progress'}), 400
        
        # Delete the maintenance window
        maintenance_ref.delete()
        
        return jsonify({
            'message': 'Maintenance window deleted successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error deleting maintenance window: {str(e)}'}), 500

@maintenance_bp.route('/<maintenance_id>/cancel-reservations', methods=['POST'])
@admin_required
def cancel_affected_reservations(maintenance_id):
    try:
        # Get the maintenance window
        maintenance_ref = db.collection('maintenance').document(maintenance_id)
        maintenance_doc = maintenance_ref.get()
        
        if not maintenance_doc.exists:
            return jsonify({'message': 'Maintenance window not found'}), 404
        
        maintenance_data = maintenance_doc.to_dict()
        start_time = maintenance_data.get('start_time')
        end_time = maintenance_data.get('end_time')
        court_id = maintenance_data.get('court_id')
        
        # Find affected reservations
        affected_reservations_query = (
            db.collection('reservations')
            .where('court_id', '==', court_id)
            .where('status', 'in', ['confirmed', 'pending'])
            .get()
        )
        
        canceled_reservations = []
        for res_doc in affected_reservations_query:
            res_data = res_doc.to_dict()
            res_start = res_data.get('start_time')
            res_end = res_data.get('end_time')
            
            # Check for overlap
            if res_start < end_time and res_end > start_time:
                # Update reservation status to canceled
                update_data = {
                    'status': 'canceled',
                    'updated_at': firestore.SERVER_TIMESTAMP,
                    'cancelled_at': datetime.now(pytz.UTC),
                    'cancellation_reason': f'Canceled due to maintenance: {maintenance_data.get("description")}',
                    'cancellation_maintenance_id': maintenance_id,
                    'cancellation_penalty': False
                }
                
                res_doc.reference.update(update_data)
                
                # Get updated reservation
                updated_res = res_doc.reference.get().to_dict()
                updated_res['id'] = res_doc.id
                canceled_reservations.append(updated_res)
        
        return jsonify({
            'message': f'Successfully canceled {len(canceled_reservations)} affected reservations',
            'canceled_reservations': canceled_reservations
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error canceling reservations: {str(e)}'}), 500 