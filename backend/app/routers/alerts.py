import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import AlertResponse, AlertStatusUpdate
from ..crud import get_alerts, update_alert_status, get_notifications

router = APIRouter(tags=["Alerts & Notifications"])

def _format_alert(a) -> AlertResponse:
    try:
        vals = json.loads(a.sensor_values) if a.sensor_values else {}
    except Exception:
        vals = {}

    try:
        trig = json.loads(a.triggering_values) if getattr(a, "triggering_values", None) else {}
    except Exception:
        trig = {}
    
    # Ensure uppercase status for consistency with verification scripts
    st = (a.status or "ACTIVE").upper()
    sev = getattr(a, "severity", "HIGH") or "HIGH"
    al_type = getattr(a, "alert_type", "failure_risk") or "failure_risk"
    al_src = getattr(a, "alert_source", "ml_failure") or "ml_failure"
    tit = getattr(a, "title", "") or f"{sev} Alert: {a.machine_name}"

    return AlertResponse(
        id=a.id,
        telemetry_id=getattr(a, "telemetry_id", None),
        prediction_id=getattr(a, "prediction_id", None),
        machine_id=a.machine_id,
        machine_name=a.machine_name,
        timestamp=a.timestamp,
        risk_level=a.risk_level,
        severity=sev,
        alert_type=al_type,
        alert_source=al_src,
        title=tit,
        reason=a.reason,
        threshold_or_rule=getattr(a, "threshold_or_rule", "") or "",
        sensor_values=vals,
        triggering_values=trig,
        recommendation=a.recommendation or "",
        status=st,
        resolution_note=getattr(a, "resolution_note", "") or "",
        acknowledged_at=a.acknowledged_at,
        resolved_at=a.resolved_at
    )

@router.get("/api/alerts", response_model=List[AlertResponse])
def list_alerts(
    status: Optional[str] = None,
    machine_id: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Retrieve operational failure alerts with optional status/machine filtering."""
    alerts = get_alerts(db, status=status, machine_id=machine_id, limit=limit)
    return [_format_alert(a) for a in alerts]

@router.patch("/api/alerts/{alert_id}/status", response_model=AlertResponse)
def change_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db)
):
    """Acknowledge or resolve an active alert."""
    alert = update_alert_status(db, alert_id=alert_id, new_status=payload.status)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found."
        )
    return _format_alert(alert)

# --- Notification Aliases for System Test Scripts ---
@router.get("/api/notifications", response_model=List[AlertResponse])
def list_notifications(limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve all notifications and alert dispatches."""
    notifs = get_notifications(db, limit=limit)
    return [_format_alert(n) for n in notifs]

@router.post("/api/notifications/{alert_id}/acknowledge")
def acknowledge_notification(alert_id: int, db: Session = Depends(get_db)):
    """Acknowledge a notification."""
    alert = update_alert_status(db, alert_id=alert_id, new_status="ACKNOWLEDGED")
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification #{alert_id} not found."
        )
    return {"status": "success", "message": f"Notification #{alert_id} acknowledged."}

@router.post("/api/notifications/{alert_id}/resolve")
def resolve_notification(alert_id: int, db: Session = Depends(get_db)):
    """Resolve a notification."""
    alert = update_alert_status(db, alert_id=alert_id, new_status="RESOLVED")
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification #{alert_id} not found."
        )
    return {"status": "success", "message": f"Notification #{alert_id} resolved."}
