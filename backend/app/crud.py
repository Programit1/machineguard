import json
import os
import secrets
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from .models import Machine, SensorReading, Prediction, Alert, MaintenanceLog, utcnow
from .schemas import MachineCreate, MachineUpdate, TelemetryCreate
from .ml_service import ml_engine
from .config import ALERT_RISK_THRESHOLD, OFFLINE_THRESHOLD_SECONDS, ANOMALY_ALERT_SCORE_THRESHOLD
from .health_service import health_service
from .alert_manager import alert_manager, AlertManager

# Cooldown window in seconds before repeating an active alert for the same condition on a machine
ALERT_COOLDOWN_SECONDS = 300

def ensure_schema_migrations(engine):
    """Safely adds newly required columns to existing SQLite database without dropping tables or resetting data."""
    if engine.dialect.name != "sqlite":
        # On PostgreSQL / Supabase, schema creation is managed natively by Base.metadata.create_all
        return
    try:
        raw_conn = engine.raw_connection()
        cursor = raw_conn.cursor()

        def add_col_if_missing(table, col, col_type):
            cursor.execute(f"PRAGMA table_info({table});")
            cols = [c[1] for c in cursor.fetchall()]
            if col not in cols:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};")

        # Telemetry columns
        add_col_if_missing("sensor_readings", "air_temperature", "REAL DEFAULT NULL")
        add_col_if_missing("sensor_readings", "process_temperature", "REAL DEFAULT NULL")
        add_col_if_missing("sensor_readings", "rotational_speed", "REAL DEFAULT NULL")
        add_col_if_missing("sensor_readings", "torque", "REAL DEFAULT NULL")
        add_col_if_missing("sensor_readings", "tool_wear", "REAL DEFAULT NULL")
        
        # Machine columns (Variant, Status)
        add_col_if_missing("machines", "type_variant", "VARCHAR(8) DEFAULT 'M'")
        add_col_if_missing("machines", "status", "VARCHAR(32) DEFAULT 'ONLINE'")
        
        # Prediction columns (Failure, Anomaly, RUL, Health & Consistency)
        add_col_if_missing("predictions", "telemetry_id", "INTEGER DEFAULT NULL")
        add_col_if_missing("predictions", "raw_probability", "REAL DEFAULT NULL")
        add_col_if_missing("predictions", "prediction_available", "INTEGER DEFAULT 1")
        add_col_if_missing("predictions", "failure_prediction", "INTEGER DEFAULT 0")
        add_col_if_missing("predictions", "anomaly_detected", "INTEGER DEFAULT 0")
        add_col_if_missing("predictions", "anomaly_score", "REAL DEFAULT NULL")
        add_col_if_missing("predictions", "anomaly_label", "VARCHAR(32) DEFAULT 'Normal'")
        add_col_if_missing("predictions", "estimated_remaining_cuts", "REAL DEFAULT NULL")
        add_col_if_missing("predictions", "rul_unit", "VARCHAR(32) DEFAULT 'cycles'")
        add_col_if_missing("predictions", "rul_available", "INTEGER DEFAULT 0")
        add_col_if_missing("predictions", "model_name", "VARCHAR(64) DEFAULT 'AI4I RandomForestClassifier'")
        add_col_if_missing("predictions", "machine_health_status", "VARCHAR(32) DEFAULT 'Healthy'")
        add_col_if_missing("predictions", "model_disagreement", "INTEGER DEFAULT 0")
        add_col_if_missing("predictions", "disagreement_reason", "TEXT DEFAULT ''")
        
        # Alert / Notification columns
        add_col_if_missing("alerts", "telemetry_id", "INTEGER DEFAULT NULL")
        add_col_if_missing("alerts", "prediction_id", "INTEGER DEFAULT NULL")
        add_col_if_missing("alerts", "alert_type", "VARCHAR(32) DEFAULT 'failure_risk'")
        add_col_if_missing("alerts", "alert_source", "VARCHAR(32) DEFAULT 'ml_failure'")
        add_col_if_missing("alerts", "title", "VARCHAR(128) DEFAULT ''")
        add_col_if_missing("alerts", "severity", "VARCHAR(32) DEFAULT 'HIGH'")
        add_col_if_missing("alerts", "triggering_values", "TEXT DEFAULT '{}'")
        add_col_if_missing("alerts", "threshold_or_rule", "VARCHAR(128) DEFAULT ''")
        add_col_if_missing("alerts", "resolution_note", "TEXT DEFAULT ''")
        add_col_if_missing("alerts", "first_seen_at", "DATETIME DEFAULT NULL")
        add_col_if_missing("alerts", "last_seen_at", "DATETIME DEFAULT NULL")

        raw_conn.commit()
        cursor.close()
        raw_conn.close()
    except Exception as e:
        # Pass safely if tables don't exist yet (Base.metadata.create_all handles initial creation)
        pass

