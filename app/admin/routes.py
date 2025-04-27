from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.admin import bp
from app import db
from app.models import VehicleType
from app.models import Vehicle

# Admin-only decorator
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/vehicle_types')
@login_required
@admin_required
def vehicle_types():
    types = VehicleType.query.order_by(VehicleType.order).all()
    return render_template('admin/vehicle_types.html', vehicle_types=types)

@bp.route('/vehicle_types/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_vehicle_type():
    if request.method == 'POST':
        name = request.form.get('name', '').strip().lower()
        display_name = request.form.get('display_name', '').strip()
        if not name or not display_name:
            flash('Both name and display name are required.', 'error')
        elif VehicleType.query.filter_by(name=name).first():
            flash('A vehicle type with this name already exists.', 'error')
        else:
            # Calculate the next order value
            max_order = db.session.query(db.func.max(VehicleType.order)).scalar()
            next_order = (max_order + 1) if max_order is not None else 0
            vt = VehicleType(name=name, display_name=display_name, order=next_order)
            db.session.add(vt)
            db.session.commit()
            flash('Vehicle type added.', 'success')
            return redirect(url_for('admin.vehicle_types'))
    return render_template('admin/add_vehicle_type.html')

@bp.route('/vehicle_types/<int:type_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_vehicle_type(type_id):
    vt = VehicleType.query.get_or_404(type_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip().lower()
        display_name = request.form.get('display_name', '').strip()
        if not name or not display_name:
            flash('Both name and display name are required.', 'error')
        elif VehicleType.query.filter(VehicleType.name == name, VehicleType.id != vt.id).first():
            flash('A vehicle type with this name already exists.', 'error')
        else:
            vt.name = name
            vt.display_name = display_name
            db.session.commit()
            flash('Vehicle type updated.', 'success')
            return redirect(url_for('admin.vehicle_types'))
    return render_template('admin/edit_vehicle_type.html', vt=vt)

@bp.route('/vehicle_types/<int:type_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_vehicle_type(type_id):
    vt = VehicleType.query.get_or_404(type_id)
    if vt.vehicles.count() > 0:
        flash('Cannot delete a vehicle type that is in use.', 'error')
        return redirect(url_for('admin.vehicle_types'))
    db.session.delete(vt)
    db.session.commit()
    flash('Vehicle type deleted.', 'success')
    return redirect(url_for('admin.vehicle_types'))

@bp.route('/vehicle_types/reorder', methods=['POST'])
@login_required
@admin_required
def reorder_vehicle_types():
    order_ids = request.form.getlist('order[]')
    for idx, vt_id in enumerate(order_ids):
        vt = VehicleType.query.get(int(vt_id))
        if vt:
            vt.order = idx
    db.session.commit()
    flash('Vehicle type order updated.', 'success')
    return redirect(url_for('admin.vehicle_types'))

@bp.route('/vehicle/<int:vehicle_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    db.session.delete(vehicle)
    db.session.commit()
    flash('Vehicle deleted successfully!', 'success')
    return redirect(url_for('main.dashboard')) 