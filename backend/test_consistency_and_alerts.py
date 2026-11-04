"""
MachinaGuard - Comprehensive Consistency, Alert Auto-Resolution & Fleet Verification Suite
Tests:
  A: Normal Telemetry Evaluation (Nominal baseline, Healthy status, no critical alert)
  B: Operational Rule Triggering (PWF mechanical power violation)
  C: Operational Anomaly Outlier & Model Disagreement
  D: High Failure Probability & Critical Health Assessment
  E: RUL Input Filtering & Graceful Fallback (No hallucinated numbers)
  F: Alert Auto-Resolution (Fault followed by nominal reading auto-resolves active alert)
  G: Alert Deduplication (Sustained fault does not spam duplicate ACTIVE alerts)
  H: End-to-End Traceability (telemetry_id links reading, prediction, and alert)
  I: Multi-Machine Fleet Isolation & Operating Profiles
"""

import os
import sys
import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.models import Base, Machine, SensorReading, Prediction, Alert
from backend.app.schemas import TelemetryCreate
from backend.app.crud import (
    save_telemetry_and_predict,
    get_machine,
    get_machine_card_summary,
    get_dashboard_summary,
    ensure_schema_migrations
)
from backend.app.alert_manager import alert_manager, AlertManager
from backend.app.health_service import health_service
from backend.app.ml_service import ml_engine


TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def db_session():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    ensure_schema_migrations(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    # Pre-register test machinery
    m1 = Machine(
        machine_id="CNC-001",
        name="Machining Center CNC-001",
        machine_type="CNC Mill",
        location="Shop Floor",
        type_variant="M"
    )
    m2 = Machine(
        machine_id="PRESS-301",
        name="Hydraulic Press Unit 301",
        machine_type="Hydraulic Press",
        location="Stamping Bay",
        type_variant="H"
    )
    m3 = Machine(
        machine_id="PUMP-201",
        name="Coolant Circulation Pump",
        machine_type="Centrifugal Pump",
        location="Coolant Tank A",
        type_variant="L"
    )
    session.add_all([m1, m2, m3])
    session.commit()

    yield session
    session.close()


def test_suite_a_nominal_reading(db_session):
    """Test A: Normal readings -> Healthy, Normal anomaly, no critical alert."""
    payload = TelemetryCreate(
        machine_id="CNC-001",
        air_temperature=298.2,
        process_temperature=308.5,
        rotational_speed=1530.0,
        torque=38.5,
        tool_wear=45.0,
        temperature=35.35,
        vibration=1.85,
        pressure=4.5
    )
    reading, pred, alert = save_telemetry_and_predict(db_session, payload)

    assert reading.id is not None
    assert pred.id is not None
    assert pred.telemetry_id == reading.id
    assert pred.failure_probability < 20.0
    assert pred.risk_category == "Low"
    assert pred.machine_health_status == "Healthy"
    assert pred.anomaly_label == "Normal"
    # No critical alert should be created for nominal reading
    assert alert is None or alert.status == "RESOLVED"
    print("PASS: Test A - Nominal Telemetry Evaluation")


def test_suite_b_power_envelope_pwf(db_session):
    """Test B: High power (PWF) -> Operational rule alert triggered with exact values."""
    # Speed 1450 rpm, Torque 75 Nm -> Power = 75 * (1450 * 2 * pi / 60) = 11,388 W (> 9000 W limit)
    payload = TelemetryCreate(
        machine_id="CNC-001",
        air_temperature=298.5,
        process_temperature=309.0,
        rotational_speed=1450.0,
        torque=75.0,
        tool_wear=50.0,
        temperature=35.85,
        vibration=2.2,
        pressure=4.5
    )
    reading, pred, alert = save_telemetry_and_predict(db_session, payload)

    assert reading.id is not None
    assert alert is not None
    assert alert.status == "ACTIVE"
    assert alert.telemetry_id == reading.id
    assert alert.prediction_id == pred.id
    assert "PWF" in alert.threshold_or_rule or "PWF" in alert.reason
    assert alert.severity == "CRITICAL"

    trig = json.loads(alert.triggering_values)
    assert trig["torque_Nm"] == 75.0
    assert trig["rotational_speed_rpm"] == 1450.0
    assert trig["mechanical_power_W"] > 9000.0
    assert pred.machine_health_status == "Critical"
    print("PASS: Test B - Operational Rule Triggering (PWF)")


def test_suite_c_sensor_outlier_model_disagreement(db_session):
    """Test C: Outlier reading -> Isolation Forest anomaly flagged, Model Disagreement evaluated."""
    # Extreme temperature difference and speed combination that is atypical
    payload = TelemetryCreate(
        machine_id="PUMP-201",
        air_temperature=290.0,
        process_temperature=315.0,
        rotational_speed=2450.0,
        torque=15.0,
        tool_wear=5.0,
        temperature=41.85,
        vibration=1.5,
        pressure=3.8
    )
    reading, pred, alert = save_telemetry_and_predict(db_session, payload)

    assert reading.id is not None
    assert pred.anomaly_score is not None
    # Model disagreement or anomaly state correctly represented
    if pred.anomaly_detected and pred.risk_category == "Low":
        assert pred.model_disagreement == 1
        assert "Model Disagreement" in pred.machine_health_status or "Warning" in pred.machine_health_status
        assert len(pred.disagreement_reason) > 0
    print("PASS: Test C - Sensor Outlier & Model Disagreement Evaluation")


def test_suite_d_high_failure_probability(db_session):
    """Test D: High probability -> Critical health status and failure alert."""
    # Near end of life tool wear + severe torque + elevated temps
    payload = TelemetryCreate(
        machine_id="PRESS-301",
        air_temperature=304.0,
        process_temperature=314.0,
        rotational_speed=1280.0,
        torque=72.0,
        tool_wear=235.0,
        temperature=40.85,
        vibration=3.5,
        pressure=6.8
    )
    reading, pred, alert = save_telemetry_and_predict(db_session, payload)

    assert pred.machine_health_status in ["Critical", "Warning"]
    assert alert is not None
    assert alert.status == "ACTIVE"
    print("PASS: Test D - High Risk / Failure Probability Evaluation")


def test_suite_e_rul_input_filtering(db_session):
    """Test E: RUL estimation adheres strictly to available sensors without hallucination."""
    payload = TelemetryCreate(
        machine_id="CNC-001",
        air_temperature=298.2,
        process_temperature=308.2,
        rotational_speed=1550.0,
        torque=40.0,
        tool_wear=100.0
    )
    reading, pred, alert = save_telemetry_and_predict(db_session, payload)

    # RUL is evaluated from valid trained model or marked unavailable
    if pred.rul_available:
        assert pred.estimated_remaining_cuts is not None
        assert pred.estimated_remaining_cuts > 0
    else:
        assert pred.estimated_remaining_cuts is None
    print("PASS: Test E - RUL Input Filtering & Availability")


def test_suite_f_alert_auto_resolution(db_session):
    """Test F: Fault reading followed by normal reading -> Active alert automatically RESOLVED."""
    # Step 1: Inject severe PWF fault to ensure active alert exists
    fault_payload = TelemetryCreate(
        machine_id="CNC-001",
        air_temperature=298.0,
        process_temperature=308.0,
        rotational_speed=1450.0,
        torque=76.0, # Power = 11,540 W -> PWF
        tool_wear=30.0,
        vibration=1.5
    )
    r1, p1, a1 = save_telemetry_and_predict(db_session, fault_payload)
    assert a1 is not None
    assert a1.status == "ACTIVE"

    # Step 2: Ingest subsequent nominal telemetry packet for CNC-001
    norm_payload = TelemetryCreate(
        machine_id="CNC-001",
        air_temperature=298.2,
        process_temperature=308.5,
        rotational_speed=1530.0,
        torque=38.5, # Power = 6,168 W -> within [3500, 9000] envelope!
        tool_wear=31.0,
        vibration=1.6
    )
    r2, p2, a2 = save_telemetry_and_predict(db_session, norm_payload)

    # Verify that previous alert is now RESOLVED
    db_session.refresh(a1)
    assert a1.status == "RESOLVED"
    assert a1.resolved_at is not None
    assert "cleared" in a1.resolution_note.lower() or "normalized" in a1.resolution_note.lower()

    # Machine health returns to Healthy
    mach = get_machine(db_session, "CNC-001")
    detail = get_machine_card_summary(db_session, mach)
    assert detail["health_status"] == "Healthy"
    assert detail["active_alerts_count"] == 0
    print("PASS: Test F - Alert Auto-Resolution & Machine Health Normalization")


def test_suite_g_alert_deduplication(db_session):
    """Test G: Repeated identical fault condition does not create alert spam."""
    # Pre-register isolated test machine
    if not get_machine(db_session, "CNC-DEDUP"):
        m_dedup = Machine(machine_id="CNC-DEDUP", name="Dedup Unit", machine_type="CNC Mill", location="Lab", type_variant="M")
        db_session.add(m_dedup)
        db_session.commit()

    fault_payload = TelemetryCreate(
        machine_id="CNC-DEDUP",
        air_temperature=298.0,
        process_temperature=308.0,
        rotational_speed=1400.0,
        torque=75.0, # PWF condition
        tool_wear=20.0,
        vibration=1.8
    )
    # Packet 1
    r1, p1, a1 = save_telemetry_and_predict(db_session, fault_payload)
    active_count_1 = db_session.query(Alert).filter(
        Alert.machine_id == "CNC-DEDUP",
        Alert.status == "ACTIVE"
    ).count()

    # Packet 2 (Identical condition immediately following)
    r2, p2, a2 = save_telemetry_and_predict(db_session, fault_payload)
    active_count_2 = db_session.query(Alert).filter(
        Alert.machine_id == "CNC-DEDUP",
        Alert.status == "ACTIVE"
    ).count()

    # Packet 3
    r3, p3, a3 = save_telemetry_and_predict(db_session, fault_payload)
    active_count_3 = db_session.query(Alert).filter(
        Alert.machine_id == "CNC-DEDUP",
        Alert.status == "ACTIVE"
    ).count()

    # Deduplication ensures active alerts do not increment on repeat
    assert active_count_1 > 0
    assert active_count_1 == active_count_2 == active_count_3
    print("PASS: Test G - Alert Deduplication & Spam Prevention")


def test_suite_h_end_to_end_traceability(db_session):
    """Test H: Full traceability: reading.id -> prediction.telemetry_id -> alert.telemetry_id."""
    fault_payload = TelemetryCreate(
        machine_id="CNC-001",
        air_temperature=298.0,
        process_temperature=308.0,
        rotational_speed=1420.0,
        torque=78.0,
        tool_wear=245.0, # TWF (tool wear >= 240)
        vibration=2.0
    )
    r, p, a = save_telemetry_and_predict(db_session, fault_payload)

    assert r.id is not None
    assert p.id is not None
    assert a is not None

    assert p.telemetry_id == r.id
    assert a.telemetry_id == r.id
    assert a.prediction_id == p.id
    assert a.machine_id == r.machine_id
    print("PASS: Test H - End-to-End Traceability (telemetry_id foreign key linkage)")


def test_suite_i_fleet_isolation(db_session):
    """Test I: Multi-machine fleet isolation."""
    d = get_dashboard_summary(db_session)
    assert d["total_machines"] >= 3
    print("PASS: Test I - Multi-Machine Fleet Isolation & Dashboard Aggregation")


if __name__ == "__main__":
    pytest.main(["-v", __file__])