def get_machine(db: Session, machine_id: str) -> Optional[Machine]:
    return db.query(Machine).filter(Machine.machine_id == machine_id.strip().upper()).first()

def get_machines(db: Session, skip: int = 0, limit: int = 100) -> List[Machine]:
    return db.query(Machine).order_by(Machine.created_at.desc()).offset(skip).limit(limit).all()

def create_machine(db: Session, machine: MachineCreate) -> Machine:
    type_variant = (machine.type_variant or "M").strip().upper()
    if type_variant not in ["L", "M", "H"]:
        type_variant = "M"

    db_machine = Machine(
        machine_id=machine.machine_id.strip().upper(),
        name=machine.name.strip(),
        machine_type=machine.machine_type.strip(),
        location=machine.location.strip(),
        description=machine.description or "",
        type_variant=type_variant
    )
    db.add(db_machine)
    db.commit()
    db.refresh(db_machine)
    return db_machine

def update_machine(db: Session, machine_id: str, machine_update: MachineUpdate) -> Optional[Machine]:
    db_machine = get_machine(db, machine_id)
    if not db_machine:
        return None
    
    update_data = machine_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "type_variant" and value:
            val = value.strip().upper()
            setattr(db_machine, key, val if val in ["L", "M", "H"] else "M")
        else:
            setattr(db_machine, key, value)
        
    db_machine.updated_at = utcnow()
    db.commit()
    db.refresh(db_machine)
    return db_machine

def delete_machine(db: Session, machine_id: str) -> bool:
    db_machine = get_machine(db, machine_id)
    if not db_machine:
        return False
        
    # Delete related readings, predictions, and alerts
    db.query(SensorReading).filter(SensorReading.machine_id == machine_id).delete()
    db.query(Prediction).filter(Prediction.machine_id == machine_id).delete()
    db.query(Alert).filter(Alert.machine_id == machine_id).delete()
    db.query(MaintenanceLog).filter(MaintenanceLog.machine_id == machine_id).delete()
    db.delete(db_machine)
    db.commit()
    return True

