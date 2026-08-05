"""Initial database schema for LifePulse AI

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-07-31

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('mobile_number', sa.String(length=50), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_mobile_number'), 'users', ['mobile_number'], unique=True)

    # 2. donor_profiles table
    op.create_table(
        'donor_profiles',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('blood_type', sa.String(length=10), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('pincode', sa.String(length=20), nullable=True),
        sa.Column('last_donation_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=True),
        sa.Column('max_travel_radius_km', sa.Float(), nullable=True),
        sa.Column('reliability_score', sa.Float(), nullable=True),
        sa.Column('screening_status', sa.String(length=50), nullable=True),
        sa.Column('screening_completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_donor_profiles_blood_type'), 'donor_profiles', ['blood_type'], unique=False)
    op.create_index(op.f('ix_donor_profiles_user_id'), 'donor_profiles', ['user_id'], unique=True)

    # 3. donor_medical_screenings table
    op.create_table(
        'donor_medical_screenings',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('donor_id', sa.String(length=64), nullable=False),
        sa.Column('age', sa.Integer(), nullable=False),
        sa.Column('weight_kg', sa.Float(), nullable=False),
        sa.Column('has_fever_or_illness', sa.Boolean(), nullable=True),
        sa.Column('recent_medication', sa.Boolean(), nullable=True),
        sa.Column('recent_surgery', sa.Boolean(), nullable=True),
        sa.Column('recent_vaccination', sa.Boolean(), nullable=True),
        sa.Column('pregnancy_status', sa.Boolean(), nullable=True),
        sa.Column('recent_tattoo_or_piercing', sa.Boolean(), nullable=True),
        sa.Column('travel_exposure_history', sa.Boolean(), nullable=True),
        sa.Column('screening_answers_json', sa.JSON(), nullable=True),
        sa.Column('eligibility_status', sa.String(length=50), nullable=True),
        sa.Column('eligibility_reasons_json', sa.JSON(), nullable=True),
        sa.Column('eligibility_flags_json', sa.JSON(), nullable=True),
        sa.Column('rules_version', sa.String(length=20), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['donor_id'], ['donor_profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_donor_medical_screenings_donor_id'), 'donor_medical_screenings', ['donor_id'], unique=True)

    # 4. emergency_requests table
    op.create_table(
        'emergency_requests',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('requester_user_id', sa.String(length=64), nullable=True),
        sa.Column('patient_name', sa.String(length=255), nullable=True),
        sa.Column('requester_phone', sa.String(length=50), nullable=True),
        sa.Column('hospital_name', sa.String(length=255), nullable=True),
        sa.Column('blood_type', sa.String(length=10), nullable=False),
        sa.Column('donation_type', sa.String(length=50), nullable=True),
        sa.Column('units_needed', sa.Integer(), nullable=True),
        sa.Column('urgency_level', sa.String(length=50), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['requester_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_emergency_requests_blood_type'), 'emergency_requests', ['blood_type'], unique=False)
    op.create_index(op.f('ix_emergency_requests_requester_user_id'), 'emergency_requests', ['requester_user_id'], unique=False)

    # 5. donor_matches table
    op.create_table(
        'donor_matches',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('match_id', sa.String(length=128), nullable=False),
        sa.Column('request_id', sa.String(length=64), nullable=False),
        sa.Column('donor_id', sa.String(length=64), nullable=False),
        sa.Column('ring_number', sa.Integer(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('distance_km', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('score_breakdown_json', sa.JSON(), nullable=True),
        sa.Column('donor_latitude', sa.Float(), nullable=True),
        sa.Column('donor_longitude', sa.Float(), nullable=True),
        sa.Column('eta_minutes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['donor_id'], ['donor_profiles.id'], ),
        sa.ForeignKeyConstraint(['request_id'], ['emergency_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_donor_matches_donor_id'), 'donor_matches', ['donor_id'], unique=False)
    op.create_index(op.f('ix_donor_matches_match_id'), 'donor_matches', ['match_id'], unique=True)
    op.create_index(op.f('ix_donor_matches_request_id'), 'donor_matches', ['request_id'], unique=False)

    # 6. donation_histories table
    op.create_table(
        'donation_histories',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('donor_id', sa.String(length=64), nullable=False),
        sa.Column('request_id', sa.String(length=64), nullable=True),
        sa.Column('donation_date', sa.Date(), nullable=False),
        sa.Column('units_donated', sa.Integer(), nullable=True),
        sa.Column('hospital_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['donor_id'], ['donor_profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_donation_histories_donor_id'), 'donation_histories', ['donor_id'], unique=False)

    # 7. hospitals table
    op.create_table(
        'hospitals',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('inventory_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('request_id', sa.String(length=64), nullable=False),
        sa.Column('donor_id', sa.String(length=64), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=True),
        sa.Column('passed_all', sa.Boolean(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('reasons_json', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_request_id'), 'audit_logs', ['request_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_request_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_table('hospitals')
    op.drop_index(op.f('ix_donation_histories_donor_id'), table_name='donation_histories')
    op.drop_table('donation_histories')
    op.drop_index(op.f('ix_donor_matches_request_id'), table_name='donor_matches')
    op.drop_index(op.f('ix_donor_matches_match_id'), table_name='donor_matches')
    op.drop_index(op.f('ix_donor_matches_donor_id'), table_name='donor_matches')
    op.drop_table('donor_matches')
    op.drop_index(op.f('ix_emergency_requests_requester_user_id'), table_name='emergency_requests')
    op.drop_index(op.f('ix_emergency_requests_blood_type'), table_name='emergency_requests')
    op.drop_table('emergency_requests')
    op.drop_index(op.f('ix_donor_medical_screenings_donor_id'), table_name='donor_medical_screenings')
    op.drop_table('donor_medical_screenings')
    op.drop_index(op.f('ix_donor_profiles_user_id'), table_name='donor_profiles')
    op.drop_index(op.f('ix_donor_profiles_blood_type'), table_name='donor_profiles')
    op.drop_table('donor_profiles')
    op.drop_index(op.f('ix_users_mobile_number'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
