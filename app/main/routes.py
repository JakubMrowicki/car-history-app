from flask import render_template, redirect, url_for, flash, request, send_file, jsonify, abort
from flask_login import login_required, current_user
from app.main import bp
from app import db
from app.main.forms import AddVehicleForm, EditProfileForm, EditVehicleForm, ServiceLogForm, EditServiceLogForm, InspectionLogForm
from app.models import Vehicle, VehicleType, MileageLog, User, OwnershipRecord, ServiceLog, Attachment, InspectionLog
from datetime import datetime
from sqlalchemy import or_
import re
from werkzeug.utils import secure_filename
from io import BytesIO
import os
from flask import current_app

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
    
    # Get all mileage logs
    mileage_logs = vehicle.mileage_logs.order_by(MileageLog.date.desc()).all()
    
    # For the graph, we want oldest to newest
    mileage_logs_for_graph = list(reversed(mileage_logs))
    latest_log = mileage_logs[0] if mileage_logs else None
    mileage_display = None
    if latest_log:
        mileage_display = int(round(latest_log.mileage * 0.621371)) if unit == 'mi' else latest_log.mileage

    # Merge logs for table
    logs = []
    for mileage_log in mileage_logs:
        log_entry = {
            'date': mileage_log.date.strftime('%d/%m/%y'),
            'mileage': int(round(mileage_log.mileage * 0.621371)) if unit == 'mi' else mileage_log.mileage,
            'note': mileage_log.note,
            'attachments': None,
            'cost': None
        }

        # Check for linked records
        if mileage_log.service_log:
            log_entry['log_type'] = 'Service Record'
            log_entry['note'] = mileage_log.service_log.description
            log_entry['attachments'] = mileage_log.service_log.attachments.count()
            log_entry['service_log_id'] = mileage_log.service_log.id
            if mileage_log.service_log.cost is not None:
                if mileage_log.service_log.cost.is_integer():
                    log_entry['cost'] = f"€{int(mileage_log.service_log.cost)}"
                else:
                    log_entry['cost'] = f"€{mileage_log.service_log.cost:.2f}"
        elif mileage_log.inspection_log:
            log_entry['log_type'] = 'Inspection Record'
            log_entry['note'] = f"Outcome: {mileage_log.inspection_log.outcome}"
            log_entry['attachments'] = mileage_log.inspection_log.attachments.count()
            log_entry['inspection_log_id'] = mileage_log.inspection_log.id
            if mileage_log.inspection_log.cost is not None:
                if mileage_log.inspection_log.cost.is_integer():
                    log_entry['cost'] = f"€{int(mileage_log.inspection_log.cost)}"
                else:
                    log_entry['cost'] = f"€{mileage_log.inspection_log.cost:.2f}"
        elif mileage_log.modification_log:
            log_entry['log_type'] = 'Modification Record'
            log_entry['note'] = mileage_log.modification_log.description
            log_entry['attachments'] = mileage_log.modification_log.attachments.count()
            if mileage_log.modification_log.cost is not None:
                if mileage_log.modification_log.cost.is_integer():
                    log_entry['cost'] = f"€{int(mileage_log.modification_log.cost)}"
                else:
                    log_entry['cost'] = f"€{mileage_log.modification_log.cost:.2f}"
        elif mileage_log.damage_log:
            log_entry['log_type'] = 'Damage Record'
            log_entry['note'] = mileage_log.damage_log.description
            log_entry['attachments'] = mileage_log.damage_log.attachments.count()
        elif mileage_log.ownership_record:
            owner_record = mileage_log.ownership_record
            log_entry['log_type'] = 'Ownership Change'
            if owner_record.user_id:
                user = User.query.get(owner_record.user_id)
                log_entry['note'] = f"Ownership transferred to {user.display_name or user.username if user else 'Unknown'} ({user.email if user else ''})"
            elif owner_record.email:
                log_entry['note'] = f"Pending transfer to {owner_record.email}"
            else:
                log_entry['note'] = "Ownership change (unknown recipient)"
        else:
            log_entry['log_type'] = 'Mileage Record'

        logs.append(log_entry)

    mileage_logs_graph = [
        {
            'date': log.date.isoformat(),
            'mileage': int(round(log.mileage * 0.621371)) if unit == 'mi' else log.mileage
        }
        for log in mileage_logs_for_graph
    ]

    return render_template('view_vehicle.html', title=f'{vehicle.make} {vehicle.model}', 
                         vehicle=vehicle, mileage_display=mileage_display, unit=unit, 
                         mileage_logs=logs, mileage_logs_graph=mileage_logs_graph)

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