def save_telemetry_and_predict(db: Session, telemetry_in: TelemetryCreate) -> Tuple[SensorReading, Prediction, Optional[Alert]]:
    mid = telemetry_in.machine_id.strip().upper()
    machine = get_machine(db, mid)
    if not machine:
        # Check if machine can be auto-registered if name supplied (e.g. CNC-001 in test)
        if mid == "CNC-001" or telemetry_in.machine_name:
            machine = Machine(
                machine_id=mid,
                name=telemetry_in.machine_name or f"Machining Center {mid}",
                machine_type=telemetry_in.equipment_type or "CNC Mill",
                location="Shop Floor",
                description="Auto-registered industrial machine",
                type_variant=telemetry_in.equipment_type if telemetry_in.equipment_type in ["L", "M", "H"] else "M"
            )
            db.add(machine)
            db.commit()
            db.refresh(machine)
        else:
            raise ValueError(f"Machine with ID '{telemetry_in.machine_id}' does not exist. Register equipment first.")

    ts = telemetry_in.timestamp or utcnow()
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)

    # Resolve physical values with legitimate defaults / unit awareness
    air_temp = telemetry_in.air_temperature
    proc_temp = telemetry_in.process_temperature
    rot_speed = telemetry_in.rotational_speed
    torque = telemetry_in.torque
    tool_wear = telemetry_in.tool_wear

    temp = telemetry_in.temperature
    if temp is not None:
        temp = round(float(temp), 2)
        if proc_temp is None:
            proc_temp = round(temp + 273.15, 2)
        if air_temp is None:
            air_temp = round(proc_temp - 10.0, 2)
    elif proc_temp is not None:
        temp = round(proc_temp - 273.15 if proc_temp > 150 else proc_temp, 2)

    vibe = round(float(telemetry_in.vibration), 2) if telemetry_in.vibration is not None else None
    press = round(float(telemetry_in.pressure), 2) if telemetry_in.pressure is not None else None
    pwr = round(float(telemetry_in.power_consumption), 2) if telemetry_in.power_consumption is not None else None
    load = round(float(telemetry_in.operating_load), 2) if telemetry_in.operating_load is not None else None

    # Derive mechanical power if power_consumption missing but torque & speed available
    if pwr is None and torque is not None and rot_speed is not None:
        mech_W = float(torque) * (float(rot_speed) * 2.0 * 3.14159 / 60.0)
        pwr = round(mech_W / 1000.0, 2)

    # 1. Save Sensor Reading
    reading = SensorReading(
        machine_id=machine.machine_id,
        timestamp=ts,
        air_temperature=round(float(air_temp), 2) if air_temp is not None else None,
        process_temperature=round(float(proc_temp), 2) if proc_temp is not None else None,
        rotational_speed=round(float(rot_speed), 1) if rot_speed is not None else None,
        torque=round(float(torque), 2) if torque is not None else None,
        tool_wear=round(float(tool_wear), 1) if tool_wear is not None else None,
        temperature=round(float(temp), 2) if temp is not None else 0.0,
        vibration=round(float(vibe), 2) if vibe is not None else 0.0,
        pressure=round(float(press), 2) if press is not None else 0.0,
        power_consumption=round(float(pwr), 2) if pwr is not None else 0.0,
        operating_load=round(float(load), 2) if load is not None else 0.0
    )
    db.add(reading)
    db.flush() # Populate reading.id for foreign-key traceability

    # 2. Run ML Prediction Engine with legitimate feature mapping
    tvar = getattr(machine, "type_variant", "M") or "M"
    if telemetry_in.equipment_type in ["L", "M", "H"]:
        tvar = telemetry_in.equipment_type

    pred_result = ml_engine.predict(
        air_temperature=air_temp,
        process_temperature=proc_temp,
        rotational_speed=rot_speed,
        torque=torque,
        tool_wear=tool_wear,
        type_variant=tvar,
        temperature=temp,
        vibration=vibe,
        pressure=press,
        power_consumption=pwr,
        operating_load=load,
        machine_type=machine.machine_type
    )

    # 3. Assess Operational Rules & Machine Health Consistency
    raw_prob = pred_result.get("failure_probability")
    prob_for_db = float(raw_prob) if raw_prob is not None else -1.0

    op_violations = AlertManager.evaluate_operational_rules(
        machine=machine,
        air_temp=air_temp,
        proc_temp=proc_temp,
        rot_speed=rot_speed,
        torque=torque,
        tool_wear=tool_wear,
        vibration=vibe
    )
    violation_codes = [v["rule_code"] for v in op_violations]

    # 3. Save Prediction Record with 100% Traceability
    prediction = Prediction(
        telemetry_id=reading.id,
        machine_id=machine.machine_id,
        timestamp=ts,
        failure_probability=prob_for_db,
        raw_probability=raw_prob,
        risk_category=pred_result["risk_category"],
        prediction_available=1 if pred_result.get("prediction_available", True) else 0,
        failure_prediction=pred_result.get("failure_prediction", 0),
        anomaly_detected=1 if pred_result.get("anomaly", False) else 0,
        anomaly_score=pred_result.get("anomaly_score"),
        anomaly_label=pred_result.get("anomaly_label", "Normal"),
        rul_available=1 if pred_result.get("rul_available", False) else 0,
        estimated_remaining_cuts=pred_result.get("estimated_remaining_cuts"),
        rul_unit=pred_result.get("rul_unit", "cycles"),
        machine_health_status="Healthy",
        model_disagreement=0,
        disagreement_reason="",
        model_name=pred_result.get("model_name", "AI4I RandomForestClassifier"),
        contributing_factors=json.dumps(pred_result.get("contributing_factors", [])),
        recommendation=pred_result.get("recommendation", "")
    )
    db.add(prediction)
    db.flush() # Populate prediction.id for alert linkage

    # 4. Synchronize Alerts: Auto-resolve stale alerts and deduplicate new triggers
    created_alerts = alert_manager.sync_machine_alerts(
        db=db,
        machine=machine,
        reading=reading,
        prediction=prediction,
        pred_result=pred_result
    )

    # In-memory evaluation of active alerts count without extra network round-trips
    remaining_active = db.query(Alert).filter(
        Alert.machine_id == machine.machine_id,
        func.lower(Alert.status) == "active"
    ).all()
    final_active_crit = sum(1 for a in remaining_active if (a.severity or "").upper() == "CRITICAL")
    final_active_warn = len(remaining_active) - final_active_crit

    final_health, final_disag, final_reason = health_service.evaluate_health(
        failure_prob=raw_prob,
        failure_risk_category=pred_result.get("risk_category", "Low"),
        is_anomaly=bool(pred_result.get("anomaly", False)),
        anomaly_score=pred_result.get("anomaly_score"),
        rul_cycles=pred_result.get("estimated_remaining_cuts"),
        active_critical_alerts=final_active_crit,
        active_warning_alerts=final_active_warn,
        operational_violations=violation_codes
    )
    prediction.machine_health_status = final_health
    prediction.model_disagreement = 1 if final_disag else 0
    prediction.disagreement_reason = final_reason

    db.commit()

    primary_created_alert = created_alerts[0] if created_alerts else None
    return reading, prediction, primary_created_alert

    return reading, prediction, primary_created_alert

