import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
import joblib

from .config import (
    FAILURE_MODEL_PATH, ANOMALY_MODEL_PATH, RUL_MODEL_PATH,
    FAILURE_METADATA_PATH, ANOMALY_METADATA_PATH, RUL_METADATA_PATH
)

logger = logging.getLogger(__name__)

AI4I_COLUMNS = [
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]"
]

PHM_REQUIRED_FEATURES = [
    "force_x_rms",
    "force_y_rms",
    "force_z_rms",
    "vibration_x_rms",
    "vibration_y_rms",
    "vibration_z_rms",
    "ae_rms"
]


class FailurePredictionService:
    """
    Module 1: Machine Failure Prediction
    Preserved AI4I 2020 Random Forest Classifier.
    """
    def __init__(self, model_path: str = FAILURE_MODEL_PATH, metadata_path: str = FAILURE_METADATA_PATH):
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self.model = None
        self.metadata = {}
        self.load()

    def load(self):
        try:
            if self.model_path.exists():
                self.model = joblib.load(self.model_path)
                logger.info("Failure Prediction model loaded from %s", self.model_path)
            else:
                logger.warning("Failure Prediction model not found at %s", self.model_path)
                
            if self.metadata_path.exists():
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
        except Exception as e:
            logger.error("Failed to load Failure Prediction model: %s", e)

    def is_loaded(self) -> bool:
        return self.model is not None

    def prepare_df(self, type_variant: str, air_temp: float, proc_temp: float,
                   rot_speed: float, torque_val: float, tool_wear_val: float) -> pd.DataFrame:
        # Convert Celsius to Kelvin if required (< 150)
        air_k = float(air_temp)
        if air_k < 150.0:
            air_k += 273.15

        proc_k = float(proc_temp)
        if proc_k < 150.0:
            proc_k += 273.15

        tvar = (type_variant or "M").strip().upper()
        if tvar not in ["L", "M", "H"]:
            tvar = "M"

        row = {
            "Type": tvar,
            "Air temperature [K]": air_k,
            "Process temperature [K]": proc_k,
            "Rotational speed [rpm]": float(rot_speed),
            "Torque [Nm]": float(torque_val),
            "Tool wear [min]": float(tool_wear_val)
        }
        return pd.DataFrame([row])[AI4I_COLUMNS]

    def predict(self, type_variant: str, air_temp: float, proc_temp: float,
                rot_speed: float, torque_val: float, tool_wear_val: float) -> Dict[str, Any]:
        if not self.is_loaded():
            raise RuntimeError(f"Failure Prediction model artifact missing at {self.model_path}")

        df = self.prepare_df(type_variant, air_temp, proc_temp, rot_speed, torque_val, tool_wear_val)
        probs = self.model.predict_proba(df)
        raw_prob = float(probs[0, 1])
        prediction_flag = int(self.model.predict(df)[0])
        # Convert to percentage and preserve non-zero decimal scale for small probabilities
        prob_pct = round(raw_prob * 100.0, 2)
        if raw_prob > 0.0 and prob_pct == 0.0:
            prob_pct = round(raw_prob * 100.0, 6)

        # Categorize risk according to specified thresholds:
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

        # Diagnose contributing factors & root causes
        air_k = df["Air temperature [K]"].iloc[0]
        proc_k = df["Process temperature [K]"].iloc[0]
        temp_diff = proc_k - air_k
        speed = df["Rotational speed [rpm]"].iloc[0]
        torque = df["Torque [Nm]"].iloc[0]
        wear = df["Tool wear [min]"].iloc[0]
        power_W = torque * (speed * 2.0 * np.pi / 60.0)
        overstrain = wear * torque
        tvar = df["Type"].iloc[0]
        osf_limit = 11000 if tvar == "L" else (12000 if tvar == "M" else 13000)

        contributing = []
        if temp_diff < 8.6 and speed < 1380.0:
            contributing.append(f"Heat Dissipation Failure (HDF): Thermal delta ({temp_diff:.1f} K) collapsed below 8.6 K at {speed:.0f} rpm.")
        elif temp_diff < 8.6:
            contributing.append(f"Low thermal dissipation delta ({temp_diff:.1f} K between process and ambient).")

        if power_W < 3500.0 or power_W > 9000.0:
            contributing.append(f"Power Failure (PWF): Motor mechanical drive power ({power_W:.0f} W) outside safe envelope (3500–9000 W).")

        if overstrain > osf_limit:
            contributing.append(f"Overstrain Failure (OSF): Cumulative cutting strain ({overstrain:.0f} min·Nm) exceeds structural limit ({osf_limit} min·Nm).")

        if wear >= 200.0:
            contributing.append(f"Tool Wear Failure (TWF): Cutting tool wear ({wear:.0f} min) nearing critical end-of-life.")
        elif wear >= 150.0:
            contributing.append(f"Elevated tool wear ({wear:.0f} min - replacement recommended during upcoming maintenance window).")

        if torque > 65.0:
            contributing.append(f"Excessive spindle torque load ({torque:.1f} Nm).")
        if speed > 2500.0:
            contributing.append(f"Elevated spindle rotational speed ({speed:.0f} rpm).")
        elif speed < 1200.0:
            contributing.append(f"Spindle under-speed stall condition ({speed:.0f} rpm).")

        if not contributing and prob_pct < 20.0:
            contributing.append("All mechanical and thermal telemetry parameters within nominal operating bounds.")

        # Prescriptive maintenance recommendations
        if risk_category == "Critical":
            rec = "Emergency shutdown recommended. Immediate inspection of cutting tool insert, spindle motor drive, and cooling loop airflow."
        elif risk_category == "High":
            rec = "Priority inspection required within 24 operational hours. Verify coolant concentration, inspect cutting insert, and check spindle load."
        elif risk_category == "Medium":
            rec = "Minor condition deviation detected. Monitor tool wear progression and verify spindle operating parameters."
        else:
            rec = "System operating normally. Continue standard preventative maintenance schedule."

        return {
            "failure_prediction": prediction_flag,
            "failure_probability": raw_prob,
            "failure_probability_pct": prob_pct,
            "risk_category": risk_category,
            "contributing_factors": contributing,
            "recommendation": rec,
            "model": "AI4I RandomForestClassifier",
            "version": "1.0.0"
        }


