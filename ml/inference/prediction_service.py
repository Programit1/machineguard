"""
MachinaGuard Centralized ML Prediction Service
Encapsulates real-time inference for:
1. Machine Failure Prediction (AI4I Random Forest Classifier)
2. Operational Anomaly Detection (AI4I Isolation Forest)
3. Remaining Useful Life Regression (RUL Dataset Random Forest Regressor)
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger("machinaguard.inference")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

FAILURE_MODEL_PATH = os.path.join(ML_DIR, "models", "failure_model.joblib")
ANOMALY_MODEL_PATH = os.path.join(ML_DIR, "models", "anomaly_model.joblib")
RUL_MODEL_PATH = os.path.join(ML_DIR, "models", "rul_model.joblib")

# Fallback compatibility paths
COMPAT_FAILURE_MODEL_PATH = os.path.join(ML_DIR, "models", "predictive_maintenance_rf.joblib")
COMPAT_ANOMALY_MODEL_PATH = os.path.join(ML_DIR, "models", "isolation_forest_ai4i.joblib")

AI4I_COLUMNS = [
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
]

RUL_COLUMNS = [
    "cycle",
    "tool_wear_min",
    "vibration_mm_s",
    "torque_nm",
    "process_temperature_k",
    "air_temperature_k",
    "rotational_speed_rpm",
    "control_type",
]


class FailurePredictionService:
    def __init__(self, model_path: str = FAILURE_MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.version = "1.0.0"
        self._load()

    def _load(self):
        target_path = self.model_path
        if not os.path.exists(target_path) and os.path.exists(COMPAT_FAILURE_MODEL_PATH):
            target_path = COMPAT_FAILURE_MODEL_PATH

        if os.path.exists(target_path):
            self.model = joblib.load(target_path)
            logger.info("FailurePredictionService loaded from %s", target_path)
        else:
            logger.warning("Failure model not found at %s", target_path)

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def prepare_df(self, data: Dict[str, Any]) -> pd.DataFrame:
        air_temp = data.get("Air temperature [K]", data.get("air_temperature"))
        proc_temp = data.get("Process temperature [K]", data.get("process_temperature"))
        rot_speed = data.get("Rotational speed [rpm]", data.get("rotational_speed"))
        torque = data.get("Torque [Nm]", data.get("torque"))
        tool_wear = data.get("Tool wear [min]", data.get("tool_wear"))
        t_var = data.get("Type", data.get("type_variant", "M"))

        if t_var not in ["L", "M", "H"]:
            t_var = "M"

        # Safe Celsius to Kelvin conversion if raw sensor transmitted °C
        if air_temp is not None and float(air_temp) < 150.0:
            air_temp = float(air_temp) + 273.15
        if proc_temp is not None and float(proc_temp) < 150.0:
            proc_temp = float(proc_temp) + 273.15

        row = {
            "Type": str(t_var),
            "Air temperature [K]": float(air_temp) if air_temp is not None else 300.0,
            "Process temperature [K]": float(proc_temp) if proc_temp is not None else 310.0,
            "Rotational speed [rpm]": float(rot_speed) if rot_speed is not None else 1500.0,
            "Torque [Nm]": float(torque) if torque is not None else 40.0,
            "Tool wear [min]": float(tool_wear) if tool_wear is not None else 0.0,
        }
        return pd.DataFrame([row])[AI4I_COLUMNS]

    def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_loaded:
            raise RuntimeError("Failure prediction model is not loaded.")

        df = self.prepare_df(data)
        probs = self.model.predict_proba(df)
        raw_prob = float(probs[0, 1])  # Class 1 = Machine Failure
        prob_pct = round(raw_prob * 100.0, 2)
        if raw_prob > 0.0 and prob_pct == 0.0:
            prob_pct = round(raw_prob * 100.0, 6)
        prediction_bin = int(raw_prob >= 0.5)

        # Risk categorization according to specified thresholds:
        # Low: below 20%
        # Medium: 20% to below 50%
        # High: 50% to below 80%
        # Critical: 80% or above
        if prob_pct >= 80.0:
            risk_category = "Critical"
        elif prob_pct >= 50.0:
            risk_category = "High"
        elif prob_pct >= 20.0:
            risk_category = "Medium"
        else:
            risk_category = "Low"

        # Diagnose physical factors
        factors = []
        rec = "Operational telemetry is nominal. Normal operations permitted."
        torque_val = df["Torque [Nm]"].iloc[0]
        tool_wear_val = df["Tool wear [min]"].iloc[0]
        speed_val = df["Rotational speed [rpm]"].iloc[0]
        delta_t = df["Process temperature [K]"].iloc[0] - df["Air temperature [K]"].iloc[0]

        if tool_wear_val * torque_val > 11000:
            factors.append("Overstrain Anomaly (Excessive wear × torque product)")
            rec = "Critical overstrain detected. Unload spindle and reduce operational feed."
        if delta_t < 8.6 and speed_val < 1380:
            factors.append("Heat Dissipation Anomaly (Inadequate thermal dissipation)")
            rec = "Thermal dissipation limit reached. Check spindle cooling lines."
        if tool_wear_val >= 200:
            factors.append("Tool Wear Anomaly (Flank wear near EOL threshold)")
            rec = "Tool wear limit reached (>=200 min). Schedule cutting insert replacement."

        return {
            "failure_prediction": prediction_bin,
            "failure_probability": raw_prob,
            "failure_probability_pct": prob_pct,
            "risk_category": risk_category,
            "contributing_factors": factors,
            "recommendation": rec,
            "model_name": "AI4I RandomForestClassifier",
            "model_version": self.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class AnomalyDetectionService:
    def __init__(self, model_path: str = ANOMALY_MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.version = "1.0.0"
        self._load()

    def _load(self):
        target_path = self.model_path
        if not os.path.exists(target_path) and os.path.exists(COMPAT_ANOMALY_MODEL_PATH):
            target_path = COMPAT_ANOMALY_MODEL_PATH

        if os.path.exists(target_path):
            self.model = joblib.load(target_path)
            logger.info("AnomalyDetectionService loaded from %s", target_path)
        else:
            logger.warning("Anomaly model not found at %s", target_path)

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def prepare_df(self, data: Dict[str, Any]) -> pd.DataFrame:
        air_temp = data.get("Air temperature [K]", data.get("air_temperature"))
        proc_temp = data.get("Process temperature [K]", data.get("process_temperature"))
        rot_speed = data.get("Rotational speed [rpm]", data.get("rotational_speed"))
        torque = data.get("Torque [Nm]", data.get("torque"))
        tool_wear = data.get("Tool wear [min]", data.get("tool_wear"))
        t_var = data.get("Type", data.get("type_variant", "M"))

        if t_var not in ["L", "M", "H"]:
            t_var = "M"

        if air_temp is not None and float(air_temp) < 150.0:
            air_temp = float(air_temp) + 273.15
        if proc_temp is not None and float(proc_temp) < 150.0:
            proc_temp = float(proc_temp) + 273.15

        row = {
            "Type": str(t_var),
            "Air temperature [K]": float(air_temp) if air_temp is not None else 300.0,
            "Process temperature [K]": float(proc_temp) if proc_temp is not None else 310.0,
            "Rotational speed [rpm]": float(rot_speed) if rot_speed is not None else 1500.0,
            "Torque [Nm]": float(torque) if torque is not None else 40.0,
            "Tool wear [min]": float(tool_wear) if tool_wear is not None else 0.0,
        }
        return pd.DataFrame([row])[AI4I_COLUMNS]

    def detect(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_loaded:
            raise RuntimeError("Anomaly detection model is not loaded.")

        df = self.prepare_df(data)

        # Handle Pipeline (preprocessor + detector)
        if hasattr(self.model, "named_steps"):
            prep = self.model.named_steps["preprocessor"]
            detector = self.model.named_steps["detector"]
            X_trans = prep.transform(df)
            score = float(detector.decision_function(X_trans)[0])
            pred = int(detector.predict(X_trans)[0])
        else:
            score = float(self.model.decision_function(df)[0])
            pred = int(self.model.predict(df)[0])

        is_anomaly = bool(pred == -1)
        label = "Anomaly" if is_anomaly else "Normal"

        return {
            "anomaly": is_anomaly,
            "anomaly_detected": is_anomaly,
            "label": label,
            "anomaly_score": round(score, 4),
            "model_name": "AI4I IsolationForest",
            "model_version": self.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Anomaly score is an unsupervised metric and not a machine-failure probability.",
        }


class RULPredictionService:
    def __init__(self, model_path: str = RUL_MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.version = "1.0.0"
        self._load()

    def _load(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            logger.info("RULPredictionService loaded from %s", self.model_path)
        else:
            logger.warning("RUL model not found at %s", self.model_path)

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def prepare_df(self, data: Dict[str, Any]) -> pd.DataFrame:
        cycle = float(data.get("cycle", 1))
        tool_wear = max(0.0, float(data.get("tool_wear_min", data.get("tool_wear", 0.0))))
        vibe = data.get("vibration_mm_s", data.get("vibration"))
        torque = data.get("torque_nm", data.get("torque"))
        proc_temp = data.get("process_temperature_k", data.get("process_temperature"))
        air_temp = data.get("air_temperature_k", data.get("air_temperature"))
        speed = data.get("rotational_speed_rpm", data.get("rotational_speed", 1500.0))
        ctrl = str(data.get("control_type", "A")).upper()

        if ctrl not in ["A", "B", "C"]:
            ctrl = "A"

        # Safe unit conversions
        if air_temp is not None and float(air_temp) < 150.0:
            air_temp = float(air_temp) + 273.15
        if proc_temp is not None and float(proc_temp) < 150.0:
            proc_temp = float(proc_temp) + 273.15

        row = {
            "cycle": cycle,
            "tool_wear_min": tool_wear,
            "vibration_mm_s": float(vibe) if vibe is not None else np.nan,
            "torque_nm": float(torque) if torque is not None else np.nan,
            "process_temperature_k": float(proc_temp) if proc_temp is not None else 310.0,
            "air_temperature_k": float(air_temp) if air_temp is not None else np.nan,
            "rotational_speed_rpm": float(speed),
            "control_type": ctrl,
        }
        return pd.DataFrame([row])[RUL_COLUMNS]

    def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_loaded:
            raise RuntimeError("RUL prediction model is not trained or loaded. Run ml/training/train_rul.py.")

        df = self.prepare_df(data)
        pred_rul = float(self.model.predict(df)[0])
        pred_rul = max(0.0, round(pred_rul, 1))

        machine_id = str(data.get("machine_id", data.get("unit_id", "UNKNOWN")))

        return {
            "machine_id": machine_id,
            "estimated_remaining_cycles": pred_rul,
            "estimated_remaining_cuts": pred_rul,  # compatibility alias
            "unit": "cycles",
            "model_name": "MachinaGuard RUL Regressor",
            "model_version": self.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Remaining useful life forecast based on current operational degradation trajectory.",
        }


class CentralizedMLEngine:
    """Unified engine coordinating all 3 ML models for MachinaGuard."""

    def __init__(self):
        self.failure_service = FailurePredictionService()
        self.anomaly_service = AnomalyDetectionService()
        self.rul_service = RULPredictionService()

    def reload_all(self):
        self.failure_service._load()
        self.anomaly_service._load()
        self.rul_service._load()

    def get_status(self) -> Dict[str, Any]:
        return {
            "failure_model": {
                "name": "Machine Failure Classifier",
                "loaded": self.failure_service.is_loaded,
                "version": self.failure_service.version,
                "dataset": "UCI AI4I 2020 Predictive Maintenance Dataset",
            },
            "anomaly_model": {
                "name": "Operational Anomaly Detector",
                "loaded": self.anomaly_service.is_loaded,
                "version": self.anomaly_service.version,
                "dataset": "UCI AI4I 2020 (Nominal records)",
            },
            "rul_model": {
                "name": "Remaining Useful Life Regressor",
                "loaded": self.rul_service.is_loaded,
                "version": self.rul_service.version,
                "dataset": "RUL Dataset (readings.csv, units.csv)",
            },
            "all_ready": self.failure_service.is_loaded and self.anomaly_service.is_loaded and self.rul_service.is_loaded,
        }


# Singleton instance
ml_engine = CentralizedMLEngine()