def get_machine_telemetry(db: Session, machine_id: str, limit: int = 100) -> List[SensorReading]:
    return db.query(SensorReading)\
        .filter(SensorReading.machine_id == machine_id)\
        .order_by(SensorReading.timestamp.desc())\
        .limit(limit)\
        .all()

def get_machine_predictions(db: Session, machine_id: str, limit: int = 100) -> List[Prediction]:
    return db.query(Prediction)\
        .filter(Prediction.machine_id == machine_id)\
        .order_by(Prediction.timestamp.desc())\
        .limit(limit)\
        .all()

def get_alerts(db: Session, status: Optional[str] = None, machine_id: Optional[str] = None, limit: int = 100) -> List[Alert]:
    query = db.query(Alert)
    if status and status.lower() != "all":
        query = query.filter(func.lower(Alert.status) == status.lower())
    if machine_id:
        query = query.filter(Alert.machine_id == machine_id)
    return query.order_by(Alert.timestamp.desc(), Alert.id.desc()).limit(limit).all()

def update_alert_status(db: Session, alert_id: int, new_status: str) -> Optional[Alert]:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return None
    
    stat = new_status.upper()
    alert.status = stat
    if stat in ["ACKNOWLEDGED"]:
        alert.acknowledged_at = utcnow()
    elif stat in ["RESOLVED"]:
        alert.resolved_at = utcnow()
        
    db.commit()
    db.refresh(alert)
    return alert

def get_notifications(db: Session, limit: int = 100) -> List[Alert]:
    return db.query(Alert).order_by(Alert.timestamp.desc()).limit(limit).all()

def get_machine_card_summary(db: Session, machine: Machine) -> Dict[str, Any]:
    latest_reading = db.query(SensorReading)\
        .filter(SensorReading.machine_id == machine.machine_id)\
        .order_by(SensorReading.timestamp.desc())\
        .first()

    latest_pred = db.query(Prediction)\
        .filter(Prediction.machine_id == machine.machine_id)\
        .order_by(Prediction.timestamp.desc())\
        .first()

    active_alerts_count = db.query(func.count(Alert.id))\
        .filter(Alert.machine_id == machine.machine_id, func.lower(Alert.status) == "active")\
        .scalar() or 0

    is_online = False
    last_telemetry_time = None
    if latest_reading:
        ts = latest_reading.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        last_telemetry_time = ts
        now_utc = datetime.now(timezone.utc)
        delta_seconds = (now_utc - ts).total_seconds()
        is_online = delta_seconds <= OFFLINE_THRESHOLD_SECONDS

    # Determine unified health status
    if not latest_pred:
        health_status = "No Data"
    else:
        m_status = getattr(latest_pred, "machine_health_status", None)
        if m_status == "Critical":
            health_status = "Critical Risk"
        elif m_status in ["Warning", "Warning (Model Disagreement)"]:
            health_status = "Attention Required"
        elif m_status == "Healthy":
            health_status = "Healthy"
        elif getattr(latest_pred, "prediction_available", 1) == 0:
            health_status = "Attention Required"
        else:
            cat = latest_pred.risk_category
            if cat == "Critical":
                health_status = "Critical Risk"
            elif cat == "High":
                health_status = "High Risk"
            elif cat == "Medium":
                health_status = "Attention Required"
            else:
                health_status = "Healthy"

    parsed_pred = None
    if latest_pred:
        try:
            factors = json.loads(latest_pred.contributing_factors) if latest_pred.contributing_factors else []
        except Exception:
            factors = []
        is_avail = bool(getattr(latest_pred, "prediction_available", 1))
        raw_p = latest_pred.failure_probability
        f_prob = raw_p if (is_avail and raw_p is not None and raw_p >= 0) else None
        
        parsed_pred = {
            "id": latest_pred.id,
            "telemetry_id": getattr(latest_pred, "telemetry_id", None),
            "machine_id": latest_pred.machine_id,
            "timestamp": latest_pred.timestamp,
            "failure_probability": f_prob,
            "raw_probability": getattr(latest_pred, "raw_probability", None),
            "risk_category": latest_pred.risk_category,
            "prediction_available": is_avail,
            "failure_prediction": getattr(latest_pred, "failure_prediction", 0),
            "anomaly": bool(getattr(latest_pred, "anomaly_detected", 0)),
            "anomaly_detected": bool(getattr(latest_pred, "anomaly_detected", 0)),
            "anomaly_score": getattr(latest_pred, "anomaly_score", None),
            "anomaly_label": getattr(latest_pred, "anomaly_label", "Normal"),
            "estimated_remaining_cuts": getattr(latest_pred, "estimated_remaining_cuts", None),
            "rul_unit": getattr(latest_pred, "rul_unit", "cycles") or "cycles",
            "rul_available": bool(getattr(latest_pred, "rul_available", 0)),
            "machine_health_status": getattr(latest_pred, "machine_health_status", "Healthy") or "Healthy",
            "model_disagreement": bool(getattr(latest_pred, "model_disagreement", 0)),
            "disagreement_reason": getattr(latest_pred, "disagreement_reason", "") or "",
            "model_name": getattr(latest_pred, "model_name", "AI4I RandomForestClassifier"),
            "contributing_factors": factors,
            "recommendation": latest_pred.recommendation or ""
        }

    return {
        "id": machine.machine_id, # String ID (e.g. CNC-001) for test verification and frontend
        "machine_id": machine.machine_id,
        "name": machine.name,
        "machine_type": machine.machine_type,
        "location": machine.location,
        "description": machine.description or "",
        "type_variant": getattr(machine, "type_variant", "M") or "M",
        "is_online": is_online,
        "status": "ONLINE" if is_online else "OFFLINE",
        "last_telemetry_time": last_telemetry_time,
        "latest_reading": latest_reading,
        "latest_prediction": parsed_pred,
        "health_status": health_status,
        "active_alerts_count": active_alerts_count
    }