class AnomalyDetectionService:
    """
    Module 2: Anomaly Detection
    Isolation Forest trained on normal AI4I operating records (Machine failure == 0).
    """
    def __init__(self, model_path: str = ANOMALY_MODEL_PATH, metadata_path: str = ANOMALY_METADATA_PATH):
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self.model = None
        self.metadata = {}
        self.load()

    def load(self):
        try:
            if self.model_path.exists():
                self.model = joblib.load(self.model_path)
                logger.info("Anomaly Detection model loaded from %s", self.model_path)
            else:
                logger.warning("Anomaly Detection model not found at %s", self.model_path)
                
            if self.metadata_path.exists():
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
        except Exception as e:
            logger.error("Failed to load Anomaly Detection model: %s", e)

    def is_loaded(self) -> bool:
        return self.model is not None

    def prepare_df(self, type_variant: str, air_temp: float, proc_temp: float,
                   rot_speed: float, torque_val: float, tool_wear_val: float) -> pd.DataFrame:
        air_k = float(air_temp)
        if air_k < 150.0: air_k += 273.15
        proc_k = float(proc_temp)
        if proc_k < 150.0: proc_k += 273.15
        tvar = (type_variant or "M").strip().upper()
        if tvar not in ["L", "M", "H"]: tvar = "M"

        row = {
            "Type": tvar,
            "Air temperature [K]": air_k,
            "Process temperature [K]": proc_k,
            "Rotational speed [rpm]": float(rot_speed),
            "Torque [Nm]": float(torque_val),
            "Tool wear [min]": float(tool_wear_val)
        }
        return pd.DataFrame([row])[AI4I_COLUMNS]

    def detect(self, type_variant: str, air_temp: float, proc_temp: float,
               rot_speed: float, torque_val: float, tool_wear_val: float) -> Dict[str, Any]:
        if not self.is_loaded():
            raise RuntimeError(f"Anomaly Detection model artifact missing at {self.model_path}")

        df = self.prepare_df(type_variant, air_temp, proc_temp, rot_speed, torque_val, tool_wear_val)
        
        # Isolation Forest prediction: +1 normal, -1 anomaly
        pred_label = self.model.predict(df)[0]
        is_anomaly = bool(pred_label == -1)
        
        # Decision function score: lower/negative = more unusual
        detector = self.model.named_steps.get("detector")
        preprocessor = self.model.named_steps.get("preprocessor")
        if detector is not None and preprocessor is not None:
            score = float(detector.decision_function(preprocessor.transform(df))[0])
        else:
            score = float(self.model.decision_function(df)[0])

        return {
            "anomaly": is_anomaly,
            "label": "Anomaly" if is_anomaly else "Normal",
            "anomaly_score": round(score, 4),
            "model": "AI4I IsolationForest",
            "version": "1.0.0",
            "note": "Anomaly score is not failure probability."
        }


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


