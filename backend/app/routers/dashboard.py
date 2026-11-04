import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import DashboardSummaryResponse, AlertResponse, TelemetryResponse
from ..crud import get_dashboard_summary

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_overview(db: Session = Depends(get_db)):
    """Retrieve aggregate statistics, risk distribution, and recent activity for the central dashboard."""
    raw = get_dashboard_summary(db)
    
    formatted_alerts = []
    for a in raw["recent_alerts"]:
        try:
            s_vals = json.loads(a.sensor_values) if a.sensor_values else {}
        except Exception:
            s_vals = {}
        formatted_alerts.append(AlertResponse(
            id=a.id,
            machine_id=a.machine_id,
            machine_name=a.machine_name,
            timestamp=a.timestamp,
            risk_level=a.risk_level,
            reason=a.reason,
            sensor_values=s_vals,
            recommendation=a.recommendation or "",
            status=a.status,
            acknowledged_at=a.acknowledged_at,
            resolved_at=a.resolved_at
        ))

    formatted_telemetry = [
        TelemetryResponse.model_validate(r) for r in raw["recent_telemetry"]
    ]

    return DashboardSummaryResponse(
        total_machines=raw["total_machines"],
        online_machines=raw["online_machines"],
        healthy_machines=raw["healthy_machines"],
        attention_machines=raw["attention_machines"],
        high_risk_machines=raw["high_risk_machines"],
        critical_risk_machines=raw["critical_risk_machines"],
        active_alerts_count=raw["active_alerts_count"],
        risk_distribution=raw["risk_distribution"],
        recent_alerts=formatted_alerts,
        recent_telemetry=formatted_telemetry
    )
