"""
Rename car table to vehicle and update foreign keys

Revision ID: rename_car_to_vehicle
Revises: a185602cab2c
Create Date: 2024-05-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'rename_car_to_vehicle'
down_revision = 'a185602cab2c'
branch_labels = None
depends_on = None

def upgrade():
    # Rename table 'car' to 'vehicle'
    op.rename_table('car', 'vehicle')

    # Add mileage column as nullable
    op.add_column('vehicle', sa.Column('mileage', sa.Integer(), nullable=True))
    # Set a default value for all existing rows
    op.execute('UPDATE vehicle SET mileage = 0')
    # Alter the column to be NOT NULL
    op.alter_column('vehicle', 'mileage', nullable=False)

    # Rename foreign key columns in related tables
    with op.batch_alter_table('ownership_record') as batch_op:
        batch_op.alter_column('car_id', new_column_name='vehicle_id')
    with op.batch_alter_table('service_log') as batch_op:
        batch_op.alter_column('car_id', new_column_name='vehicle_id')
    with op.batch_alter_table('inspection_log') as batch_op:
        batch_op.alter_column('car_id', new_column_name='vehicle_id')
    with op.batch_alter_table('modification_log') as batch_op:
        batch_op.alter_column('car_id', new_column_name='vehicle_id')
    with op.batch_alter_table('damage_log') as batch_op:
        batch_op.alter_column('car_id', new_column_name='vehicle_id')

    # Add distance_unit column to user
    op.add_column('user', sa.Column('distance_unit', sa.String(length=4), nullable=True))
    op.execute("UPDATE \"user\" SET distance_unit = 'km'")
    op.alter_column('user', 'distance_unit', nullable=False)

def downgrade():
    # Remove mileage column
    op.drop_column('vehicle', 'mileage')

    # Remove distance_unit column
    op.drop_column('user', 'distance_unit')

    # Revert foreign key columns
    with op.batch_alter_table('ownership_record') as batch_op:
        batch_op.alter_column('vehicle_id', new_column_name='car_id')
    with op.batch_alter_table('service_log') as batch_op:
        batch_op.alter_column('vehicle_id', new_column_name='car_id')
    with op.batch_alter_table('inspection_log') as batch_op:
        batch_op.alter_column('vehicle_id', new_column_name='car_id')
    with op.batch_alter_table('modification_log') as batch_op:
        batch_op.alter_column('vehicle_id', new_column_name='car_id')
    with op.batch_alter_table('damage_log') as batch_op:
        batch_op.alter_column('vehicle_id', new_column_name='car_id')

    # Rename table 'vehicle' back to 'car'
    op.rename_table('vehicle', 'car') 