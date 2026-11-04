import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ..database import get_db
from ..schemas import (
    FailurePredictionRequest, FailurePredictionResponse,
    AnomalyDetectionRequest, AnomalyDetectionResponse,
    RULPredictionRequest, RULPredictionResponse,
    MLModelsStatusResponse, ModelStatusDetail,
    MLMetadataResponse, MLEvaluationReportsResponse
)
from ..ml_service import ml_engine
from ..crud import get_machine, utcnow
from ..models import Prediction

router = APIRouter(prefix="/api/ml", tags=["Machine Learning Modules"])

@router.post("/failure/predict", response_model=FailurePredictionResponse)
def predict_machine_failure(payload: FailurePredictionRequest, db: Session = Depends(get_db)):
    """
    Module 1: Machine Failure Prediction Endpoint (AI4I 2020 Random Forest Classifier).
    Calculates failure probability, prediction flag (0=Normal, 1=Failure), and risk category.
    """
    if not ml_engine.failure_service.is_loaded():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failure prediction model artifact is not loaded in backend. Please verify 'predictive_maintenance_rf.joblib' exists."
        )

    # Validate inputs
    air_t = payload.air_temperature
    proc_t = payload.process_temperature
    speed = payload.rotational_speed
    torque = payload.torque
    wear = payload.tool_wear
    tvar = payload.Type or "M"

    # Support raw dictionary extraction if provided
    if payload.extra_features:
        air_t = air_t if air_t is not None else payload.extra_features.get("Air temperature [K]")
        proc_t = proc_t if proc_t is not None else payload.extra_features.get("Process temperature [K]")
        speed = speed if speed is not None else payload.extra_features.get("Rotational speed [rpm]")
        torque = torque if torque is not None else payload.extra_features.get("Torque [Nm]")
        wear = wear if wear is not None else payload.extra_features.get("Tool wear [min]")
        tvar = tvar or payload.extra_features.get("Type", "M")

    missing = []
    if air_t is None: missing.append("air_temperature")
    if proc_t is None: missing.append("process_temperature")
    if speed is None: missing.append("rotational_speed")
    if torque is None: missing.append("torque")
    if wear is None: missing.append("tool_wear")

    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required AI4I physical sensor fields for failure prediction: {', '.join(missing)}"
        )

    try:
        res = ml_engine.failure_service.predict(
            type_variant=tvar,
            air_temp=air_t,
            proc_temp=proc_t,
            rot_speed=speed,
            torque_val=torque,
            tool_wear_val=wear
        )
        
        # Persist prediction if valid registered machine_id
        if payload.machine_id:
            m = get_machine(db, payload.machine_id)
            if m:
                db_pred = Prediction(
                    machine_id=m.machine_id,
                    timestamp=utcnow(),
                    failure_probability=res["failure_probability"],
                    failure_prediction=res["failure_prediction"],
                    risk_category=res["risk_category"],
                    prediction_available=1,
                    model_name="AI4I RandomForestClassifier",
                    recommendation=res["recommendation"]
                )
                db.add(db_pred)
                db.commit()

        return FailurePredictionResponse(
            machine_id=payload.machine_id,
            failure_prediction=res["failure_prediction"],
            failure_probability=res["failure_probability"],
            failure_probability_pct=res.get("failure_probability_pct"),
            risk_category=res["risk_category"],
            model=res["model"],
            version=res["version"],
            timestamp=datetime.now(timezone.utc),
            contributing_factors=res["contributing_factors"],
            recommendation=res["recommendation"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failure: {str(e)}"
        )


@router.post("/anomaly/detect", response_model=AnomalyDetectionResponse)
def detect_operational_anomaly(payload: AnomalyDetectionRequest, db: Session = Depends(get_db)):
    """
    Module 2: Anomaly Detection Endpoint (AI4I 2020 Isolation Forest).
    Unsupervised detection of unusual sensor combinations. Negative score indicates anomaly.
    """
    if not ml_engine.anomaly_service.is_loaded():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Anomaly detection model artifact is not loaded in backend. Please verify 'isolation_forest_ai4i.joblib' exists."
        )

    air_t = payload.air_temperature
    proc_t = payload.process_temperature
    speed = payload.rotational_speed
    torque = payload.torque
    wear = payload.tool_wear
    tvar = payload.Type or "M"

    missing = []
    if air_t is None: missing.append("air_temperature")
    if proc_t is None: missing.append("process_temperature")
    if speed is None: missing.append("rotational_speed")
    if torque is None: missing.append("torque")
    if wear is None: missing.append("tool_wear")

    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required AI4I physical sensor fields for anomaly detection: {', '.join(missing)}"
        )

    try:
        res = ml_engine.anomaly_service.detect(
            type_variant=tvar,
            air_temp=air_t,
            proc_temp=proc_t,
            rot_speed=speed,
            torque_val=torque,
            tool_wear_val=wear
        )

        return AnomalyDetectionResponse(
            machine_id=payload.machine_id,
            anomaly=res["anomaly"],
            label=res["label"],
            anomaly_score=res["anomaly_score"],
            model=res["model"],
            version=res["version"],
            timestamp=datetime.now(timezone.utc),
            note=res["note"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly evaluation failed: {str(e)}"
        )


@router.post("/rul/predict", response_model=RULPredictionResponse)
def predict_remaining_useful_life(payload: RULPredictionRequest, db: Session = Depends(get_db)):
    """
    Module 3: Remaining Useful Life (RUL) Prediction Endpoint.
    Predicts remaining operating life in cycles using Random Forest Regressor.
    """
    if not ml_engine.rul_service.is_loaded():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "RUL prediction model ('rul_model.joblib') is not currently trained or available. "
                "Run 'python ml/training/train_rul.py' to train the model on ml/data/rul_dataset/."
            )
        )

    # Validate incoming features: do not fabricate missing values
    missing = []
    if payload.cycle is None: missing.append("cycle")
    if payload.tool_wear_min is None: missing.append("tool_wear_min")
    if payload.torque_nm is None: missing.append("torque_nm")
    if payload.rotational_speed_rpm is None: missing.append("rotational_speed_rpm")

    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required operational fields for RUL forecasting: {', '.join(missing)}"
        )

    try:
        res = ml_engine.rul_service.predict(payload.model_dump())
        return RULPredictionResponse(
            machine_id=payload.machine_id,
            estimated_remaining_cycles=res["estimated_remaining_cycles"],
            estimated_remaining_cuts=res["estimated_remaining_cuts"],
            unit=res["unit"],
            rul_available=True,
            model=res["model"],
            version=res["version"],
            timestamp=datetime.now(timezone.utc),
            note=res["note"]
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RUL evaluation failed: {str(e)}"
        )


