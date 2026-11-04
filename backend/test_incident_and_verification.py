import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Machine, SensorReading, Prediction, Alert, Incident, MaintenanceLog, IncidentVerification

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(Machine(
        machine_id="CNC-001",
        name="Precision CNC Mill 01",
        machine_type="CNC Mill",
        location="Bay 1",
        description="5-axis titanium CNC mill",
        type_variant="M",
        status="ONLINE"
    ))
    db.commit()
    db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def test_critical_incident_creation_and_deduplication(client):
    """Verify critical operational faults create incidents and deduplicate active incidents."""
    osf_payload = {
        "machine_id": "CNC-001",
        "air_temperature": 298.15,
        "process_temperature": 308.65,
        "rotational_speed": 1420.0,
        "torque": 66.0,
        "tool_wear": 220.0,
        "vibration": 3.8
    }
    resp1 = client.post("/api/telemetry", json=osf_payload)
    assert resp1.status_code == 201

    inc_resp = client.get("/api/incidents?machine_id=CNC-001")
    assert inc_resp.status_code == 200
    incidents = inc_resp.json()
    assert len(incidents) >= 1
    osf_inc = next((i for i in incidents if i["condition_type"] == "OSF"), None)
    assert osf_inc is not None
    assert osf_inc["status"] == "Open"
    assert osf_inc["severity"] == "CRITICAL"
    assert "Overstrain" in osf_inc["title"]

    resp2 = client.post("/api/telemetry", json=osf_payload)
    assert resp2.status_code == 201
    inc_resp2 = client.get("/api/incidents?machine_id=CNC-001")
    incidents2 = inc_resp2.json()
    osf_count = sum(1 for i in incidents2 if i["condition_type"] == "OSF" and i["status"] in ["Open", "Acknowledged", "Under Maintenance", "Verification Pending"])
    assert osf_count == 1, "Duplicate active incident created for sustained fault!"


def test_maintenance_logging_and_successful_verification(client):
    """Verify operator logs maintenance, moves to Verification Pending, and 3 healthy cycles resolve the incident."""
    osf_payload = {
        "machine_id": "CNC-001",
        "air_temperature": 298.15,
        "process_temperature": 308.65,
        "rotational_speed": 1420.0,
        "torque": 68.0,
        "tool_wear": 225.0
    }
    client.post("/api/telemetry", json=osf_payload)
    inc_list = client.get("/api/incidents?machine_id=CNC-001").json()
    incident = inc_list[0]
    inc_id = incident["incident_id"]

    maint_payload = {
        "machine_id": "CNC-001",
        "action": "Replaced worn cutter insert and reset spindle torque calibration",
        "technician": "Operator Sarah",
        "notes": "Spindle runs smooth; new carbide insert mounted."
    }
    maint_resp = client.post(f"/api/incidents/{inc_id}/maintenance", json=maint_payload)
    assert maint_resp.status_code == 201

    inc_after_maint = client.get(f"/api/incidents/{inc_id}").json()
    assert inc_after_maint["status"] == "Verification Pending"

    healthy_payload = {
        "machine_id": "CNC-001",
        "air_temperature": 298.15,
        "process_temperature": 308.65,
        "rotational_speed": 1520.0,
        "torque": 38.0,
        "tool_wear": 15.0,
        "vibration": 1.4
    }

    # Cycle 1: Verification in progress (1/3)
    client.post("/api/telemetry", json=healthy_payload)
    v1 = client.get(f"/api/incidents/{inc_id}/verifications").json()
    assert len(v1) >= 1
    assert v1[0]["status"] == "IN_PROGRESS"
    assert v1[0]["consecutive_healthy_count"] == 1
    inc_state1 = client.get(f"/api/incidents/{inc_id}").json()
    assert inc_state1["status"] == "Verification Pending"

    # Cycle 2: Verification in progress (2/3)
    client.post("/api/telemetry", json=healthy_payload)
    v2 = client.get(f"/api/incidents/{inc_id}/verifications").json()
    assert v2[0]["consecutive_healthy_count"] == 2

    # Cycle 3: Verification completes (3/3) -> RESOLVED
    client.post("/api/telemetry", json=healthy_payload)
    v3 = client.get(f"/api/incidents/{inc_id}/verifications").json()
    assert v3[0]["status"] == "RESOLVED"
    assert v3[0]["consecutive_healthy_count"] >= 3
    assert "RECOVERY VERIFIED" in v3[0]["evidence"]

    final_inc = client.get(f"/api/incidents/{inc_id}").json()
    assert final_inc["status"] == "Resolved"
    assert final_inc["resolved_at"] is not None


def test_failed_maintenance_verification_when_fault_persists(client):
    """Verify that if abnormal conditions recur during verification, the incident is marked 'Not Fixed'."""
    twf_payload = {
        "machine_id": "CNC-001",
        "air_temperature": 298.15,
        "process_temperature": 308.65,
        "rotational_speed": 1400.0,
        "torque": 40.0,
        "tool_wear": 245.0
    }
    client.post("/api/telemetry", json=twf_payload)
    inc_list = client.get("/api/incidents?machine_id=CNC-001").json()
    incident = inc_list[0]
    inc_id = incident["incident_id"]

    client.post(f"/api/incidents/{inc_id}/maintenance", json={
        "machine_id": "CNC-001",
        "action": "Inspected cutter without replacement",
        "technician": "Operator Mark"
    })

    client.post("/api/telemetry", json=twf_payload)

    v = client.get(f"/api/incidents/{inc_id}/verifications").json()
    assert len(v) >= 1
    assert v[0]["status"] == "NOT FIXED"
    assert "VERIFICATION FAILED" in v[0]["evidence"]

    inc_state = client.get(f"/api/incidents/{inc_id}").json()
    assert inc_state["status"] == "Not Fixed"


def test_maintenance_history_and_incident_preservation(client):
    """Verify maintenance records and incident histories are fully preserved."""
    m_resp = client.post("/api/maintenance", json={
        "machine_id": "CNC-001",
        "action": "Semi-annual spindle lubrication and filter replacement",
        "technician": "Maintenance Lead Dana",
        "notes": "Lubrication reservoir topped up with Mobil Vactra No. 2"
    })
    assert m_resp.status_code == 201

    history = client.get("/api/maintenance?machine_id=CNC-001").json()
    assert len(history) >= 1
    assert any("lubrication" in h["action"].lower() for h in history)
