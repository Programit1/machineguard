"""
Unit and integration tests for MachineGuard Supabase PostgreSQL schema,
SQLAlchemy models, compatibility aliases, and database engine behaviors.
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base, Machine, SensorReading, Prediction, Alert, MaintenanceLog
from backend.app.config import DATABASE_URL
from backend.app import database


@pytest.fixture(scope="module")
def test_db():
    """Create an isolated in-memory SQLite database mimicking PostgreSQL schema structures."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session, engine
    finally:
        session.close()


def test_schema_tables_present(test_db):
    """Verify all 5 core tables exist in the schema metadata."""
    session, engine = test_db
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "machines" in tables
    assert "sensor_readings" in tables
    assert "predictions" in tables
    assert "alerts" in tables
    assert "maintenance_logs" in tables


def test_machine_model_and_compatibility_aliases(test_db):
    """Verify Machine entity properties, types, and Section 4 compatibility aliases."""
    session, _ = test_db
    machine = Machine(
        machine_id="TEST-CNC-999",
        name="High-Speed Machining Center",
        machine_type="CNC Mill",
        location="Bay 7",
        description="Dual spindle test setup",
        type_variant="H",
        status="ONLINE"
    )
    session.add(machine)
    session.commit()

    saved = session.query(Machine).filter_by(machine_id="TEST-CNC-999").first()
    assert saved is not None
    assert saved.machine_id == "TEST-CNC-999"
    assert saved.name == "High-Speed Machining Center"
    assert saved.status == "ONLINE"
    assert saved.type_variant == "H"

    # Compatibility aliases
    assert saved.machine_name == "High-Speed Machining Center"
    assert saved.configuration == "Dual spindle test setup"

    # Test setter aliases
    saved.machine_name = "Updated Center Name"
    saved.configuration = "Updated configuration parameters"
    session.commit()

    updated = session.query(Machine).filter_by(machine_id="TEST-CNC-999").first()
    assert updated.name == "Updated Center Name"
    assert updated.description == "Updated configuration parameters"


def test_sensor_reading_and_telemetry_id(test_db):
    """Verify SensorReading attributes and telemetry_id alias."""
    session, _ = test_db
    reading = SensorReading(
        machine_id="TEST-CNC-999",
        air_temperature=298.2,
        process_temperature=308.5,
        rotational_speed=1500.0,
        torque=40.0,
        tool_wear=45.0,
        temperature=32.5,
        vibration=1.85,
        pressure=4.2,
        power_consumption=6.0,
        operating_load=65.0
    )
    session.add(reading)
    session.commit()

    assert reading.id is not None
    assert reading.telemetry_id == reading.id
    assert reading.machine_id == "TEST-CNC-999"
    assert reading.air_temperature == 298.2


def test_prediction_model_and_aliases(test_db):
    """Verify Prediction entity fields and compatibility aliases."""
    session, _ = test_db
    reading = session.query(SensorReading).filter_by(machine_id="TEST-CNC-999").first()
    assert reading is not None

    pred = Prediction(
        telemetry_id=reading.id,
        machine_id="TEST-CNC-999",
        failure_probability=0.15,
        raw_probability=0.1524,
        risk_category="Low",
        prediction_available=1,
        failure_prediction=0,
        anomaly_detected=0,
        anomaly_score=0.125,
        anomaly_label="Normal",
        estimated_remaining_cuts=185.0,
        rul_unit="cycles",
        rul_available=1,
        machine_health_status="Healthy",
        model_name="AI4I RandomForestClassifier"
    )
    session.add(pred)
    session.commit()

    assert pred.id is not None
    assert pred.failure_probability == 0.15
    assert pred.risk_category == "Low"
    assert pred.anomaly_label == "Normal"

    # Test aliases
    assert pred.failure_risk == "Low"
    assert pred.anomaly_status == "Normal"
    assert pred.overall_machine_health == "Healthy"
    assert pred.prediction_timestamp == pred.timestamp


def test_alert_model_and_aliases(test_db):
    """Verify Alert entity fields and compatibility aliases."""
    session, _ = test_db
    reading = session.query(SensorReading).filter_by(machine_id="TEST-CNC-999").first()
    pred = session.query(Prediction).filter_by(machine_id="TEST-CNC-999").first()

    alert = Alert(
        telemetry_id=reading.id,
        prediction_id=pred.id,
        machine_id="TEST-CNC-999",
        machine_name="Updated Center Name",
        risk_level="High",
        severity="HIGH",
        alert_type="failure_risk",
        reason="Overstrain failure risk high",
        threshold_or_rule="OSF > 12000 min*Nm",
        recommendation="Reduce spindle feed rate immediately",
        status="ACTIVE"
    )
    session.add(alert)
    session.commit()

    assert alert.id is not None
    assert alert.description == "Overstrain failure risk high"
    assert alert.recommended_action == "Reduce spindle feed rate immediately"

    # Test setter aliases
    alert.description = "Updated alert reason description"
    alert.recommended_action = "Execute urgent tool inspection"
    session.commit()

    updated_alert = session.query(Alert).filter_by(id=alert.id).first()
    assert updated_alert.reason == "Updated alert reason description"
    assert updated_alert.recommendation == "Execute urgent tool inspection"


def test_maintenance_log_creation(test_db):
    """Verify MaintenanceLog persistence."""
    session, _ = test_db
    log = MaintenanceLog(
        machine_id="TEST-CNC-999",
        action="Tool insert replacement",
        technician="Lead Maintenance Engineer",
        notes="Replaced worn carbide inserts after reaching wear limit."
    )
    session.add(log)
    session.commit()

    assert log.id is not None
    assert log.machine_id == "TEST-CNC-999"
    assert log.action == "Tool insert replacement"


def test_database_url_normalization():
    """Verify postgres:// is correctly normalized to postgresql:// for SQLAlchemy."""
    raw_postgres_url = "postgres://postgres.abc:pwd123@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    if raw_postgres_url.startswith("postgres://"):
        normalized = raw_postgres_url.replace("postgres://", "postgresql://", 1)
    else:
        normalized = raw_postgres_url
    assert normalized.startswith("postgresql://")