@bp.route('/vehicle/<int:vehicle_id>/add_service_log', methods=['GET', 'POST'])
@login_required
def add_service_log(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if not (current_user.id == vehicle.owner_id or current_user.is_admin):
        flash('You do not have permission to add a service log to this vehicle.', 'error')
        return redirect(url_for('main.dashboard'))
    
    unit = current_user.distance_unit or 'km'
    form = ServiceLogForm()
    
    if request.method == 'GET':
        form.date.data = datetime.utcnow().date()

    if form.validate_on_submit():
        # Convert mileage to km if user prefers miles
        mileage = form.mileage.data
        if mileage is not None:
            if unit == 'mi':
                mileage_km = int(round(mileage / 0.621371))
            else:
                mileage_km = mileage

            # Get all mileage records for validation
            all_mileage_records = []
            
            # Add mileage logs
            mileage_logs = vehicle.mileage_logs.all()
            for log in mileage_logs:
                all_mileage_records.append({
                    'date': log.date,
                    'mileage': log.mileage
                })
            
            # Sort records by date
            all_mileage_records.sort(key=lambda x: x['date'])
            
            # Find surrounding records
            prev_record = None
            next_record = None
            log_date = form.date.data
            
            for record in all_mileage_records:
                if record['date'].date() < log_date:
                    prev_record = record
                elif record['date'].date() > log_date:
                    next_record = record
                    break
            
            # Validate mileage against surrounding records
            if prev_record and mileage_km < prev_record['mileage']:
                flash(f'Mileage cannot be less than {prev_record["mileage"]} km (recorded on {prev_record["date"].strftime("%d/%m/%y")})', 'error')
                return render_template('add_service_log.html', form=form, vehicle=vehicle, currency_symbol='€', unit=unit)
                
            if next_record and mileage_km > next_record['mileage']:
                flash(f'Mileage cannot be greater than {next_record["mileage"]} km (recorded on {next_record["date"].strftime("%d/%m/%y")})', 'error')
                return render_template('add_service_log.html', form=form, vehicle=vehicle, currency_symbol='€', unit=unit)

            # Create mileage log
            mileage_log = MileageLog(
                vehicle_id=vehicle.id,
                date=form.date.data,
                mileage=mileage_km,
                note=f'Mileage recorded with service log'
            )
            db.session.add(mileage_log)
            db.session.flush()  # Get mileage_log.id
        else:
            mileage_log = None

        service_log = ServiceLog(
            vehicle_id=vehicle.id,
            date=form.date.data,
            cost=form.cost.data,
            description=form.description.data,
            created_by_id=current_user.id,
            mileage_log_id=mileage_log.id if mileage_log else None
        )
        db.session.add(service_log)
        db.session.flush()  # Get service_log.id
        
        # Handle attachments
        files = form.attachments.data
        if files:  # Only process attachments if files were uploaded
            for file in files:
                if file:
                    filename = secure_filename(file.filename)
                    data = file.read()
                    attachment = Attachment(
                        filename=filename,
                        data=data,
                        service_log_id=service_log.id
                    )
                    db.session.add(attachment)
        
        db.session.commit()
        flash('Service log added successfully!', 'success')
        return redirect(url_for('main.view_vehicle', vehicle_id=vehicle.id))
        
    return render_template('add_service_log.html', form=form, vehicle=vehicle, currency_symbol='€', unit=unit)

@bp.route('/service_log/<int:log_id>')
@login_required
def view_service_log(log_id):
    service_log = ServiceLog.query.get_or_404(log_id)
    vehicle = Vehicle.query.get_or_404(service_log.vehicle_id)
    
    # Check permissions
    if vehicle.owner_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to view this service log.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get mileage in user's preferred unit
    unit = current_user.distance_unit or 'km'
    mileage = None
    if service_log.mileage_log_id:
        mileage_log = MileageLog.query.get(service_log.mileage_log_id)
        if mileage_log:
            mileage = int(round(mileage_log.mileage * 0.621371)) if unit == 'mi' else mileage_log.mileage
    
    # Format cost for display
    formatted_cost = None
    if service_log.cost is not None:
        if service_log.cost.is_integer():
            formatted_cost = f"€{int(service_log.cost)}"
        else:
            formatted_cost = f"€{service_log.cost:.2f}"
    
    return render_template('view_service_log.html', 
                         service_log=service_log,
                         vehicle=vehicle,
                         mileage=mileage,
                         unit=unit,
                         formatted_cost=formatted_cost)

@bp.route('/attachment/<int:attachment_id>')
@login_required
def view_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    # Check if this is a preview request (no download)
    preview = request.args.get('preview', '').lower() == 'true'
    
    return send_file(
        BytesIO(attachment.data),
        mimetype=attachment.mimetype,
        download_name=attachment.filename,
        as_attachment=not preview  # Only set as attachment if not previewing
    )

@bp.route('/service_log/<int:log_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_service_log(log_id):
    service_log = ServiceLog.query.get_or_404(log_id)
    vehicle = Vehicle.query.get_or_404(service_log.vehicle_id)
    
    # Check permissions
    if vehicle.owner_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to edit this service log.', 'error')
        return redirect(url_for('main.dashboard'))
    
    form = EditServiceLogForm()
    unit = current_user.distance_unit or 'km'
    
    if request.method == 'GET':
        form.date.data = service_log.date
        form.description.data = service_log.description
        form.cost.data = service_log.cost
        form.mileage_unit.data = unit
        
        # Get mileage in user's preferred unit
        if service_log.mileage_log_id:
            mileage_log = MileageLog.query.get(service_log.mileage_log_id)
            if mileage_log:
                mileage = mileage_log.mileage
                if unit == 'mi':
                    mileage = int(round(mileage * 0.621371))
                form.mileage.data = mileage
    
    if form.validate_on_submit():
        # Update service log
        service_log.date = form.date.data
        service_log.description = form.description.data
        service_log.cost = form.cost.data
        
        # Update mileage if provided
        if form.mileage.data is not None:
            mileage = form.mileage.data
            # Convert to km if user uses miles
            if unit == 'mi':
                mileage = int(round(mileage * 1.60934))
            
            # Create new mileage log if none exists, or update existing one
            if service_log.mileage_log_id:
                mileage_log = MileageLog.query.get(service_log.mileage_log_id)
                mileage_log.mileage = mileage
                mileage_log.date = form.date.data
            else:
                mileage_log = MileageLog(
                    vehicle_id=vehicle.id,
                    date=form.date.data,
                    mileage=mileage,
                    note='Mileage recorded with service log'
                )
                db.session.add(mileage_log)
                db.session.flush()  # Get mileage_log.id
                service_log.mileage_log_id = mileage_log.id
        
        # Handle new attachments
        files = form.attachments.data
        if files:
            for file in files:
                if file:
                    filename = secure_filename(file.filename)
                    data = file.read()
                    attachment = Attachment(
                        filename=filename,
                        data=data,
                        service_log_id=service_log.id
                    )
                    db.session.add(attachment)
        
        db.session.commit()
        flash('Service log updated successfully!', 'success')
        return redirect(url_for('main.view_service_log', log_id=service_log.id))
    
    return render_template('edit_service_log.html', form=form, service_log=service_log, 
                         vehicle=vehicle, unit=unit)

@bp.route('/service_log/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_service_log(log_id):
    service_log = ServiceLog.query.get_or_404(log_id)
    vehicle = Vehicle.query.get_or_404(service_log.vehicle_id)
    
    # Check permissions
    if vehicle.owner_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to delete this service log.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Delete associated mileage log if it exists and is not linked to other logs
    if service_log.mileage_log_id:
        mileage_log = MileageLog.query.get(service_log.mileage_log_id)
        if mileage_log:
            # Check if mileage log is used by other log types
            if not (mileage_log.inspection_log or mileage_log.modification_log or 
                   mileage_log.damage_log or mileage_log.ownership_record):
                db.session.delete(mileage_log)
    
    # Delete all attachments
    for attachment in service_log.attachments:
        db.session.delete(attachment)
    
    # Delete the service log
    db.session.delete(service_log)
    db.session.commit()
    
    flash('Service log deleted successfully!', 'success')
    return redirect(url_for('main.view_vehicle', vehicle_id=vehicle.id))

@bp.route('/attachment/<int:attachment_id>/delete', methods=['POST'])
@login_required
def delete_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    
    # Get the associated log and vehicle
    service_log = None
    inspection_log = None
    if attachment.service_log_id:
        service_log = ServiceLog.query.get(attachment.service_log_id)
        vehicle = Vehicle.query.get(service_log.vehicle_id) if service_log else None
    elif attachment.inspection_log_id:
        inspection_log = InspectionLog.query.get(attachment.inspection_log_id)
        vehicle = Vehicle.query.get(inspection_log.vehicle_id) if inspection_log else None
    
    if not vehicle:
        return jsonify({'error': 'Attachment not found'}), 404
        
    # Check permissions
    if vehicle.owner_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Delete the attachment
    db.session.delete(attachment)
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/attachment/<int:attachment_id>/download')
@login_required
def download_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    service_log = ServiceLog.query.get(attachment.service_log_id)
    
    # Check if user has permission to access this attachment
    if not service_log or service_log.vehicle.user_id != current_user.id:
        abort(403)
    
    # Get the file from the uploads directory
    uploads_dir = current_app.config['UPLOADS_FOLDER']
    file_path = os.path.join(uploads_dir, attachment.stored_filename)
    
    if not os.path.exists(file_path):
        abort(404)
    
    return send_file(
        file_path,
        download_name=attachment.filename,
        as_attachment=True
    )

@bp.route('/vehicle/<int:vehicle_id>/add_inspection_log', methods=['GET', 'POST'])
@login_required
def add_inspection_log(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if not (current_user.id == vehicle.owner_id or current_user.is_admin):
        flash('You do not have permission to add an inspection log to this vehicle.', 'error')
        return redirect(url_for('main.dashboard'))
    
    form = InspectionLogForm()
    unit = current_user.distance_unit or 'km'
    
    if request.method == 'GET':
        form.date.data = datetime.utcnow().date()
        last_mileage = vehicle.mileage_in_unit(unit)
        if last_mileage is not None:
            form.mileage.data = last_mileage

    if form.validate_on_submit():
        # Convert mileage to km if user uses miles
        mileage_km = form.mileage.data
        if unit == 'mi':
            mileage_km = int(round(mileage_km / 0.621371))
            
        # Create mileage log first
        mileage_log = MileageLog(
            vehicle_id=vehicle.id,
            date=form.date.data,
            mileage=mileage_km
        )
        db.session.add(mileage_log)
        db.session.flush()  # Get mileage_log.id before creating inspection log
        
        # Create inspection log with mileage_log_id
        inspection_log = InspectionLog(
            vehicle_id=vehicle.id,
            date=form.date.data,
            cost=form.cost.data,
            outcome=form.outcome.data,
            description=form.description.data,
            created_by_id=current_user.id,
            mileage_log_id=mileage_log.id
        )
        db.session.add(inspection_log)
        db.session.flush()  # Get inspection_log.id before handling attachments
        
        # Handle file attachments
        files = request.files.getlist('attachments')
        for file in files:
            if file.filename:
                filename = secure_filename(file.filename)
                file_data = file.read()
                
                # Determine mimetype
                mimetype = 'application/octet-stream'  # default
                filename_lower = filename.lower()
                if filename_lower.endswith('.pdf'):
                    mimetype = 'application/pdf'
                elif filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    mimetype = f'image/{filename_lower.split(".")[-1]}'
                elif filename_lower.endswith('.txt'):
                    mimetype = 'text/plain'
                
                attachment = Attachment(
                    filename=filename,
                    data=file_data,
                    mimetype=mimetype,
                    inspection_log_id=inspection_log.id,
                    upload_date=datetime.utcnow()
                )
                db.session.add(attachment)
        
        db.session.commit()
        flash('Inspection log added successfully!', 'success')
        return redirect(url_for('main.view_vehicle', vehicle_id=vehicle.id))
    
    return render_template('add_inspection_log.html', 
                         title='Add Inspection Log',
                         form=form,
                         vehicle=vehicle,
                         unit=unit,
                         currency_symbol='€')

@bp.route('/inspection_log/<int:log_id>')
@login_required
def view_inspection_log(log_id):
    inspection_log = InspectionLog.query.get_or_404(log_id)
    vehicle = Vehicle.query.get_or_404(inspection_log.vehicle_id)
    
    if not (current_user.id == vehicle.owner_id or current_user.is_admin):
        flash('You do not have permission to view this inspection log.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get the mileage log associated with this inspection
    mileage_log = MileageLog.query.get(inspection_log.mileage_log_id) if inspection_log.mileage_log_id else None
    unit = current_user.distance_unit or 'km'
    
    # Convert mileage if needed
    mileage = None
    if mileage_log:
        mileage = mileage_log.mileage
        if unit == 'mi':
            mileage = int(round(mileage * 0.621371))
    
    # Format cost with currency symbol
    formatted_cost = None
    if inspection_log.cost is not None:
        if inspection_log.cost.is_integer():
            formatted_cost = f"€{int(inspection_log.cost)}"
        else:
            formatted_cost = f"€{inspection_log.cost:.2f}"
    
    return render_template('view_inspection_log.html',
                         title=f'Inspection Log - {vehicle.make} {vehicle.model}',
                         inspection_log=inspection_log,
                         vehicle=vehicle,
                         mileage=mileage,
                         unit=unit,
                         formatted_cost=formatted_cost)

@bp.route('/inspection_log/<int:log_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_inspection_log(log_id):
    inspection_log = InspectionLog.query.get_or_404(log_id)
    vehicle = Vehicle.query.get_or_404(inspection_log.vehicle_id)
    
    if not (current_user.id == vehicle.owner_id or current_user.is_admin):
        flash('You do not have permission to edit this inspection log.', 'error')
        return redirect(url_for('main.dashboard'))
    
    form = InspectionLogForm(obj=inspection_log)
    unit = current_user.distance_unit or 'km'
    
    # Get the mileage log associated with this inspection
    mileage_log = MileageLog.query.get(inspection_log.mileage_log_id) if inspection_log.mileage_log_id else None
    if mileage_log and request.method == 'GET':
        mileage = mileage_log.mileage
        if unit == 'mi':
            mileage = int(round(mileage * 0.621371))
        form.mileage.data = mileage
    
    if form.validate_on_submit():
        # Update inspection log
        inspection_log.date = form.date.data
        inspection_log.cost = form.cost.data
        inspection_log.outcome = form.outcome.data
        inspection_log.description = form.description.data
        
        # Update mileage log if it exists
        if mileage_log:
            mileage_km = form.mileage.data
            if unit == 'mi':
                mileage_km = int(round(mileage_km / 0.621371))
            mileage_log.date = form.date.data
            mileage_log.mileage = mileage_km
        
        # Handle file attachments
        files = request.files.getlist('attachments')
        for file in files:
            if file.filename:
                filename = secure_filename(file.filename)
                file_data = file.read()
                
                # Determine mimetype
                mimetype = 'application/octet-stream'  # default
                filename_lower = filename.lower()
                if filename_lower.endswith('.pdf'):
                    mimetype = 'application/pdf'
                elif filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    mimetype = f'image/{filename_lower.split(".")[-1]}'
                elif filename_lower.endswith('.txt'):
                    mimetype = 'text/plain'
                
                attachment = Attachment(
                    filename=filename,
                    data=file_data,
                    mimetype=mimetype,
                    inspection_log_id=inspection_log.id,
                    upload_date=datetime.utcnow()
                )
                db.session.add(attachment)
        
        db.session.commit()
        flash('Inspection log updated successfully!', 'success')
        return redirect(url_for('main.view_inspection_log', log_id=inspection_log.id))
    
    return render_template('edit_inspection_log.html',
                         title='Edit Inspection Log',
                         form=form,
                         inspection_log=inspection_log,
                         vehicle=vehicle,
                         unit=unit,
                         currency_symbol='€')

@bp.route('/inspection_log/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_inspection_log(log_id):
    inspection_log = InspectionLog.query.get_or_404(log_id)
    vehicle = Vehicle.query.get_or_404(inspection_log.vehicle_id)
    
    if not (current_user.id == vehicle.owner_id or current_user.is_admin):
        flash('You do not have permission to delete this inspection log.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Delete associated mileage log if it exists and is not linked to other logs
    if inspection_log.mileage_log_id:
        mileage_log = MileageLog.query.get(inspection_log.mileage_log_id)
        if mileage_log:
            # Check if mileage log is used by other log types
            if not (mileage_log.service_log or mileage_log.modification_log or 
                   mileage_log.damage_log or mileage_log.ownership_record):
                db.session.delete(mileage_log)
    
    # Delete the inspection log (this will cascade delete attachments)
    db.session.delete(inspection_log)
    db.session.commit()
    
    flash('Inspection log deleted successfully!', 'success')
    return redirect(url_for('main.view_vehicle', vehicle_id=vehicle.id)) 