"""Initial schema - all tables

Revision ID: 001
Revises:
Create Date: 2026-05-07 14:50:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # sources_metadata
    op.create_table(
        'sources_metadata',
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('independence_class', sa.Text(), nullable=False),
        sa.Column('typical_latency_min', sa.Integer(), nullable=True),
        sa.Column('update_frequency', sa.String(), nullable=True),
        sa.Column('coverage_notes', sa.Text(), nullable=True),
        sa.Column('license', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('source'),
        sa.CheckConstraint("independence_class IN ('sensor','field_reported','media_derived')", name='check_independence_class')
    )

    # events_quarantine
    op.create_table(
        'events_quarantine',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('ingest_time', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('rejection_code', sa.String(), nullable=False),
        sa.Column('rejection_detail', sa.Text(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_events_quarantine_source_ingest_time', 'events_quarantine', ['source', 'ingest_time'])
    op.create_index('ix_events_quarantine_resolved', 'events_quarantine', ['resolved'], unique=False, postgresql_where=sa.text('NOT resolved'))

    # events_canonical - using SQL directly for geometry columns
    op.execute("""
        CREATE TABLE events_canonical (
            id SERIAL PRIMARY KEY,
            event_id_source TEXT NOT NULL,
            source TEXT NOT NULL,
            event_time TIMESTAMPTZ NOT NULL,
            ingest_time TIMESTAMPTZ DEFAULT now(),
            event_type TEXT NOT NULL,
            category TEXT NOT NULL CHECK (category IN ('conflict','disaster_natural','wildfire','mobility','humanitarian','other')),
            location_point geometry(Point,4326) NOT NULL,
            location_accuracy_km FLOAT,
            admin1 TEXT,
            admin2 TEXT,
            country_iso2 TEXT,
            geometry geometry(Geometry,4326),
            geometry_type TEXT CHECK (geometry_type IN ('POINT','POLYGON','MULTIPOLYGON')),
            actors JSONB,
            fatalities INT,
            severity FLOAT NOT NULL CHECK (severity BETWEEN 0 AND 10),
            confidence FLOAT NOT NULL CHECK (confidence BETWEEN 0 AND 10),
            source_url TEXT,
            source_refs TEXT[],
            raw_event_id INT,
            is_confirmed BOOLEAN DEFAULT FALSE,
            is_rumor BOOLEAN DEFAULT FALSE,
            UNIQUE (source, event_id_source)
        )
    """)
    op.execute("ALTER TABLE events_canonical ADD CONSTRAINT fk_events_canonical_source FOREIGN KEY (source) REFERENCES sources_metadata(source)")
    op.create_index('ix_events_canonical_event_time_category', 'events_canonical', ['event_time', 'category'])
    op.create_index('ix_events_canonical_source_event_time', 'events_canonical', ['source', 'event_time'])
    op.create_index('ix_events_canonical_category_is_confirmed', 'events_canonical', ['category', 'is_confirmed'])

    # incidents - using SQL directly for geometry columns
    op.execute("""
        CREATE TABLE incidents (
            incident_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            first_seen TIMESTAMPTZ NOT NULL,
            last_seen TIMESTAMPTZ NOT NULL,
            last_updated TIMESTAMPTZ DEFAULT now(),
            event_type TEXT NOT NULL,
            category TEXT NOT NULL,
            country_iso2 TEXT,
            admin1 TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            status_changed_at TIMESTAMPTZ DEFAULT now(),
            canonical_point geometry(Point,4326) NOT NULL,
            canonical_geometry geometry(Geometry,4326),
            severity_max FLOAT CHECK (severity_max BETWEEN 0 AND 10),
            severity_latest FLOAT CHECK (severity_latest BETWEEN 0 AND 10),
            confidence FLOAT CHECK (confidence BETWEEN 0 AND 10),
            fatalities_total INT DEFAULT 0,
            source_count INT DEFAULT 0,
            observation_count INT DEFAULT 0,
            sources TEXT[],
            linked_event_ids BIGINT[]
        )
    """)
    op.create_index('ix_incidents_status_last_seen', 'incidents', ['status', 'last_seen'])
    op.create_index('ix_incidents_category_status', 'incidents', ['category', 'status'])

    # aoi - using SQL directly for geometry columns
    op.execute("""
        CREATE TABLE aoi (
            aoi_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            description TEXT,
            geometry geometry(Geometry,4326) NOT NULL,
            categories TEXT[],
            min_severity FLOAT DEFAULT 0.0,
            is_active BOOLEAN DEFAULT TRUE,
            created_by TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    # corrections_audit
    op.create_table(
        'corrections_audit',
        sa.Column('correction_id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('incident_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('corrected_by', sa.String(), nullable=False),
        sa.Column('correction_type', sa.String(), nullable=False),
        sa.Column('before_state', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('after_state', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('correction_id'),
        sa.CheckConstraint("correction_type IN ('false_positive','reclassify','relocate','merge','close')", name='check_correction_type')
    )
    op.execute("ALTER TABLE corrections_audit ADD CONSTRAINT fk_corrections_incident FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)")

    # Add GIST indexes for geometry columns (separate from table creation for clarity)
    op.execute("CREATE INDEX ix_events_canonical_location_point ON events_canonical USING GIST (location_point)")
    op.execute("CREATE INDEX ix_incidents_canonical_point ON incidents USING GIST (canonical_point)")
    op.execute("CREATE INDEX ix_aoi_geometry ON aoi USING GIST (geometry)")
    op.execute("CREATE INDEX ix_incidents_last_seen_open ON incidents (last_seen) WHERE status IN ('open', 'updated')")
    op.execute("CREATE INDEX ix_aoi_is_active ON aoi (is_active) WHERE is_active = TRUE")
    op.execute("CREATE INDEX ix_events_quarantine_resolved_active ON events_quarantine (resolved) WHERE resolved = FALSE")


def downgrade() -> None:
    op.drop_table('corrections_audit')
    op.drop_table('aoi')
    op.drop_table('incidents')
    op.drop_table('events_canonical')
    op.drop_table('events_quarantine')
    op.drop_table('sources_metadata')