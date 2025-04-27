from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlparse
from app import db
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm
from app.models import User, OwnershipRecord, Vehicle
from sqlalchemy import func, or_

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        login_input = form.username.data.strip()
        user = User.query.filter(
            or_(
                func.lower(User.username) == login_input.lower(),
                func.lower(User.email) == login_input.lower()
            )
        ).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'error')
            return redirect(url_for('auth.login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.dashboard')
        return redirect(next_page)
    return render_template('auth/login.html', title='Sign In', form=form)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            display_name=form.username.data,  # Default display_name to username
            county=None,
            country=None
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        # Claim pending ownerships
        pending_ownerships = OwnershipRecord.query.filter_by(email=user.email, user_id=None).all()
        for record in pending_ownerships:
            record.user_id = user.id
            record.email = None
            # Update the vehicle's owner_id
            if record.vehicle_id:
                vehicle = Vehicle.query.get(record.vehicle_id)
                if vehicle:
                    vehicle.owner_id = user.id
        if pending_ownerships:
            db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title='Register', form=form)

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))

def is_admin():
    return current_user.is_authenticated and getattr(current_user, 'is_admin', False) 