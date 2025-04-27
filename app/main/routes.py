from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.main import bp
from app import db
from app.main.forms import AddVehicleForm, EditProfileForm, EditVehicleForm
from app.models import Vehicle, VehicleType, MileageLog, User, OwnershipRecord
from datetime import datetime
from sqlalchemy import or_
import re

@bp.route('/')
@bp.route('/index')
def index():
    return render_template('index.html', title='Home')

@bp.route('/dashboard')
@login_required
def dashboard():
    vehicle_types = VehicleType.query.order_by(VehicleType.display_name).all()
    return render_template('dashboard.html', title='Dashboard', vehicle_types=vehicle_types)

@bp.route('/add_vehicle', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    vehicle_type_name = request.args.get('vehicle_type')
    vehicle_types = VehicleType.query.order_by(VehicleType.display_name).all()
    form = AddVehicleForm()
    vt = None
    if vehicle_type_name:
        vt = VehicleType.query.filter_by(name=vehicle_type_name).first()
        if vt:
            form.vehicle_type.choices = [(vt.name, vt.display_name)]
            form.vehicle_type.data = vt.name
        else:
            form.vehicle_type.choices = [(vt.name, vt.display_name) for vt in vehicle_types]
    else:
        form.vehicle_type.choices = [(vt.name, vt.display_name) for vt in vehicle_types]
    form.submit.label.text = 'Add Vehicle'
    if form.validate_on_submit():
        entered_mileage = form.mileage.data
        if form.mileage_unit.data == 'mi':
            entered_mileage = round(entered_mileage * 1.60934)
        existing = Vehicle.query.filter_by(vin=form.vin.data.strip()).first()
        if existing:
            form.vin.errors.append('A vehicle with this VIN already exists.')
            return render_template('add_vehicle.html', title=f'Add {vt.display_name if vt else "Vehicle"}', form=form, hide_vehicle_type=bool(vt))
        vt_submit = VehicleType.query.filter_by(name=form.vehicle_type.data).first()
        vehicle = Vehicle(
            vin=form.vin.data.strip(),
            make=form.make.data.strip(),
            model=form.model.data.strip(),
            year=form.year.data,
            vehicle_type_id=vt_submit.id if vt_submit else None,
            owner_id=current_user.id
        )
        db.session.add(vehicle)
        db.session.flush()  # Get vehicle.id before commit
        mileage_log = MileageLog(vehicle_id=vehicle.id, mileage=entered_mileage, note='Initial mileage')
        db.session.add(mileage_log)
        db.session.commit()
        flash('Vehicle added successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('add_vehicle.html', title=f'Add {vt.display_name if vt else "Vehicle"}', form=form, hide_vehicle_type=bool(vt))

@bp.route('/vehicle/<int:vehicle_id>')
@login_required
def view_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if vehicle.owner_id != current_user.id:
        flash('You do not have permission to view this vehicle.', 'error')
        return redirect(url_for('main.dashboard'))
    unit = current_user.distance_unit or 'km'
    mileage_logs_query = vehicle.mileage_logs.order_by(MileageLog.date.desc()).all()
    # For the graph, we want oldest to newest
    mileage_logs_for_graph = list(reversed(mileage_logs_query))
    latest_log = mileage_logs_query[0] if mileage_logs_query else None
    mileage_display = None
    if latest_log:
        mileage_display = int(round(latest_log.mileage * 0.621371)) if unit == 'mi' else latest_log.mileage
    # Ownership records
    ownership_records = OwnershipRecord.query.filter_by(vehicle_id=vehicle.id).order_by(OwnershipRecord.start_date.desc()).all()
    # Merge logs for table
    logs = []
    for log in mileage_logs_query:
        logs.append({
            'date': log.date.isoformat(),
            'log_type': 'Mileage Record',
            'mileage': int(round(log.mileage * 0.621371)) if unit == 'mi' else log.mileage,
            'note': log.note,
            'attachments': None
        })
    for record in ownership_records:
        if record.user_id:
            user = User.query.get(record.user_id)
            note = f"Ownership transferred to {user.display_name or user.username if user else 'Unknown'} ({user.email if user else ''})"
        elif record.email:
            note = f"Pending transfer to {record.email}"
        else:
            note = "Ownership change (unknown recipient)"
        logs.append({
            'date': record.start_date.isoformat() if record.start_date else '',
            'log_type': 'Ownership Change',
            'mileage': '',
            'note': note,
            'attachments': None
        })
    # Sort all logs by date descending
    logs.sort(key=lambda x: x['date'], reverse=True)
    mileage_logs_graph = [
        {
            'date': log.date.isoformat(),
            'mileage': int(round(log.mileage * 0.621371)) if unit == 'mi' else log.mileage
        }
        for log in mileage_logs_for_graph
    ]
    return render_template('view_vehicle.html', title=f'{vehicle.make} {vehicle.model}', vehicle=vehicle, mileage_display=mileage_display, unit=unit, mileage_logs=logs, mileage_logs_graph=mileage_logs_graph)

@bp.route('/vehicle/<int:vehicle_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if vehicle.owner_id != current_user.id:
        flash('You do not have permission to edit this vehicle.', 'error')
        return redirect(url_for('main.dashboard'))
    form = EditVehicleForm(obj=vehicle)
    form.submit.label.text = 'Update Vehicle'
    # Get the referrer, but avoid using the edit page itself as the referrer
    referrer = request.referrer
    if referrer and referrer.endswith(request.path):
        referrer = url_for('main.view_vehicle', vehicle_id=vehicle.id)
    if form.validate_on_submit():
        # Check for duplicate VIN if changed
        if form.vin.data.strip() != vehicle.vin:
            existing = Vehicle.query.filter_by(vin=form.vin.data.strip()).first()
            if existing and existing.id != vehicle.id:
                form.vin.errors.append('A vehicle with this VIN already exists.')
                return render_template('edit_vehicle.html', title='Edit Vehicle', form=form, vehicle=vehicle, referrer=referrer)
        vehicle.vin = form.vin.data.strip()
        vehicle.make = form.make.data.strip()
        vehicle.model = form.model.data.strip()
        vehicle.year = form.year.data
        db.session.commit()
        flash('Vehicle updated successfully!', 'success')
        return redirect(url_for('main.view_vehicle', vehicle_id=vehicle.id))
    return render_template('edit_vehicle.html', title='Edit Vehicle', form=form, vehicle=vehicle, referrer=referrer)

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = EditProfileForm(obj=current_user)
    # Get the referrer, but avoid using the profile page itself as the referrer
    referrer = request.referrer
    if referrer and referrer.endswith(request.path):
        referrer = url_for('main.dashboard')
    if request.method == 'GET':
        form.distance_unit.data = current_user.distance_unit or 'km'
    if form.validate_on_submit():
        current_user.display_name = form.display_name.data
        current_user.county = form.county.data
        current_user.country = form.country.data
        current_user.distance_unit = form.distance_unit.data
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('main.profile'))
    return render_template('profile.html', title='Edit Profile', form=form, user=current_user, referrer=referrer)

@bp.route('/vehicle/<int:vehicle_id>/add_mileage_log', methods=['GET'])
@login_required
def add_mileage_log_get(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if vehicle.owner_id != current_user.id:
        flash('You do not have permission to add a log to this vehicle.', 'error')
        return redirect(url_for('main.dashboard'))
    current_date = datetime.utcnow().strftime('%Y-%m-%d')
    unit = current_user.distance_unit or 'km'
    last_mileage = vehicle.mileage_in_unit(unit)
    if last_mileage is None:
        last_mileage = 0
    return render_template('add_mileage_log.html', vehicle=vehicle, current_date=current_date, last_mileage=last_mileage, min_mileage=last_mileage, unit=unit)

@bp.route('/vehicle/<int:vehicle_id>/add_mileage_log', methods=['POST'])
@login_required
def add_mileage_log(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if vehicle.owner_id != current_user.id:
        flash('You do not have permission to add a log to this vehicle.', 'error')
        return redirect(url_for('main.dashboard'))
    mileage = request.form.get('mileage')
    note = request.form.get('note')
    unit = current_user.distance_unit or 'km'
    last_mileage_km = vehicle.mileage_in_unit('km')
    if last_mileage_km is None:
        last_mileage_km = 0
    try:
        date = datetime.utcnow()
        mileage = int(mileage)
        # Convert to km if user prefers miles
        if unit == 'mi':
            mileage_km = int(round(mileage / 0.621371))
        else:
            mileage_km = mileage
        if mileage_km < last_mileage_km:
            flash('Mileage cannot be less than the last known value.', 'error')
            return redirect(url_for('main.add_mileage_log_get', vehicle_id=vehicle.id))
    except Exception:
        flash('Invalid date or mileage.', 'error')
        return redirect(url_for('main.add_mileage_log_get', vehicle_id=vehicle.id))
    log = MileageLog(vehicle_id=vehicle.id, date=date, mileage=mileage_km, note=note)
    db.session.add(log)
    db.session.commit()
    flash('Mileage log added successfully!', 'success')
    return redirect(url_for('main.view_vehicle', vehicle_id=vehicle.id))

@bp.route('/vehicle/<int:vehicle_id>/transfer_ownership', methods=['GET', 'POST'])
@login_required
def transfer_ownership(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    # Check for existing pending ownership
    pending = OwnershipRecord.query.filter_by(vehicle_id=vehicle.id, user_id=None).filter(OwnershipRecord.email != None).first()
    if pending:
        return redirect(url_for('main.cancel_pending_ownership', vehicle_id=vehicle.id))
    if not (current_user.id == vehicle.owner_id or current_user.is_admin):
        flash('You do not have permission to transfer this vehicle.', 'error')
        return redirect(url_for('main.dashboard'))
    unit = current_user.distance_unit or 'km'
    last_mileage = vehicle.mileage_in_unit(unit)
    if last_mileage is None:
        last_mileage = 0
    min_mileage = last_mileage
    search_results = []
    pending_email = None
    if request.method == 'POST':
        search = request.form.get('search')
        user_id = request.form.get('user_id')
        confirm = request.form.get('confirm')
        mileage = request.form.get('mileage')
        email = request.form.get('pending_email')
        if user_id and confirm == 'on':
            new_owner = User.query.get(int(user_id))
            if not new_owner:
                flash('Selected user not found.', 'error')
                return redirect(url_for('main.transfer_ownership', vehicle_id=vehicle.id))
            old_owner_id = vehicle.owner_id
            vehicle.owner_id = new_owner.id
            db.session.commit()
            # Add OwnershipRecord
            ownership_record = OwnershipRecord(vehicle_id=vehicle.id, user_id=new_owner.id, start_date=datetime.utcnow())
            db.session.add(ownership_record)
            # Optionally add a MileageLog if mileage is provided and valid
            if mileage:
                try:
                    mileage = int(mileage)
                    # Convert to km if user prefers miles
                    if unit == 'mi':
                        mileage_km = int(round(mileage / 0.621371))
                    else:
                        mileage_km = mileage
                    last_mileage_km = vehicle.mileage_in_unit('km')
                    if last_mileage_km is None:
                        last_mileage_km = 0
                    if mileage_km < last_mileage_km:
                        flash('Mileage cannot be less than the last known value.', 'error')
                        return redirect(url_for('main.transfer_ownership', vehicle_id=vehicle.id))
                    log = MileageLog(vehicle_id=vehicle.id, date=datetime.utcnow(), mileage=mileage_km, note='Mileage recorded at ownership transfer')
                    db.session.add(log)
                except Exception:
                    flash('Invalid mileage value.', 'error')
                    return redirect(url_for('main.transfer_ownership', vehicle_id=vehicle.id))
            db.session.commit()
            flash('Ownership transferred successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        elif email and confirm == 'on':
            # Pending transfer by email
            email = email.strip() if email else ''
            email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
            if not email or not re.match(email_regex, email):
                flash('Please enter a valid email address for the pending transfer.', 'error')
                return redirect(url_for('main.transfer_ownership', vehicle_id=vehicle.id))
            # Check if a user with this email already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('A user with this email address is already registered. Please use the user search to transfer ownership.', 'error')
                return redirect(url_for('main.transfer_ownership', vehicle_id=vehicle.id))
            ownership_record = OwnershipRecord(vehicle_id=vehicle.id, email=email, start_date=datetime.utcnow())
            db.session.add(ownership_record)
            db.session.commit()
            flash('Pending transfer created for email: {}'.format(email), 'success')
            return redirect(url_for('main.view_vehicle', vehicle_id=vehicle.id))
        elif search:
            search_results = User.query.filter(
                or_(User.username.ilike(f'%{search}%'), User.email.ilike(f'%{search}%')),
                User.id != vehicle.owner_id,
                User.id != current_user.id
            ).all()
        elif not confirm:
            flash('You must confirm that this change is permanent.', 'error')
    return render_template('transfer_ownership.html', vehicle=vehicle, search_results=search_results, last_mileage=last_mileage, min_mileage=min_mileage, unit=unit, pending_email=pending_email)

@bp.route('/vehicle/<int:vehicle_id>/cancel_pending_ownership', methods=['GET', 'POST'])
@login_required
def cancel_pending_ownership(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    pending = OwnershipRecord.query.filter_by(vehicle_id=vehicle.id, user_id=None).filter(OwnershipRecord.email != None).first()
    if not pending:
        return redirect(url_for('main.transfer_ownership', vehicle_id=vehicle.id))
    if request.method == 'POST':
        if request.form.get('confirm') == 'yes':
            db.session.delete(pending)
            db.session.commit()
            flash('Pending ownership change cancelled.', 'success')
            return redirect(url_for('main.transfer_ownership', vehicle_id=vehicle.id))
        else:
            return redirect(url_for('main.view_vehicle', vehicle_id=vehicle.id))
    return render_template('cancel_pending_ownership.html', vehicle=vehicle, pending=pending) 