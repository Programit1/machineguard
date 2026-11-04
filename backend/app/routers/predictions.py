import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import PredictionResponse
from ..crud import get_machine_predictions, get_machine

router = APIRouter(tags=["Predictions"])

@router.get("/api/machines/{machine_id}/predictions", response_model=List[PredictionResponse])
def get_predictions_history(machine_id: str, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve historical ML failure predictions, anomaly scores, and risk evaluations for a machine."""
    machine = get_machine(db, machine_id.strip().upper())
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found."
        )
    preds = get_machine_predictions(db, machine.machine_id, limit=limit)
    
    results = []
    for p in preds:
        try:
            factors = json.loads(p.contributing_factors) if p.contributing_factors else []
        except Exception:
            factors = []
        is_avail = bool(getattr(p, "prediction_available", 1))
        f_prob = p.failure_probability if (is_avail and p.failure_probability is not None and p.failure_probability >= 0) else None
        
        results.append(PredictionResponse(
            id=p.id,
            telemetry_id=getattr(p, "telemetry_id", None),
            machine_id=p.machine_id,
            timestamp=p.timestamp,
            failure_probability=f_prob,
            raw_probability=getattr(p, "raw_probability", None),
            risk_category=p.risk_category or "Low",
            prediction_available=is_avail,
            failure_prediction=getattr(p, "failure_prediction", 0),
            anomaly=bool(getattr(p, "anomaly_detected", 0)),
            anomaly_detected=bool(getattr(p, "anomaly_detected", 0)),
            anomaly_score=getattr(p, "anomaly_score", None),
            anomaly_label=getattr(p, "anomaly_label", "Normal"),
            estimated_remaining_cuts=getattr(p, "estimated_remaining_cuts", None),
            rul_unit=getattr(p, "rul_unit", "cycles") or "cycles",
            rul_available=bool(getattr(p, "rul_available", 0)),
            machine_health_status=getattr(p, "machine_health_status", "Healthy") or "Healthy",
            model_disagreement=bool(getattr(p, "model_disagreement", 0)),
            disagreement_reason=getattr(p, "disagreement_reason", "") or "",
            model_name=getattr(p, "model_name", "AI4I RandomForestClassifier"),
            contributing_factors=factors,
            recommendation=p.recommendation or ""
        ))
    return results
