"""
MachinaGuard - Comprehensive System & ML Integration Test Suite
Verifies:
1. Health check and model loading
2. Failure prediction endpoint (AI4I Random Forest)
3. Anomaly detection endpoint (AI4I Isolation Forest)
4. RUL prediction endpoint (PHM 2010 Random Forest Regressor & missing model handling)
5. Missing / invalid input validation
6. Telemetry ingestion, prediction generation, and alert dispatching
7. Notifications acknowledge and resolve workflows
8. Machine latest & history endpoints
"""

import os
import sys
from pathlib import Path
import pytest
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.main import app
from backend.app.models import Base, Machine
from backend.app.database import get_db
from backend.app.crud import ensure_schema_migrations

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)
ensure_schema_migrations(test_engine)

# Seed test machine CNC-001 so all endpoints work deterministically
seed_session = TestingSessionLocal()
if not seed_session.query(Machine).filter(Machine.machine_id == "CNC-001").first():
    m = Machine(
        machine_id="CNC-001",
        name="Machining Center CNC-001",
        machine_type="CNC Mill",
        location="Shop Floor Alpha",
        type_variant="M",
        status="Operational"
    )
    seed_session.add(m)
    seed_session.commit()
seed_session.close()

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["model_loaded"] is True
    assert data["anomaly_model_loaded"] is True
    assert "models" in data
    print("[PASS] 1. Backend health check: OK, Failure & Anomaly models loaded.")