class RULPredictionService:
    """
    Module 3: Remaining Useful Life (RUL) Prediction
    MachinaGuard Random Forest Regressor trained on RUL dataset.
    Predicts remaining operating life in cycles.
    """
    def __init__(self, model_path: str = RUL_MODEL_PATH, metadata_path: str = RUL_METADATA_PATH):
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self.model = None
        self.feature_names = RUL_COLUMNS
        self.metadata = {}
        self.load()

    def load(self):
        try:
            if self.model_path.exists():
                loaded = joblib.load(self.model_path)
                if isinstance(loaded, dict) and "model" in loaded:
                    self.model = loaded["model"]
                    self.feature_names = loaded.get("features", RUL_COLUMNS)
                else:
                    self.model = loaded
                    self.feature_names = RUL_COLUMNS
                logger.info("RUL Prediction model loaded from %s", self.model_path)
            else:
                logger.warning("RUL model not found at %s.", self.model_path)

            if self.metadata_path.exists():
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
        except Exception as e:
            logger.error("Failed to load RUL model: %s", e)

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

        # Safe conversion if in Celsius
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

    def predict(self, sensor_features: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_loaded():
            raise RuntimeError(
                "RUL prediction model is not currently trained or available. "
                "Run 'python ml/training/train_rul.py' to train the RUL model on ml/data/rul_dataset/."
            )

        df = self.prepare_df(sensor_features)
        predicted_cycles = max(0.0, float(self.model.predict(df)[0]))

        return {
            "estimated_remaining_cycles": round(predicted_cycles, 1),
            "estimated_remaining_cuts": round(predicted_cycles, 1),  # Compatibility alias
            "unit": "cycles",
            "model": "MachinaGuard RUL Regressor",
            "version": "1.0.0",
            "note": "Remaining useful life forecast based on current operational degradation trajectory.",
        }


class MLPredictionEngine:
    """
    Central Engine managing all three prediction services and telemetry processing.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MLPredictionEngine, cls).__new__(cls)
            cls._instance._init_services()
        return cls._instance

    def _init_services(self):
        self.failure_service = FailurePredictionService()
        self.anomaly_service = AnomalyDetectionService()
        self.rul_service = RULPredictionService()

    @property
    def model(self):
        return self.failure_service.model

    @property
    def metadata(self):
        return self.failure_service.metadata

    def predict(self,
                air_temperature: Optional[float] = None,
                process_temperature: Optional[float] = None,
                rotational_speed: Optional[float] = None,
                torque: Optional[float] = None,
                tool_wear: Optional[float] = None,
                type_variant: str = "M",
                temperature: Optional[float] = None,
                vibration: Optional[float] = None,
                pressure: Optional[float] = None,
                power_consumption: Optional[float] = None,
                operating_load: Optional[float] = None,
                machine_type: str = "Machine") -> Dict[str, Any]:
        """
        Processes multi-sensor telemetry, evaluates Failure Prediction, executes Anomaly Detection,
        and determines RUL availability.
        """
        required_ai4i = [air_temperature, process_temperature, rotational_speed, torque, tool_wear]
        has_ai4i_features = all(v is not None for v in required_ai4i)

        if not has_ai4i_features:
            missing_fields = []
            if air_temperature is None: missing_fields.append("air_temperature")
            if process_temperature is None: missing_fields.append("process_temperature")
            if rotational_speed is None: missing_fields.append("rotational_speed")
            if torque is None: missing_fields.append("torque")
            if tool_wear is None: missing_fields.append("tool_wear")

            return {
                "prediction_available": False,
                "failure_prediction": 0,
                "failure_probability": None,
                "risk_category": "Low",
                "anomaly": False,
                "anomaly_score": None,
                "anomaly_label": "Normal",
                "rul_available": False,
                "estimated_remaining_cuts": None,
                "rul_unit": "machining cuts",
                "contributing_factors": [
                    f"Prediction unavailable for this reading: missing required AI4I physical features ({', '.join(missing_fields)})."
                ],
                "recommendation": "Configure telemetry source to provide AI4I physical sensor fields (rotational_speed, torque, tool_wear, air_temperature, process_temperature) to enable ML failure forecasting."
            }

        if not self.failure_service.is_loaded():
            return {
                "prediction_available": False,
                "failure_prediction": 0,
                "failure_probability": None,
                "risk_category": "Low",
                "anomaly": False,
                "anomaly_score": None,
                "anomaly_label": "Normal",
                "rul_available": False,
                "estimated_remaining_cuts": None,
                "rul_unit": "machining cuts",
                "contributing_factors": ["ML failure model artifact not loaded in backend."],
                "recommendation": "Verify model artifacts exist in ml/models/ directory."
            }

        # 1. Run Failure Prediction
        failure_res = self.failure_service.predict(
            type_variant=type_variant,
            air_temp=air_temperature,
            proc_temp=process_temperature,
            rot_speed=rotational_speed,
            torque_val=torque,
            tool_wear_val=tool_wear
        )

        # 2. Run Anomaly Detection
        anomaly_res = {"anomaly": False, "label": "Normal", "anomaly_score": 0.0}
        if self.anomaly_service.is_loaded():
            try:
                anomaly_res = self.anomaly_service.detect(
                    type_variant=type_variant,
                    air_temp=air_temperature,
                    proc_temp=process_temperature,
                    rot_speed=rotational_speed,
                    torque_val=torque,
                    tool_wear_val=tool_wear
                )
            except Exception as e:
                logger.error("Error evaluating anomaly detection: %s", e)

        # 3. RUL Prediction (MachinaGuard RUL Regressor)
        # Validate required RUL features: do not fabricate missing sensor channels
        rul_available = False
        estimated_cuts = None
        rul_unit = "cycles"
        has_rul_features = (
            tool_wear is not None
            and vibration is not None
            and torque is not None
            and process_temperature is not None
            and air_temperature is not None
            and rotational_speed is not None
        )
        if has_rul_features and self.rul_service.is_loaded():
            try:
                rul_data = {
                    "cycle": max(1.0, float(tool_wear) * 0.8) if (float(tool_wear) > 0) else 1.0,
                    "tool_wear_min": float(tool_wear),
                    "vibration_mm_s": float(vibration),
                    "torque_nm": float(torque),
                    "process_temperature_k": float(process_temperature),
                    "air_temperature_k": float(air_temperature),
                    "rotational_speed_rpm": float(rotational_speed),
                    "control_type": type_variant or "A"
                }
                rul_res = self.rul_service.predict(rul_data)
                if isinstance(rul_res, dict):
                    estimated_cuts = float(rul_res.get("estimated_remaining_cycles") or rul_res.get("estimated_remaining_cuts", 0.0))
                else:
                    estimated_cuts = float(rul_res)
                rul_available = True
            except Exception as e:
                logger.debug("RUL estimation in telemetry stream: %s", e)
                rul_available = False
                estimated_cuts = None

        return {
            "prediction_available": True,
            "failure_prediction": failure_res["failure_prediction"],
            "failure_probability": failure_res["failure_probability"],
            "failure_probability_pct": failure_res["failure_probability_pct"],
            "risk_category": failure_res["risk_category"],
            "contributing_factors": failure_res["contributing_factors"],
            "recommendation": failure_res["recommendation"],
            "anomaly": anomaly_res["anomaly"],
            "anomaly_label": anomaly_res["label"],
            "anomaly_score": anomaly_res["anomaly_score"],
            "rul_available": rul_available,
            "estimated_remaining_cuts": estimated_cuts,
            "rul_unit": rul_unit,
            "model_name": "AI4I RandomForestClassifier + IsolationForest + RUL Regressor"
        }

ml_engine = MLPredictionEngine()
