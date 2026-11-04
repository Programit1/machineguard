from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    MachineCreate, MachineUpdate, MachineResponse, MachineCardSummary,
    TelemetryResponse
)
from ..crud import (
    get_machine, get_machines, create_machine, update_machine,
    delete_machine, get_machine_card_summary, get_machine_telemetry
)

router = APIRouter(prefix="/api/machines", tags=["Machines"])

@router.get("", response_model=List[MachineCardSummary])
def list_machines(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all registered machines along with their live operational summary and health status."""
    machines = get_machines(db, skip=skip, limit=limit)
    summaries = []
    for m in machines:
        summaries.append(get_machine_card_summary(db, m))
    return summaries

@router.post("", response_model=MachineResponse, status_code=status.HTTP_201_CREATED)
def register_machine(machine: MachineCreate, db: Session = Depends(get_db)):
    """Register a new industrial machine."""
    existing = get_machine(db, machine.machine_id.strip().upper())
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Machine with ID '{machine.machine_id.upper()}' is already registered."
        )
    created = create_machine(db, machine)
    return {
        "id": created.machine_id,
        "machine_id": created.machine_id,
        "name": created.name,
        "machine_type": created.machine_type,
        "location": created.location,
        "description": created.description,
        "type_variant": created.type_variant,
        "status": "ONLINE",
        "created_at": created.created_at,
        "updated_at": created.updated_at
    }

@router.get("/{machine_id}/latest")
def retrieve_machine_latest(machine_id: str, db: Session = Depends(get_db)):
    """Retrieve machine latest sensor telemetry reading and latest ML prediction."""
    machine = get_machine(db, machine_id.strip().upper())
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine with ID '{machine_id}' was not found."
        )
    summary = get_machine_card_summary(db, machine)
    return {
        "machine_id": machine.machine_id,
        "latest_reading": summary.get("latest_reading"),
        "latest_prediction": summary.get("latest_prediction")
    }

@router.get("/{machine_id}/history", response_model=List[TelemetryResponse])
def get_machine_history(machine_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """Retrieve historical sensor readings for charts and tables."""
    machine = get_machine(db, machine_id.strip().upper())
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found."
        )
    return get_machine_telemetry(db, machine.machine_id, limit=limit)

@router.get("/{machine_id}", response_model=MachineCardSummary)
def retrieve_machine(machine_id: str, db: Session = Depends(get_db)):
    """Retrieve an individual machine's details and operational summary."""
    machine = get_machine(db, machine_id.strip().upper())
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine with ID '{machine_id}' was not found."
        )
    return get_machine_card_summary(db, machine)

@router.put("/{machine_id}", response_model=MachineResponse)
def modify_machine(machine_id: str, update_in: MachineUpdate, db: Session = Depends(get_db)):
    """Update machine details (name, type, location, description)."""
    machine = update_machine(db, machine_id.strip().upper(), update_in)
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine with ID '{machine_id}' was not found."
        )
    return {
        "id": machine.machine_id,
        "machine_id": machine.machine_id,
        "name": machine.name,
        "machine_type": machine.machine_type,
        "location": machine.location,
        "description": machine.description,
        "type_variant": machine.type_variant,
        "status": "ONLINE",
        "created_at": machine.created_at,
        "updated_at": machine.updated_at
    }

@router.delete("/{machine_id}", status_code=status.HTTP_200_OK)
def remove_machine(machine_id: str, db: Session = Depends(get_db)):
    """Delete a registered machine and its historical telemetry and prediction records."""
    success = delete_machine(db, machine_id.strip().upper())
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine with ID '{machine_id}' was not found."
        )
    return {"message": f"Machine '{machine_id}' and all associated records deleted successfully."}