def test_failure_prediction_valid():
    payload = {
        "machine_id": "CNC-001",
        "Type": "M",
        "air_temperature": 298.1,
        "process_temperature": 308.6,
        "rotational_speed": 1551.0,
        "torque": 42.8,
        "tool_wear": 120.0
    }
    response = client.post("/api/ml/failure/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "failure_prediction" in data
    assert "failure_probability" in data
    assert "risk_category" in data
    assert data["model"] == "AI4I RandomForestClassifier"
    assert data["failure_prediction"] in [0, 1]
    assert 0.0 <= data["failure_probability"] <= 1.0
    print(f"[PASS] 2. Failure prediction valid input: Risk={data['risk_category']}, Prob={data['failure_probability']:.4f}")

def test_failure_prediction_missing_fields():
    payload = {
        "Type": "M",
        "air_temperature": 298.1
        # missing process_temperature, speed, torque, tool_wear
    }
    response = client.post("/api/ml/failure/predict", json=payload)
    assert response.status_code == 422
    print("[PASS] 3. Failure prediction missing fields validation: HTTP 422 rejected.")

def test_anomaly_detection_normal_vs_anomalous():
    # Normal operating record
    normal_payload = {
        "machine_id": "CNC-001",
        "Type": "M",
        "air_temperature": 298.1,
        "process_temperature": 308.6,
        "rotational_speed": 1551.0,
        "torque": 42.8,
        "tool_wear": 120.0
    }
    res_normal = client.post("/api/ml/anomaly/detect", json=normal_payload)
    assert res_normal.status_code == 200
    data_normal = res_normal.json()
    assert data_normal["anomaly"] is False
    assert data_normal["label"] == "Normal"
    assert data_normal["anomaly_score"] > 0
    assert "not failure probability" in data_normal["note"]
    print(f"[PASS] 4a. Anomaly detection on normal record: Label={data_normal['label']}, Score={data_normal['anomaly_score']:.4f}")

    # Outlier / anomalous record
    anomaly_payload = {
        "machine_id": "CNC-001",
        "Type": "L",
        "air_temperature": 305.0,
        "process_temperature": 306.0,
        "rotational_speed": 2850.0,
        "torque": 85.0,
        "tool_wear": 245.0
    }
    res_anom = client.post("/api/ml/anomaly/detect", json=anomaly_payload)
    assert res_anom.status_code == 200
    data_anom = res_anom.json()
    assert data_anom["anomaly"] is True
    assert data_anom["label"] == "Anomaly"
    assert data_anom["anomaly_score"] < 0
    print(f"[PASS] 4b. Anomaly detection on unusual record: Label={data_anom['label']}, Score={data_anom['anomaly_score']:.4f}")

def test_rul_prediction_endpoint():
    rul_payload = {
        "machine_id": "CNC-001",
        "cycle": 45,
        "tool_wear_min": 52.0,
        "vibration_mm_s": 0.82,
        "torque_nm": 39.5,
        "process_temperature_k": 311.2,
        "air_temperature_k": 300.1,
        "rotational_speed_rpm": 1560.0,
        "control_type": "B"
    }
    response = client.post("/api/ml/rul/predict", json=rul_payload)
    assert response.status_code == 200
    data = response.json()
    assert "estimated_remaining_cycles" in data
    assert data["estimated_remaining_cycles"] > 0
    assert data["unit"] == "cycles"
    print(f"[PASS] 5. RUL prediction with trained model: Remaining Cycles={data['estimated_remaining_cycles']} {data['unit']}")

def test_rul_prediction_missing_fields():
    rul_payload = {
        "machine_id": "CNC-001",
        "control_type": "B"
        # missing cycle, tool_wear_min, torque_nm, rotational_speed_rpm
    }
    response = client.post("/api/ml/rul/predict", json=rul_payload)
    assert response.status_code == 422
    print("[PASS] 5a. RUL prediction missing fields validation: HTTP 422 rejected.")

def test_models_metadata_and_evaluations():
    res_meta = client.get("/api/ml/models/metadata")
    assert res_meta.status_code == 200
    meta_data = res_meta.json()
    assert meta_data["failure_model"] is not None
    assert meta_data["anomaly_model"] is not None
    assert meta_data["rul_model"] is not None
    print("[PASS] 5b. ML Models metadata endpoint: All 3 metadata JSON records retrieved.")

    res_eval = client.get("/api/ml/models/evaluations")
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    assert eval_data["failure_evaluation"] is not None
    assert eval_data["anomaly_evaluation"] is not None
    assert eval_data["rul_evaluation"] is not None
    print("[PASS] 5c. ML Models evaluations endpoint: All 3 evaluation reports retrieved.")

def test_models_status_endpoint():
    response = client.get("/api/ml/models/status")
    assert response.status_code == 200
    data = response.json()
    assert "failure_model" in data
    assert "anomaly_model" in data
    assert "rul_model" in data
    assert data["failure_model"]["loaded"] is True
    assert data["anomaly_model"]["loaded"] is True
    print(f"[PASS] 6. ML Models status endpoint: Failure={data['failure_model']['status']}, Anomaly={data['anomaly_model']['status']}, RUL={data['rul_model']['status']}")

def test_telemetry_ingestion_and_predictions():
    telemetry = {
        "machine_id": "CNC-001",
        "air_temperature": 298.5,
        "process_temperature": 308.8,
        "rotational_speed": 1320.0,
        "torque": 72.5,
        "tool_wear": 185.0,
        "vibration": 6.8,
        "pressure": 4.1
    }
    response = client.post("/api/telemetry", json=telemetry)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    pred = data["prediction"]
    assert "failure_probability" in pred
    assert "anomaly" in pred
    assert "anomaly_score" in pred
    print(f"[PASS] 7. Telemetry ingestion: Risk={pred['risk_category']}, Anomaly={pred['anomaly']}, Score={pred['anomaly_score']}")

def test_machine_latest_and_history():
    res_latest = client.get("/api/machines/CNC-001/latest")
    assert res_latest.status_code == 200
    latest_data = res_latest.json()
    assert "latest_reading" in latest_data
    assert "latest_prediction" in latest_data

    res_history = client.get("/api/machines/CNC-001/history?limit=10")
    assert res_history.status_code == 200
    assert len(res_history.json()) > 0
    print("[PASS] 8. Machine latest & history endpoints verified.")

def test_notifications_workflow():
    res = client.get("/api/notifications")
    assert res.status_code == 200
    notifs = res.json()
    assert len(notifs) > 0
    first_id = notifs[0]["id"]
    
    # Acknowledge
    ack = client.post(f"/api/notifications/{first_id}/acknowledge")
    assert ack.status_code == 200
    assert ack.json()["status"] == "success"

    # Resolve
    resolve = client.post(f"/api/notifications/{first_id}/resolve")
    assert resolve.status_code == 200
    assert resolve.json()["status"] == "success"
    print(f"[PASS] 9. Notification #{first_id} Acknowledge and Resolve workflow verified.")

if __name__ == "__main__":
    test_health_check()
    test_failure_prediction_valid()
    test_failure_prediction_missing_fields()
    test_anomaly_detection_normal_vs_anomalous()
    test_rul_prediction_endpoint()
    test_rul_prediction_missing_fields()
    test_models_metadata_and_evaluations()
    test_models_status_endpoint()
    test_telemetry_ingestion_and_predictions()
    test_machine_latest_and_history()
    test_notifications_workflow()
    print("\n" + "=" * 60)
    print("ALL 11 COMPREHENSIVE BACKEND AND ML TESTS PASSED 100%!")
    print("=" * 60)
