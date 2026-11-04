from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    IncidentResponse, IncidentStatusUpdate,
    MaintenanceCreate, MaintenanceResponse,
    IncidentVerificationResponse
)
from ..crud import (
    get_incidents, get_incident, update_incident_status,
    record_maintenance, get_maintenance_history,
    get_verifications_for_incident
)

router = APIRouter(tags=["Incidents & Maintenance"])

@router.get("/api/incidents", response_model=List[IncidentResponse])
def list_incidents(
    status: Optional[str] = None,
    machine_id: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Retrieve all critical incidents with optional filtering by status or machine_id."""
    return get_incidents(db, status=status, machine_id=machine_id, limit=limit)

@router.get("/api/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident_detail(incident_id: str, db: Session = Depends(get_db)):
    """Retrieve a specific incident by its unique ID."""
    inc = get_incident(db, incident_id)
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found."
        )
    return inc

@router.patch("/api/incidents/{incident_id}/status", response_model=IncidentResponse)
def modify_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update the status of an incident (e.g. Acknowledged, Under Maintenance, Verification Pending)."""
    inc = update_incident_status(
        db,
        incident_id=incident_id,
        new_status=payload.status,
        operator_name=payload.operator_name or "Operator"
    )
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found."
        )
    return inc

@router.post("/api/incidents/{incident_id}/maintenance", response_model=MaintenanceResponse, status_code=status.HTTP_201_CREATED)
def log_incident_maintenance(
    incident_id: str,
    payload: MaintenanceCreate,
    db: Session = Depends(get_db)
):
    """
    Record maintenance action performed for a specific incident.
    Automatically transitions the incident to 'Verification Pending' to trigger automated telemetry verification.
    """
    payload.incident_id = incident_id
    log = record_maintenance(db, payload)
    return log

@router.get("/api/incidents/{incident_id}/verifications", response_model=List[IncidentVerificationResponse])
def get_incident_verifications(incident_id: str, db: Session = Depends(get_db)):
    """Retrieve automated verification history and evidence for an incident."""
    return get_verifications_for_incident(db, incident_id)

@router.post("/api/maintenance", response_model=MaintenanceResponse, status_code=status.HTTP_201_CREATED)
def create_maintenance_log(
    payload: MaintenanceCreate,
    db: Session = Depends(get_db)
):
    """Record a general or incident-specific maintenance action."""
    return record_maintenance(db, payload)

@router.get("/api/maintenance", response_model=List[MaintenanceResponse])
def list_maintenance_logs(
    machine_id: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Retrieve maintenance logs across all machines or for a specific machine."""
    return get_maintenance_history(db, machine_id=machine_id, limit=limit)
