"""
MachinaGuard ML Models Unit and Integration Test Suite
Validates all 3 ML models:
1. Machine Failure Classifier (RandomForestClassifier)
2. Operational Anomaly Detector (IsolationForest)
3. Remaining Useful Life Regressor (RandomForestRegressor)
"""

import os
import sys
import pytest

# Ensure ml and project root are importable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(ML_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if ML_DIR not in sys.path:
    sys.path.insert(0, ML_DIR)

from ml.inference.prediction_service import (
    FailurePredictionService,
    AnomalyDetectionService,
    RULPredictionService,
    CentralizedMLEngine,
)


@pytest.fixture
def failure_service():
    service = FailurePredictionService()
    assert service.is_loaded, "Failure model must be loaded."
    return service


@pytest.fixture
def anomaly_service():
    service = AnomalyDetectionService()
    assert service.is_loaded, "Anomaly model must be loaded."
    return service


@pytest.fixture
def rul_service():
    service = RULPredictionService()
    assert service.is_loaded, "RUL model must be loaded."
    return service


def test_failure_model_nominal_input(failure_service):
    nominal_payload = {
        "Type": "M",
        "Air temperature [K]": 298.5,
        "Process temperature [K]": 308.6,
        "Rotational speed [rpm]": 1500,
        "Torque [Nm]": 40.0,
        "Tool wear [min]": 20,
    }
    result = failure_service.predict(nominal_payload)

    assert result["failure_prediction"] == 0
    assert 0.0 <= result["failure_probability"] < 0.35
    assert result["risk_category"] in ["Low", "Medium"]
    assert "model_name" in result
    assert "timestamp" in result


def test_failure_model_overstrain_input(failure_service):
    overstrain_payload = {
        "Type": "L",
        "Air temperature [K]": 302.0,
        "Process temperature [K]": 311.5,
        "Rotational speed [rpm]": 1380,
        "Torque [Nm]": 68.0,
        "Tool wear [min]": 230,
    }
    result = failure_service.predict(overstrain_payload)

    assert result["failure_probability"] >= 0.50
    assert result["risk_category"] in ["High", "Critical"]
    assert any("Overstrain" in f or "Tool Wear" in f for f in result["contributing_factors"])


def test_failure_model_celsius_conversion(failure_service):
    # Sensor transmits in Celsius (<150°C)
    celsius_payload = {
        "Type": "M",
        "air_temperature": 25.0,  # 298.15 K
        "process_temperature": 35.0,  # 308.15 K
        "rotational_speed": 1520,
        "torque": 38.5,
        "tool_wear": 15,
    }
    result = failure_service.predict(celsius_payload)
    assert 0.0 <= result["failure_probability"] <= 1.0


def test_anomaly_model_normal_input(anomaly_service):
    normal_payload = {
        "Type": "M",
        "Air temperature [K]": 298.2,
        "Process temperature [K]": 308.4,
        "Rotational speed [rpm]": 1520,
        "Torque [Nm]": 39.5,
        "Tool wear [min]": 35,
    }
    result = anomaly_service.detect(normal_payload)

    assert result["anomaly"] is False
    assert result["label"] == "Normal"
    assert result["anomaly_score"] > 0.0, "Nominal data should have positive Isolation Forest score."
    assert "not a machine-failure probability" in result["note"].lower()


def test_anomaly_model_extreme_outlier(anomaly_service):
    outlier_payload = {
        "Type": "H",
        "Air temperature [K]": 320.0,
        "Process temperature [K]": 340.0,
        "Rotational speed [rpm]": 2850,  # Far outside AI4I operational envelope
        "Torque [Nm]": 85.0,
        "Tool wear [min]": 248,
    }
    result = anomaly_service.detect(outlier_payload)

    assert result["anomaly"] is True
    assert result["label"] == "Anomaly"
    assert result["anomaly_score"] < 0.0, "Extreme outlier should have negative Isolation Forest score."


def test_rul_model_valid_prediction(rul_service):
    rul_payload = {
        "machine_id": "CNC-001",
        "cycle": 45,
        "tool_wear_min": 52.0,
        "vibration_mm_s": 0.82,
        "torque_nm": 39.5,
        "process_temperature_k": 311.2,
        "air_temperature_k": 300.1,
        "rotational_speed_rpm": 1560.0,
        "control_type": "B",
    }
    result = rul_service.predict(rul_payload)

    assert result["unit"] == "cycles"
    assert result["machine_id"] == "CNC-001"
    assert result["estimated_remaining_cycles"] > 0
    assert result["estimated_remaining_cycles"] == result["estimated_remaining_cuts"]
    assert "timestamp" in result


def test_rul_model_handles_missing_sensor_channels(rul_service):
    # Control A: vibration_mm_s is missing in the dataset schema
    rul_payload_control_a = {
        "machine_id": "CNC-002",
        "cycle": 10,
        "tool_wear_min": 10.0,
        "vibration_mm_s": None,  # Missing channel for control A
        "torque_nm": 41.2,
        "process_temperature_k": 310.5,
        "air_temperature_k": 299.8,
        "rotational_speed_rpm": 1580.0,
        "control_type": "A",
    }
    result = rul_service.predict(rul_payload_control_a)
    assert result["estimated_remaining_cycles"] > 0


def test_rul_model_higher_cycle_lower_rul(rul_service):
    early_cycle = {
        "machine_id": "CNC-001",
        "cycle": 5,
        "tool_wear_min": 8.0,
        "vibration_mm_s": 0.75,
        "torque_nm": 38.0,
        "process_temperature_k": 310.0,
        "air_temperature_k": 299.5,
        "rotational_speed_rpm": 1600.0,
        "control_type": "B",
    }
    late_cycle = {
        "machine_id": "CNC-001",
        "cycle": 240,
        "tool_wear_min": 210.0,
        "vibration_mm_s": 1.45,
        "torque_nm": 52.0,
        "process_temperature_k": 315.0,
        "air_temperature_k": 301.0,
        "rotational_speed_rpm": 1390.0,
        "control_type": "B",
    }
    rul_early = rul_service.predict(early_cycle)["estimated_remaining_cycles"]
    rul_late = rul_service.predict(late_cycle)["estimated_remaining_cycles"]

    assert rul_early > rul_late, f"Early cycle RUL ({rul_early}) should be greater than late cycle RUL ({rul_late})"


def test_centralized_engine_status():
    engine = CentralizedMLEngine()
    status = engine.get_status()

    assert status["all_ready"] is True
    assert status["failure_model"]["loaded"] is True
    assert status["anomaly_model"]["loaded"] is True
    assert status["rul_model"]["loaded"] is True
