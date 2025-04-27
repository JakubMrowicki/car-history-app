from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager
import hashlib

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(64))
    county = db.Column(db.String(64))
    country = db.Column(db.String(64))
    password_hash = db.Column(db.String(512))
    is_service_center = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    distance_unit = db.Column(db.String(4), nullable=False, default='km')  # 'km' or 'mi'
    vehicles = db.relationship('Vehicle', backref='current_owner', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def gravatar_url(self, size=128):
        email = (self.email or '').strip().lower()
        hash = hashlib.md5(email.encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{hash}?d=identicon&s={size}'

class VehicleType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)  # e.g., 'car', 'motorcycle', 'boat'
    display_name = db.Column(db.String(64), nullable=False)  # e.g., 'Car', 'Motorcycle', 'Boat'
    order = db.Column(db.Integer, nullable=False, unique=True, default=0)
    vehicles = db.relationship('Vehicle', backref='vehicle_type_obj', lazy='dynamic')

class Vehicle(db.Model):
    __tablename__ = 'vehicle'
    id = db.Column(db.Integer, primary_key=True)
    vin = db.Column(db.String(17), unique=True)
    make = db.Column(db.String(64))
    model = db.Column(db.String(64))
    year = db.Column(db.Integer)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    service_logs = db.relationship('ServiceLog', backref='vehicle', lazy='dynamic')
    inspection_logs = db.relationship('InspectionLog', backref='vehicle', lazy='dynamic')
    modification_logs = db.relationship('ModificationLog', backref='vehicle', lazy='dynamic')
    damage_logs = db.relationship('DamageLog', backref='vehicle', lazy='dynamic')
    mileage_logs = db.relationship('MileageLog', backref='vehicle', lazy='dynamic', cascade='all, delete-orphan')
    vehicle_type_id = db.Column(db.Integer, db.ForeignKey('vehicle_type.id'), nullable=False)

    def mileage_in_unit(self, unit):
        latest_log = self.mileage_logs.order_by(MileageLog.date.desc()).first()
        if not latest_log:
            return None
        if unit == 'mi':
            return int(round(latest_log.mileage * 0.621371))
        return latest_log.mileage

class OwnershipRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    email = db.Column(db.String(120), nullable=True, index=True)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)

class ServiceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    mileage = db.Column(db.Integer)
    cost = db.Column(db.Float)
    description = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    attachments = db.relationship('Attachment', backref='service_log', lazy='dynamic')

class InspectionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    mileage = db.Column(db.Integer)
    cost = db.Column(db.Float)
    outcome = db.Column(db.String(20))  # Pass/Advisory/Fail
    attachments = db.relationship('Attachment', backref='inspection_log', lazy='dynamic')

class ModificationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    mileage = db.Column(db.Integer)
    cost = db.Column(db.Float)
    description = db.Column(db.Text)
    attachments = db.relationship('Attachment', backref='modification_log', lazy='dynamic')

class DamageLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    mileage = db.Column(db.Integer)
    description = db.Column(db.Text)
    related_service_log_id = db.Column(db.Integer, db.ForeignKey('service_log.id'))
    attachments = db.relationship('Attachment', backref='damage_log', lazy='dynamic')

class MileageLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    mileage = db.Column(db.Integer, nullable=False)  # Always stored in km
    note = db.Column(db.String(255))

class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    data = db.Column(db.LargeBinary)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    service_log_id = db.Column(db.Integer, db.ForeignKey('service_log.id'))
    inspection_log_id = db.Column(db.Integer, db.ForeignKey('inspection_log.id'))
    modification_log_id = db.Column(db.Integer, db.ForeignKey('modification_log.id'))
    damage_log_id = db.Column(db.Integer, db.ForeignKey('damage_log.id')) 