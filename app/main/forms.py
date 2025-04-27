from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, SelectField, FloatField, DateField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from app.models import Vehicle

class AddVehicleForm(FlaskForm):
    vin = StringField('VIN', validators=[DataRequired(), Length(min=11, max=17)])
    make = StringField('Make', validators=[DataRequired(), Length(max=64)])
    model = StringField('Model', validators=[DataRequired(), Length(max=64)])
    year = IntegerField('Year', validators=[DataRequired(), NumberRange(min=1886, max=2100)])
    mileage = IntegerField('Initial Mileage', validators=[DataRequired(), NumberRange(min=0)])
    mileage_unit = SelectField('Mileage Unit', choices=[('km', 'Kilometers'), ('mi', 'Miles')], validators=[DataRequired()])
    vehicle_type = SelectField('Vehicle Type', choices=[('vehicle', 'Vehicle'), ('motorcycle', 'Motorcycle'), ('boat', 'Boat')], validators=[DataRequired()])
    submit = SubmitField()

class EditProfileForm(FlaskForm):
    display_name = StringField('Display Name', validators=[Optional(), Length(max=64)])
    county = StringField('County', validators=[Optional(), Length(max=64)])
    country = StringField('Country', validators=[Optional(), Length(max=64)])
    distance_unit = SelectField('Distance Unit', choices=[('km', 'Kilometers'), ('mi', 'Miles')], validators=[DataRequired()])
    submit = SubmitField('Save Changes')

class EditVehicleForm(FlaskForm):
    vin = StringField('VIN', validators=[DataRequired(), Length(min=11, max=17)])
    make = StringField('Make', validators=[DataRequired(), Length(max=64)])
    model = StringField('Model', validators=[DataRequired(), Length(max=64)])
    year = IntegerField('Year', validators=[DataRequired(), NumberRange(min=1886, max=2100)])
    submit = SubmitField('Update Vehicle')

class ServiceLogForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    mileage = IntegerField('Mileage', validators=[DataRequired(), NumberRange(min=0)])
    cost = FloatField('Cost', validators=[Optional()])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Add Service Log')

class InspectionLogForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    mileage = IntegerField('Mileage', validators=[DataRequired(), NumberRange(min=0)])
    cost = FloatField('Cost', validators=[Optional()])
    outcome = SelectField('Outcome', choices=[('Pass', 'Pass'), ('Advisory', 'Advisory'), ('Fail', 'Fail')], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Add Inspection Log')

class ModificationLogForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    mileage = IntegerField('Mileage', validators=[DataRequired(), NumberRange(min=0)])
    cost = FloatField('Cost', validators=[Optional()])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Add Modification Log')

class DamageLogForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    mileage = IntegerField('Mileage', validators=[DataRequired(), NumberRange(min=0)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Add Damage Log') 