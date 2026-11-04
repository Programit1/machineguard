from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Machine
from ..schemas import TelemetryCreate, TelemetryResponse
from ..crud import save_telemetry_and_predict, get_machine_telemetry, get_machine

router = APIRouter(tags=["Telemetry"])

@router.post("/api/telemetry", status_code=status.HTTP_201_CREATED)
def ingest_telemetry(payload: TelemetryCreate, db: Session = Depends(get_db)):
    """
    Ingest real-time sensor telemetry from external generator.
    Validates machine existence by machine_id, persists sensor readings,
    and executes ML prediction, anomaly detection, and RUL forecasting.
    """
    # 1. Look up machine
    machine_id = payload.machine_id.strip().upper()
    machine = get_machine(db, machine_id)
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' is not registered."
        )

    try:
        reading, prediction, alert = save_telemetry_and_predict(db, payload)
        
        is_avail = bool(getattr(prediction, "prediction_available", 1))
        f_prob = prediction.failure_probability if (is_avail and prediction.failure_probability is not None and prediction.failure_probability >= 0) else None

        return {
            "status": "success",
            "message": "Telemetry received and evaluated by ML pipeline.",
            "reading": {
                "id": reading.id,
                "machine_id": reading.machine_id,
                "timestamp": reading.timestamp.isoformat(),
                "air_temperature": reading.air_temperature,
                "process_temperature": reading.process_temperature,
                "rotational_speed": reading.rotational_speed,
                "torque": reading.torque,
                "tool_wear": reading.tool_wear,
                "temperature": reading.temperature,
                "vibration": reading.vibration,
                "pressure": reading.pressure,
                "power_consumption": reading.power_consumption,
                "operating_load": reading.operating_load
            },
            "prediction": {
                "id": prediction.id,
                "telemetry_id": getattr(prediction, "telemetry_id", None),
                "failure_probability": f_prob,
                "raw_probability": getattr(prediction, "raw_probability", None),
                "risk_category": prediction.risk_category or "Low",
                "machine_health_status": getattr(prediction, "machine_health_status", "Healthy"),
                "model_disagreement": bool(getattr(prediction, "model_disagreement", 0)),
                "disagreement_reason": getattr(prediction, "disagreement_reason", ""),
                "prediction_available": is_avail,
                "failure_prediction": getattr(prediction, "failure_prediction", 0),
                "anomaly": bool(getattr(prediction, "anomaly_detected", 0)),
                "anomaly_score": getattr(prediction, "anomaly_score", None),
                "anomaly_label": getattr(prediction, "anomaly_label", "Normal"),
                "rul_available": bool(getattr(prediction, "rul_available", 0)),
                "estimated_remaining_cuts": getattr(prediction, "estimated_remaining_cuts", None),
                "rul_unit": getattr(prediction, "rul_unit", "cycles"),
                "recommendation": prediction.recommendation or ""
            },
            "alert_generated": alert is not None
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing telemetry: {str(e)}"
        )

@router.get("/api/machines/{machine_id}/telemetry", response_model=List[TelemetryResponse])
def get_telemetry_history(machine_id: str, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve historical sensor readings for a specific machine."""
    machine = get_machine(db, machine_id.strip().upper())
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found."
        )
    return get_machine_telemetry(db, machine.machine_id, limit=limit)
