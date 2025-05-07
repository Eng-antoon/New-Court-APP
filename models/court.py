from firebase_admin import firestore
from datetime import datetime
import pytz
import json

class Court:
    """
    Represents a volleyball court in the system.
    """
    def __init__(self, id=None, name=None, address=None, is_indoor=None, 
                 surface_type=None, description=None, amenities=None, 
                 images=None, operating_hours=None, coordinates=None):
        self.id = id
        self.name = name
        self.address = address or {}
        self.is_indoor = is_indoor
        self.surface_type = surface_type
        self.description = description or ""
        self.amenities = amenities or []
        self.images = images or []
        self.operating_hours = operating_hours or {}
        self.coordinates = coordinates or {}
        self.status = "active"
        self.created_at = datetime.now(pytz.UTC)
        self.updated_at = datetime.now(pytz.UTC)
    
    @classmethod
    def from_dict(cls, source, id=None):
        """Create a Court instance from a dictionary."""
        court = cls()
        court.id = id
        
        # Map standard fields
        if 'name' in source:
            court.name = source['name']
        if 'address' in source:
            court.address = source['address']
        if 'is_indoor' in source:
            court.is_indoor = source['is_indoor']
        if 'surface_type' in source:
            court.surface_type = source['surface_type']
        if 'description' in source:
            court.description = source['description']
        if 'amenities' in source:
            court.amenities = source['amenities']
        if 'images' in source:
            court.images = source['images']
        if 'operating_hours' in source:
            court.operating_hours = source['operating_hours']
        if 'coordinates' in source:
            court.coordinates = source['coordinates']
        if 'status' in source:
            court.status = source['status']
        if 'created_at' in source:
            court.created_at = source['created_at']
        if 'updated_at' in source:
            court.updated_at = source['updated_at']
        
        return court
    
    def to_dict(self):
        """Return a dictionary representation of the Court."""
        court_dict = {
            'name': self.name,
            'address': self.address,
            'is_indoor': self.is_indoor,
            'surface_type': self.surface_type,
            'description': self.description,
            'amenities': self.amenities,
            'images': self.images,
            'operating_hours': self.operating_hours,
            'coordinates': self.coordinates,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
        # Remove None values
        return {k: v for k, v in court_dict.items() if v is not None}
    
    def save(self, db):
        """Save the court to Firestore."""
        if not self.id:
            # New court
            ref = db.collection('courts').document()
            self.id = ref.id
        else:
            # Existing court
            ref = db.collection('courts').document(self.id)
        
        # Update timestamp
        self.updated_at = firestore.SERVER_TIMESTAMP
        
        # Save to Firestore
        ref.set(self.to_dict())
        return self
    
    @classmethod
    def get_by_id(cls, db, id):
        """Get a court by ID."""
        doc = db.collection('courts').document(id).get()
        if not doc.exists:
            return None
        
        court_data = doc.to_dict()
        return cls.from_dict(court_data, id=id)
    
    @staticmethod
    def get_all(db, limit=10, offset=0, filters=None):
        """Get all courts with optional filtering."""
        query = db.collection('courts')
        
        if filters:
            for field, op, value in filters:
                query = query.where(field, op, value)
        
        docs = query.limit(limit).offset(offset).get()
        courts = []
        
        for doc in docs:
            court_data = doc.to_dict()
            court = Court.from_dict(court_data, id=doc.id)
            courts.append(court)
        
        return courts
    
    def delete(self, db):
        """Delete a court."""
        if not self.id:
            raise ValueError("Court has no ID")
        
        db.collection('courts').document(self.id).delete()
    
    def get_availability(self, db, date, start_time=None, end_time=None):
        """Get court availability for a specific date."""
        from models.reservation import Reservation
        from models.maintenance import Maintenance
        
        if not start_time:
            start_time = datetime.combine(date, datetime.min.time().replace(hour=0, minute=0), tzinfo=pytz.UTC)
        if not end_time:
            end_time = datetime.combine(date, datetime.min.time().replace(hour=23, minute=59), tzinfo=pytz.UTC)
        
        # Get reservations
        reservations = Reservation.get_for_court(db, self.id, start_time, end_time)
        
        # Get maintenance windows
        maintenance_windows = Maintenance.get_for_court(db, self.id, start_time, end_time)
        
        # Get operating hours for this day
        day_of_week = date.strftime('%A').lower()
        operating_hours = self.operating_hours.get(day_of_week, {})
        
        is_open = True
        open_time = None
        close_time = None
        
        if operating_hours:
            if not operating_hours.get('is_open', True):
                is_open = False
            
            if 'open' in operating_hours and operating_hours['open']:
                open_parts = operating_hours['open'].split(':')
                if len(open_parts) == 2:
                    open_hour, open_minute = int(open_parts[0]), int(open_parts[1])
                    open_time = datetime.combine(date, datetime.min.time().replace(hour=open_hour, minute=open_minute), tzinfo=pytz.UTC)
            
            if 'close' in operating_hours and operating_hours['close']:
                close_parts = operating_hours['close'].split(':')
                if len(close_parts) == 2:
                    close_hour, close_minute = int(close_parts[0]), int(close_parts[1])
                    close_time = datetime.combine(date, datetime.min.time().replace(hour=close_hour, minute=close_minute), tzinfo=pytz.UTC)
        
        # Default operating hours if not specified
        if not open_time:
            open_time = datetime.combine(date, datetime.min.time().replace(hour=8, minute=0), tzinfo=pytz.UTC)
        if not close_time:
            close_time = datetime.combine(date, datetime.min.time().replace(hour=20, minute=0), tzinfo=pytz.UTC)
        
        return {
            'court_id': self.id,
            'name': self.name,
            'is_open': is_open,
            'open_time': open_time,
            'close_time': close_time,
            'reservations': [r.to_dict() for r in reservations],
            'maintenance': [m.to_dict() for m in maintenance_windows]
        } 