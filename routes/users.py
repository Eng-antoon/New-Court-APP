from flask import Blueprint, request, jsonify, current_app
from firebase_admin import firestore, auth, storage
import uuid
from routes.auth import token_required, admin_required
import re

users_bp = Blueprint('users', __name__)
db = firestore.client()
bucket = storage.bucket()

@users_bp.route('', methods=['GET'])
@admin_required
def get_users():
    try:
        # Get query parameters
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))
        role = request.args.get('role')
        search = request.args.get('search', '').lower()
        
        # Get users from Firestore
        query = db.collection('users')
        
        # Apply role filter if provided
        if role:
            query = query.where('role', '==', role)
        
        # Order by name
        query = query.order_by('name')
        
        # Execute query with pagination
        users = []
        user_docs = query.limit(limit).offset(offset).get()
        
        for doc in user_docs:
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            
            # Apply search filter if provided
            if search:
                name = user_data.get('name', '').lower()
                email = user_data.get('email', '').lower()
                
                if search not in name and search not in email:
                    continue
            
            # Remove sensitive fields
            if 'password' in user_data:
                del user_data['password']
                
            users.append(user_data)
        
        # Get total count for pagination
        # Note: This is inefficient for large collections
        total_query = db.collection('users')
        if role:
            total_query = total_query.where('role', '==', role)
        
        total = len(list(total_query.get()))
        
        return jsonify({
            'users': users,
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving users: {str(e)}'}), 500

@users_bp.route('/<user_id>', methods=['GET'])
@token_required
def get_user(user_id):
    try:
        # Check if requesting user is the target user or an admin
        if user_id != request.user['id'] and request.user['role'] not in ['admin', 'owner']:
            return jsonify({'message': 'Not authorized to view this user'}), 403
        
        # Get user from Firestore
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return jsonify({'message': 'User not found'}), 404
        
        user_data = user_doc.to_dict()
        user_data['id'] = user_id
        
        # Remove sensitive fields
        if 'password' in user_data:
            del user_data['password']
        
        # If admin, include reservation history
        if request.user['role'] in ['admin', 'owner']:
            # Get user's reservations
            reservations_ref = db.collection('reservations').where('user_id', '==', user_id).get()
            
            reservations = []
            for res_doc in reservations_ref:
                res_data = res_doc.to_dict()
                res_data['id'] = res_doc.id
                reservations.append(res_data)
            
            user_data['reservations'] = reservations
        
        return jsonify(user_data), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving user: {str(e)}'}), 500

@users_bp.route('/<user_id>', methods=['PUT'])
@token_required
def update_user(user_id):
    try:
        data = request.json
        
        if not data:
            return jsonify({'message': 'No input data provided'}), 400
        
        # Check if requesting user is the target user or an admin
        if user_id != request.user['id'] and request.user['role'] not in ['admin', 'owner']:
            return jsonify({'message': 'Not authorized to update this user'}), 403
        
        # Get user from Firestore
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return jsonify({'message': 'User not found'}), 404
        
        # Determine which fields can be updated
        allowed_fields = ['name', 'phone', 'address', 'preferences']
        
        # Admin users can update more fields
        if request.user['role'] in ['admin', 'owner']:
            allowed_fields.extend(['role', 'status'])
        
        # Update user data
        update_data = {}
        for field in allowed_fields:
            if field in data:
                # Validate role update
                if field == 'role' and data[field] not in ['user', 'admin', 'owner']:
                    return jsonify({'message': 'Invalid role. Must be one of: user, admin, owner'}), 400
                
                update_data[field] = data[field]
        
        # Always update the updated_at timestamp
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        
        # If profile is being completed for the first time
        if 'profile_complete' in data and data['profile_complete'] and not user_doc.to_dict().get('profile_complete', False):
            update_data['profile_complete'] = True
        
        # Update the user
        user_ref.update(update_data)
        
        # Return the updated user
        updated_user = user_ref.get().to_dict()
        updated_user['id'] = user_id
        
        # Remove sensitive fields
        if 'password' in updated_user:
            del updated_user['password']
        
        return jsonify({
            'message': 'User updated successfully',
            'user': updated_user
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error updating user: {str(e)}'}), 500

@users_bp.route('/<user_id>/avatar', methods=['POST'])
@token_required
def upload_avatar(user_id):
    try:
        # Check if requesting user is the target user or an admin
        if user_id != request.user['id'] and request.user['role'] not in ['admin', 'owner']:
            return jsonify({'message': 'Not authorized to update this user'}), 403
        
        # Check if user exists
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return jsonify({'message': 'User not found'}), 404
        
        # Check if image is in request
        if 'avatar' not in request.files:
            return jsonify({'message': 'No avatar provided'}), 400
        
        avatar_file = request.files['avatar']
        
        # Validate file type
        if not avatar_file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            return jsonify({'message': 'Invalid file type. Only PNG, JPG, JPEG, and GIF are allowed'}), 400
        
        # Delete old avatar if it exists
        user_data = user_doc.to_dict()
        if 'avatar_url' in user_data:
            try:
                old_avatar_url = user_data['avatar_url']
                # Extract path from URL
                if 'firebasestorage.googleapis.com' in old_avatar_url:
                    old_path = old_avatar_url.split('/')[-1].split('?')[0]
                    old_blob = bucket.blob(f"avatars/{user_id}/{old_path}")
                    old_blob.delete()
            except Exception as e:
                # Continue even if deletion fails
                print(f"Error deleting old avatar: {str(e)}")
        
        # Generate unique filename
        filename = f"avatars/{user_id}/{str(uuid.uuid4())}-{avatar_file.filename}"
        
        # Upload to Firebase Storage
        blob = bucket.blob(filename)
        blob.upload_from_file(avatar_file)
        
        # Make file publicly accessible
        blob.make_public()
        
        # Get the public URL
        avatar_url = blob.public_url
        
        # Update user with new avatar URL
        user_ref.update({
            'avatar_url': avatar_url,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({
            'message': 'Avatar uploaded successfully',
            'avatar_url': avatar_url
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error uploading avatar: {str(e)}'}), 500

@users_bp.route('/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    try:
        # Check if user exists
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return jsonify({'message': 'User not found'}), 404
        
        # Get user data
        user_data = user_doc.to_dict()
        
        # Check if user is an owner (additional safety check)
        if user_data.get('role') == 'owner':
            return jsonify({'message': 'Cannot delete an owner account'}), 403
        
        # Delete user's reservations
        reservations_ref = db.collection('reservations').where('user_id', '==', user_id).get()
        for res_doc in reservations_ref:
            res_doc.reference.delete()
        
        # Delete user's waitlist entries
        waitlist_ref = db.collection('waitlist').where('user_id', '==', user_id).get()
        for entry_doc in waitlist_ref:
            entry_doc.reference.delete()
        
        # Delete user avatar
        if 'avatar_url' in user_data:
            try:
                avatar_url = user_data['avatar_url']
                if 'firebasestorage.googleapis.com' in avatar_url:
                    path = avatar_url.split('/')[-1].split('?')[0]
                    blob = bucket.blob(f"avatars/{user_id}/{path}")
                    blob.delete()
            except Exception as e:
                # Continue even if deletion fails
                print(f"Error deleting avatar: {str(e)}")
        
        # Delete user in Firebase Auth
        try:
            auth.delete_user(user_id)
        except Exception as e:
            print(f"Error deleting user from Auth: {str(e)}")
        
        # Delete user in Firestore
        user_ref.delete()
        
        return jsonify({
            'message': 'User deleted successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error deleting user: {str(e)}'}), 500 