@router.get("/models/status", response_model=MLModelsStatusResponse)
def get_ml_models_status():
    """
    Returns deployment and readiness status for all three ML modules.
    """
    f_loaded = ml_engine.failure_service.is_loaded()
    a_loaded = ml_engine.anomaly_service.is_loaded()
    r_loaded = ml_engine.rul_service.is_loaded()

    failure_detail = ModelStatusDetail(
        name="AI4I 2020 Failure Predictor",
        loaded=f_loaded,
        algorithm="RandomForestClassifier (100 estimators, max_depth=12)",
        dataset="UCI AI4I 2020 Predictive Maintenance Dataset",
        features=[
            "Type", "Air temperature [K]", "Process temperature [K]",
            "Rotational speed [rpm]", "Torque [Nm]", "Tool wear [min]"
        ],
        status="ACTIVE" if f_loaded else "NOT_FOUND",
        notes="Predicts failure probability and categorizes risk into Low, Medium, High, and Critical."
    )

    anomaly_detail = ModelStatusDetail(
        name="AI4I 2020 Anomaly Detector",
        loaded=a_loaded,
        algorithm="IsolationForest (300 estimators, contamination=0.02)",
        dataset="UCI AI4I 2020 Predictive Maintenance Dataset (Normal records)",
        features=[
            "Type", "Air temperature [K]", "Process temperature [K]",
            "Rotational speed [rpm]", "Torque [Nm]", "Tool wear [min]"
        ],
        status="ACTIVE" if a_loaded else "NOT_FOUND",
        notes="Unsupervised detection of unusual sensor combinations. Negative decision score indicates anomaly."
    )

    rul_detail = ModelStatusDetail(
        name="MachinaGuard RUL Regressor",
        loaded=r_loaded,
        algorithm="RandomForestRegressor (100 estimators, max_depth=15, unit-level validation)",
        dataset="Predictive Maintenance Remaining Useful Life Dataset (readings.csv, units.csv, ground_truth.csv)",
        features=[
            "cycle", "tool_wear_min", "vibration_mm_s", "torque_nm",
            "process_temperature_k", "air_temperature_k", "rotational_speed_rpm", "control_type"
        ],
        status="ACTIVE" if r_loaded else "DATASET_REQUIRED",
        notes="Predicts estimated remaining useful life in operational cycles."
    )

    return MLModelsStatusResponse(
        failure_model=failure_detail,
        anomaly_model=anomaly_detail,
        rul_model=rul_detail,
        all_ready=f_loaded and a_loaded and r_loaded
    )


@router.get("/models/metadata", response_model=MLMetadataResponse)
def get_ml_models_metadata():
    """
    Returns verified model metadata JSON for all three models directly from ml/metadata/.
    """
    from ..config import FAILURE_METADATA_PATH, ANOMALY_METADATA_PATH, RUL_METADATA_PATH
    
    def _read_json(path_str):
        if os.path.exists(path_str):
            try:
                with open(path_str, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Error reading metadata %s: %s", path_str, e)
        return None

    return MLMetadataResponse(
        failure_model=_read_json(FAILURE_METADATA_PATH),
        anomaly_model=_read_json(ANOMALY_METADATA_PATH),
        rul_model=_read_json(RUL_METADATA_PATH)
    )


@router.get("/models/evaluations", response_model=MLEvaluationReportsResponse)
def get_ml_models_evaluation_reports():
    """
    Returns independent evaluation reports for all three models directly from ml/evaluation/reports/.
    """
    from ..config import FAILURE_REPORT_PATH, ANOMALY_REPORT_PATH, RUL_REPORT_PATH

    def _read_json(path_str):
        if os.path.exists(path_str):
            try:
                with open(path_str, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Error reading evaluation report %s: %s", path_str, e)
        return None

    return MLEvaluationReportsResponse(
        failure_evaluation=_read_json(FAILURE_REPORT_PATH),
        anomaly_evaluation=_read_json(ANOMALY_REPORT_PATH),
        rul_evaluation=_read_json(RUL_REPORT_PATH)
    )