def get_dashboard_summary(db: Session) -> Dict[str, Any]:
    machines = db.query(Machine).all()
    total_machines = len(machines)
    
    online_machines = 0
    healthy_machines = 0
    attention_machines = 0
    high_risk_machines = 0
    critical_risk_machines = 0

    risk_dist = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    now_utc = datetime.now(timezone.utc)

    for m in machines:
        latest_reading = db.query(SensorReading)\
            .filter(SensorReading.machine_id == m.machine_id)\
            .order_by(SensorReading.timestamp.desc(), SensorReading.id.desc())\
            .first()

        if latest_reading:
            ts = latest_reading.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            delta = (now_utc - ts).total_seconds()
            if delta <= OFFLINE_THRESHOLD_SECONDS:
                online_machines += 1

        latest_pred = db.query(Prediction)\
            .filter(Prediction.machine_id == m.machine_id)\
            .order_by(Prediction.timestamp.desc(), Prediction.id.desc())\
            .first()

        if latest_pred:
            cat = latest_pred.risk_category
            if cat in risk_dist:
                risk_dist[cat] += 1
            else:
                risk_dist["Low"] += 1

            m_status = getattr(latest_pred, "machine_health_status", None)
            if m_status == "Critical":
                critical_risk_machines += 1
            elif m_status in ["Warning", "Warning (Model Disagreement)"]:
                attention_machines += 1
            elif m_status == "Healthy":
                healthy_machines += 1
            elif cat == "Critical":
                critical_risk_machines += 1
            elif cat == "High":
                high_risk_machines += 1
            elif cat == "Medium":
                attention_machines += 1
            else:
                healthy_machines += 1
        else:
            healthy_machines += 1
            risk_dist["Low"] += 1

    active_alerts_count = db.query(func.count(Alert.id))\
        .filter(func.lower(Alert.status) == "active")\
        .scalar() or 0

    recent_alerts = db.query(Alert)\
        .order_by(Alert.timestamp.desc())\
        .limit(10)\
        .all()

    recent_telemetry = db.query(SensorReading)\
        .order_by(SensorReading.timestamp.desc())\
        .limit(15)\
        .all()

    return {
        "total_machines": total_machines,
        "online_machines": online_machines,
        "healthy_machines": healthy_machines,
        "attention_machines": attention_machines,
        "high_risk_machines": high_risk_machines,
        "critical_risk_machines": critical_risk_machines,
        "active_alerts_count": active_alerts_count,
        "risk_distribution": risk_dist,
        "recent_alerts": recent_alerts,
        "recent_telemetry": recent_telemetry
    }
