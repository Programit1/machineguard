"""
MachinaGuard - Incident & Maintenance Verification Engine
Manages the lifecycle of critical incidents, maintenance logging,
and evidence-based automated recovery verification across consecutive telemetry cycles.
"""

import json
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import Machine, SensorReading, Prediction, Alert, Incident, MaintenanceLog, IncidentVerification
from .config import ALERT_RISK_THRESHOLD, ANOMALY_ALERT_SCORE_THRESHOLD


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class IncidentManager:
    """
    Coordinates Critical Incidents and Automatic Maintenance Verification:
    1. Detects critical machine states and creates deduplicated incidents.
    2. Evaluates verification criteria on fresh telemetry for incidents in 'Verification Pending'.
    3. Requires 3 consecutive healthy telemetry cycles before declaring an incident 'Resolved'.
    4. Marks incidents as 'Not Fixed' if abnormal conditions persist or recur during verification.
    """

    REQUIRED_HEALTHY_CYCLES = 3

    @staticmethod
    def generate_incident_id(machine_id: str, condition_type: str, timestamp: datetime) -> str:
        ts_str = timestamp.strftime("%Y%m%d%H%M%S")
        clean_cond = condition_type.replace(" ", "_").upper()[:8]
        return f"INC-{machine_id}-{clean_cond}-{ts_str[-6:]}"

    @staticmethod
    def sync_incidents_and_verification(
        db: Session,
        machine: Machine,
        reading: SensorReading,
        prediction: Prediction,
        pred_result: Dict[str, Any],
        alerts_created: List[Alert],
        violations: List[Dict[str, Any]]
    ) -> Tuple[List[Incident], List[IncidentVerification]]:
        """
        Main synchronization method called during telemetry ingestion.
        Returns any newly created incidents and updated verifications.
        """
        now_ts = reading.timestamp or utcnow()
        created_incidents: List[Incident] = []
        updated_verifications: List[IncidentVerification] = []

        # ---------------------------------------------------------------------
        # 1. PROCESS VERIFICATION PENDING INCIDENTS FOR THIS MACHINE
        # ---------------------------------------------------------------------
        pending_incidents = db.query(Incident).filter(
            Incident.machine_id == machine.machine_id,
            Incident.status == "Verification Pending"
        ).all()

        prob = pred_result.get("failure_probability")
        prob_pct = (prob * 100.0) if (prob is not None and prob <= 1.0) else (prob or 0.0)
        risk = pred_result.get("risk_category", "Low")
        is_anomaly = bool(pred_result.get("anomaly", False))
        active_violation_codes = {v["rule_code"] for v in violations}

        for inc in pending_incidents:
            cond = inc.condition_type

            # Check if this specific condition or any critical failure is currently active
            is_condition_active = False
            retrigger_reason = ""

            if cond in ["PWF", "OSF", "HDF", "TWF", "VIBRATION"]:
                if cond in active_violation_codes:
                    is_condition_active = True
                    matching_v = next((v for v in violations if v["rule_code"] == cond), None)
                    retrigger_reason = matching_v["reason"] if matching_v else f"{cond} rule threshold violated"
            elif cond == "ML_FAILURE":
                if prob_pct >= ALERT_RISK_THRESHOLD or risk in ["High", "Critical"]:
                    is_condition_active = True
                    retrigger_reason = f"Failure risk remains elevated at {prob_pct:.1f}% ({risk})"
            elif cond == "ANOMALY":
                if is_anomaly:
                    is_condition_active = True
                    retrigger_reason = f"Operational anomaly persists with score {pred_result.get('anomaly_score', 0):.3f}"
            else:
                # Catch-all: If any critical operational violation or high failure risk occurs
                if active_violation_codes or (prob_pct >= ALERT_RISK_THRESHOLD):
                    is_condition_active = True
                    retrigger_reason = f"Severe operational parameters observed: {active_violation_codes or risk}"

            # Retrieve or create active verification session
            verif = db.query(IncidentVerification).filter(
                IncidentVerification.incident_id == inc.incident_id
            ).order_by(IncidentVerification.id.desc()).first()

            if not verif or verif.status in ["RESOLVED", "NOT FIXED"]:
                verif = IncidentVerification(
                    incident_id=inc.incident_id,
                    machine_id=machine.machine_id,
                    status="IN_PROGRESS",
                    consecutive_healthy_count=0,
                    required_healthy_count=IncidentManager.REQUIRED_HEALTHY_CYCLES,
                    verification_timestamp=now_ts,
                    evidence="Verification initiated following maintenance. Awaiting consecutive nominal telemetry readings.",
                    supporting_telemetry_ids="[]",
                    evaluated_predictions="{}"
                )
                db.add(verif)
                db.flush()

            # Parse supporting telemetry IDs
            try:
                sup_ids = json.loads(verif.supporting_telemetry_ids or "[]")
            except Exception:
                sup_ids = []

            if not is_condition_active:
                # Telemetry reading is healthy!
                verif.consecutive_healthy_count += 1
                if reading.id not in sup_ids:
                    sup_ids.append(reading.id)
                verif.supporting_telemetry_ids = json.dumps(sup_ids)
                verif.verification_timestamp = now_ts
                verif.evaluated_predictions = json.dumps({
                    "telemetry_id": reading.id,
                    "failure_probability_pct": round(prob_pct, 2),
                    "risk_category": risk,
                    "anomaly": is_anomaly,
                    "consecutive_healthy": verif.consecutive_healthy_count
                })

                if verif.consecutive_healthy_count >= verif.required_healthy_count:
                    # Successfully resolved!
                    verif.status = "RESOLVED"
                    verif.evidence = (
                        f"RECOVERY VERIFIED: {verif.consecutive_healthy_count} consecutive healthy telemetry cycles confirmed. "
                        f"Original fault '{cond}' is fully cleared. Current physical parameters nominal: "
                        f"Speed={reading.rotational_speed or 0:.0f} rpm, Torque={reading.torque or 0:.1f} Nm, "
                        f"Wear={reading.tool_wear or 0:.1f} min, Vibration={reading.vibration or 0:.2f} mm/s, "
                        f"Failure Probability={prob_pct:.1f}% ({risk})."
                    )
                    inc.status = "Resolved"
                    inc.resolved_at = now_ts
                    inc.updated_at = now_ts

                    # Resolve any linked alerts
                    if inc.alert_id:
                        al = db.query(Alert).filter(Alert.id == inc.alert_id).first()
                        if al and al.status != "RESOLVED":
                            al.status = "RESOLVED"
                            al.resolved_at = now_ts
                            al.resolution_note = f"Resolved via verified maintenance completion (Incident {inc.incident_id})"
                else:
                    verif.status = "IN_PROGRESS"
                    verif.evidence = (
                        f"Verification in progress: {verif.consecutive_healthy_count}/{verif.required_healthy_count} "
                        f"consecutive healthy cycles observed at telemetry #{reading.id}."
                    )
                    inc.updated_at = now_ts
            else:
                # Problem re-occurred during verification!
                verif.status = "NOT FIXED"
                verif.consecutive_healthy_count = 0
                verif.verification_timestamp = now_ts
                verif.evidence = (
                    f"VERIFICATION FAILED: Original abnormal condition recurred during verification window at telemetry #{reading.id}. "
                    f"Fault reason: {retrigger_reason}. "
                    f"Sensor values at failure: Speed={reading.rotational_speed or 0:.0f} rpm, Torque={reading.torque or 0:.1f} Nm, "
                    f"Wear={reading.tool_wear or 0:.1f} min, Vibration={reading.vibration or 0:.2f} mm/s."
                )
                inc.status = "Not Fixed"
                inc.updated_at = now_ts

            updated_verifications.append(verif)

        # ---------------------------------------------------------------------
        # 2. DETECT CRITICAL CONDITIONS & CREATE INCIDENTS
        # ---------------------------------------------------------------------
        # Candidates for critical incidents:
        # A. Critical operational rules (OSF, TWF limit, extreme PWF)
        # B. High or Critical ML failure risk
        # C. Critical vibration
        incident_candidates = []

        for v in violations:
            if v["severity"] == "CRITICAL" or v.get("rule_code") in ["OSF", "TWF"]:
                incident_candidates.append({
                    "condition_type": v["rule_code"],
                    "severity": "CRITICAL",
                    "title": v["title"],
                    "description": v["reason"],
                    "triggering_values": v["triggering_values"],
                    "failure_prob": prob,
                    "anomaly_score": pred_result.get("anomaly_score")
                })

        if risk == "Critical" or (prob_pct >= 80.0):
            incident_candidates.append({
                "condition_type": "ML_FAILURE",
                "severity": "CRITICAL",
                "title": f"Critical Failure Risk Forecast: {machine.name}",
                "description": f"Machine failure probability elevated to {prob_pct:.1f}% ({risk}). Urgent physical inspection required.",
                "triggering_values": {
                    "failure_probability_pct": round(prob_pct, 2),
                    "risk_category": risk,
                    "contributing_factors": pred_result.get("contributing_factors", [])
                },
                "failure_prob": prob,
                "anomaly_score": pred_result.get("anomaly_score")
            })

        # Deduplicate and create incidents
        active_statuses = ["Open", "Acknowledged", "Under Maintenance", "Verification Pending"]
        for cand in incident_candidates:
            c_type = cand["condition_type"]

            # Check if active incident already exists for this machine and condition
            existing_active = db.query(Incident).filter(
                Incident.machine_id == machine.machine_id,
                Incident.condition_type == c_type,
                Incident.status.in_(active_statuses)
            ).first()

            if not existing_active:
                # Find matching alert ID if present
                matching_alert = next((
                    a for a in alerts_created
                    if (a.threshold_or_rule and c_type in a.threshold_or_rule) or
                       (a.reason and c_type in a.reason) or
                       (a.alert_type == "failure_risk" and c_type == "ML_FAILURE")
                ), None)

                inc_id = IncidentManager.generate_incident_id(machine.machine_id, c_type, now_ts)
                new_inc = Incident(
                    incident_id=inc_id,
                    machine_id=machine.machine_id,
                    machine_name=machine.name,
                    telemetry_id=reading.id,
                    prediction_id=prediction.id,
                    alert_id=matching_alert.id if matching_alert else None,
                    condition_type=c_type,
                    severity=cand["severity"],
                    status="Open",
                    title=cand["title"],
                    description=cand["description"],
                    triggering_values=json.dumps(cand["triggering_values"]),
                    failure_probability=cand["failure_prob"],
                    anomaly_score=cand["anomaly_score"],
                    created_at=now_ts,
                    updated_at=now_ts
                )
                db.add(new_inc)
                created_incidents.append(new_inc)

        db.flush()
        return created_incidents, updated_verifications
