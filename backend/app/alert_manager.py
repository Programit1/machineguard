"""
MachinaGuard - Alert Manager with Deduplication, Auto-Resolution & Physical Rule Verification
Enforces strict consistency between current telemetry, model outputs, and active alerts.
"""

import json
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import Alert, Machine, SensorReading, Prediction
from .config import ALERT_RISK_THRESHOLD, ANOMALY_ALERT_SCORE_THRESHOLD


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AlertManager:
    """
    Coordinates alert lifecycle:
    1. Evaluates physical operational failure rules (PWF, OSF, HDF, TWF, Vibration) on current telemetry.
    2. Auto-resolves previously ACTIVE alerts whose underlying physical or ML conditions have normalized.
    3. Deduplicates alerts so machines with sustained conditions do not flood the database.
    4. Stores exact telemetry_id, prediction_id, and triggering values for 100% auditability.
    """

    @staticmethod
    def evaluate_operational_rules(
        machine: Machine,
        air_temp: Optional[float],
        proc_temp: Optional[float],
        rot_speed: Optional[float],
        torque: Optional[float],
        tool_wear: Optional[float],
        vibration: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluates physical operational rules derived from AI4I predictive maintenance domain physics.
        Returns a list of triggered rule descriptions.
        """
        violations = []
        variant = (getattr(machine, "type_variant", "M") or "M").upper()

        # 1. Power Failure (PWF): Mechanical power outside [3500 W, 9000 W]
        # P = Torque (Nm) * Rotational_speed (rad/s) = Torque * (Speed * 2 * pi / 60)
        if torque is not None and rot_speed is not None:
            t_val = float(torque)
            s_val = float(rot_speed)
            mech_power_w = t_val * (s_val * 2.0 * math.pi / 60.0)
            if mech_power_w < 3500.0 or mech_power_w > 9000.0:
                is_crit = mech_power_w < 2500.0 or mech_power_w > 10000.0
                violations.append({
                    "rule_code": "PWF",
                    "title": f"Power Envelope Violation (PWF): {machine.name}",
                    "reason": f"Mechanical power is {mech_power_w:.1f} W (allowed envelope: 3,500 W – 9,000 W).",
                    "threshold_or_rule": "PWF: mechanical power outside [3500 W, 9000 W]",
                    "severity": "CRITICAL" if is_crit else "HIGH",
                    "alert_type": "operational_rule",
                    "alert_source": "operational_rule",
                    "triggering_values": {
                        "torque_Nm": t_val,
                        "rotational_speed_rpm": s_val,
                        "mechanical_power_W": round(mech_power_w, 2)
                    },
                    "recommendation": "Inspect spindle drive and cutting resistance; adjust feed rate and rotational speed."
                })

        # 2. Overstrain Failure (OSF): Tool wear (min) * Torque (Nm) exceeds product threshold
        osf_limits = {"L": 11000.0, "M": 12000.0, "H": 13000.0}
        osf_limit = osf_limits.get(variant, 12000.0)
        if tool_wear is not None and torque is not None:
            tw_val = float(tool_wear)
            t_val = float(torque)
            strain_product = tw_val * t_val
            if strain_product > osf_limit:
                violations.append({
                    "rule_code": "OSF",
                    "title": f"Overstrain Failure (OSF): {machine.name}",
                    "reason": f"Overstrain product is {strain_product:.1f} min·Nm (exceeds variant {variant} limit of {osf_limit:.0f} min·Nm).",
                    "threshold_or_rule": f"OSF: tool_wear * torque > {osf_limit:.0f} min·Nm",
                    "severity": "CRITICAL",
                    "alert_type": "operational_rule",
                    "alert_source": "operational_rule",
                    "triggering_values": {
                        "tool_wear_min": tw_val,
                        "torque_Nm": t_val,
                        "overstrain_product": round(strain_product, 2),
                        "limit": osf_limit
                    },
                    "recommendation": "Reduce cutting torque immediately and replace worn cutter insert."
                })

        # 3. Heat Dissipation Failure (HDF): Temp diff < 8.6 K and speed < 1380 rpm
        if air_temp is not None and proc_temp is not None and rot_speed is not None:
            a_k = float(air_temp) if float(air_temp) > 150.0 else float(air_temp) + 273.15
            p_k = float(proc_temp) if float(proc_temp) > 150.0 else float(proc_temp) + 273.15
            delta_t = p_k - a_k
            s_val = float(rot_speed)
            if delta_t < 8.6 and s_val < 1380.0:
                violations.append({
                    "rule_code": "HDF",
                    "title": f"Heat Dissipation Failure (HDF): {machine.name}",
                    "reason": f"Process thermal gradient is insufficient ({delta_t:.1f} K < 8.6 K) at low speed ({s_val:.0f} rpm < 1380 rpm).",
                    "threshold_or_rule": "HDF: (Process Temp - Air Temp) < 8.6 K and Speed < 1380 rpm",
                    "severity": "HIGH",
                    "alert_type": "operational_rule",
                    "alert_source": "operational_rule",
                    "triggering_values": {
                        "air_temp_K": round(a_k, 2),
                        "process_temp_K": round(p_k, 2),
                        "delta_temp_K": round(delta_t, 2),
                        "rotational_speed_rpm": s_val
                    },
                    "recommendation": "Check coolant flow, heat exchanger, and increase rotational speed to clear heat buildup."
                })

        # 4. Tool Wear Failure (TWF): Accumulated tool wear exceeds design replacement limit
        if tool_wear is not None:
            tw_val = float(tool_wear)
            if tw_val >= 240.0:
                violations.append({
                    "rule_code": "TWF",
                    "title": f"Tool Wear Limit Exceeded (TWF): {machine.name}",
                    "reason": f"Cutter tool wear reached {tw_val:.1f} min (exceeds recommended end-of-life limit 240 min).",
                    "threshold_or_rule": "TWF: tool_wear >= 240 min",
                    "severity": "CRITICAL",
                    "alert_type": "operational_rule",
                    "alert_source": "operational_rule",
                    "triggering_values": {"tool_wear_min": tw_val, "limit": 240.0},
                    "recommendation": "Halt machining and replace cutter insert before tool failure occurs."
                })
            elif tw_val >= 200.0 and torque is not None and float(torque) > 55.0:
                violations.append({
                    "rule_code": "TWF",
                    "title": f"Elevated Cutter Wear & Torque: {machine.name}",
                    "reason": f"Tool wear {tw_val:.1f} min with elevated cutting torque {float(torque):.1f} Nm.",
                    "threshold_or_rule": "TWF Warning: tool_wear >= 200 min and torque > 55 Nm",
                    "severity": "HIGH",
                    "alert_type": "operational_rule",
                    "alert_source": "operational_rule",
                    "triggering_values": {"tool_wear_min": tw_val, "torque_Nm": float(torque)},
                    "recommendation": "Schedule cutter replacement at next production shift transition."
                })

        # 5. Vibration Anomaly: ISO 10816 limit (> 5.0 mm/s)
        if vibration is not None and float(vibration) >= 5.0:
            v_val = float(vibration)
            violations.append({
                "rule_code": "VIBRATION",
                "title": f"Excessive Mechanical Vibration: {machine.name}",
                "reason": f"Measured vibration is {v_val:.2f} mm/s (exceeds ISO 10816 boundary 5.0 mm/s).",
                "threshold_or_rule": "ISO 10816: vibration >= 5.0 mm/s",
                "severity": "HIGH",
                "alert_type": "operational_rule",
                "alert_source": "operational_rule",
                "triggering_values": {"vibration_mms": v_val, "threshold": 5.0},
                "recommendation": "Inspect machine spindle bearings, mounting balance, and tool clamp tension."
            })

        return violations

    @staticmethod
    def sync_machine_alerts(
        db: Session,
        machine: Machine,
        reading: SensorReading,
        prediction: Prediction,
        pred_result: Dict[str, Any]
    ) -> List[Alert]:
        """
        Synchronizes all alerts for the given machine based on current telemetry and ML outputs:
        1. Auto-resolves existing active alerts that are no longer supported by current conditions.
        2. Deduplicates: adds new alerts only if no active alert for the same condition exists.
        Returns any newly created Alert instances.
        """
        created_alerts: List[Alert] = []
        now_ts = reading.timestamp or utcnow()

        # Extract current physical telemetry
        air_t = reading.air_temperature
        proc_t = reading.process_temperature
        rot_s = reading.rotational_speed
        torq = reading.torque
        tw = reading.tool_wear
        vibe = reading.vibration

        # Extract current ML predictions
        prob = pred_result.get("failure_probability")
        prob_pct = (prob * 100.0) if (prob is not None and prob <= 1.0) else (prob or 0.0)
        risk = pred_result.get("risk_category", "Low")
        is_anomaly = bool(pred_result.get("anomaly", False))
        anomaly_score = pred_result.get("anomaly_score")

        # 1. Evaluate Current Violations
        op_violations = AlertManager.evaluate_operational_rules(
            machine=machine,
            air_temp=air_t,
            proc_temp=proc_t,
            rot_speed=rot_s,
            torque=torq,
            tool_wear=tw,
            vibration=vibe
        )
        active_op_codes = {v["rule_code"] for v in op_violations}

        # Determine if ML Failure condition is currently triggered
        ml_failure_triggered = (
            pred_result.get("prediction_available", True)
            and (prob_pct >= ALERT_RISK_THRESHOLD or risk in ["High", "Critical"])
        )

        # Determine if Anomaly condition is currently triggered
        anomaly_triggered = (
            is_anomaly
            and anomaly_score is not None
            and anomaly_score < ANOMALY_ALERT_SCORE_THRESHOLD
        )

        # 2. Auto-Resolve Stale Active Alerts
        active_alerts = db.query(Alert).filter(
            Alert.machine_id == machine.machine_id,
            func.lower(Alert.status) == "active"
        ).all()

        for alert in active_alerts:
            should_resolve = False
            res_note = ""

            # Check if this alert was an operational rule (PWF, OSF, HDF, TWF, VIBRATION)
            rule_matched = None
            for code in ["PWF", "OSF", "HDF", "TWF", "VIBRATION"]:
                if (alert.threshold_or_rule and code in alert.threshold_or_rule) or \
                   (alert.reason and code in alert.reason) or \
                   (alert.title and code in alert.title):
                    rule_matched = code
                    break

            if rule_matched:
                if rule_matched not in active_op_codes:
                    should_resolve = True
                    res_note = (
                        f"Auto-resolved at telemetry #{reading.id}: {rule_matched} condition cleared. "
                        f"Current readings normalized (Speed: {rot_s or 0:.0f} rpm, Torque: {torq or 0:.1f} Nm, Wear: {tw or 0:.1f} min)."
                    )

            elif alert.alert_source == "ml_failure" or alert.alert_type == "failure_risk":
                if not ml_failure_triggered:
                    should_resolve = True
                    res_note = (
                        f"Auto-resolved at telemetry #{reading.id}: Failure risk decreased to {risk} "
                        f"({prob_pct:.1f}% failure probability, below {ALERT_RISK_THRESHOLD}% threshold)."
                    )

            elif alert.alert_source == "anomaly" or alert.alert_type == "anomaly":
                if not anomaly_triggered:
                    should_resolve = True
                    score_str = f"{anomaly_score:+.4f}" if anomaly_score is not None else "N/A"
                    res_note = (
                        f"Auto-resolved at telemetry #{reading.id}: Operational anomaly cleared "
                        f"(decision score: {score_str} >= {ANOMALY_ALERT_SCORE_THRESHOLD})."
                    )

            elif alert.status.upper() == "ACTIVE" and not ml_failure_triggered and not active_op_codes:
                # Catch-all for legacy alerts (e.g. Alert #22) where all machine parameters are currently nominal
                should_resolve = True
                res_note = (
                    f"Auto-resolved at telemetry #{reading.id}: All machine parameters and predictive risk normalized."
                )

            if should_resolve:
                alert.status = "RESOLVED"
                alert.resolved_at = now_ts
                alert.resolution_note = res_note

        db.flush() # Ensure resolved status is persisted in the session before subsequent queries

        # 3. Create New Alerts with Deduplication
        sensor_snapshot = {
            "air_temperature": air_t,
            "process_temperature": proc_t,
            "rotational_speed": rot_s,
            "torque": torq,
            "tool_wear": tw,
            "vibration": vibe,
            "temperature": reading.temperature,
            "pressure": reading.pressure,
            "power_consumption": reading.power_consumption,
            "operating_load": reading.operating_load
        }

        # A. Create alerts for triggered operational rules
        for viol in op_violations:
            code = viol["rule_code"]
            # Deduplication check: Is there already an active alert for this rule?
            has_active = any(
                a.status == "ACTIVE" and (
                    (a.threshold_or_rule and code in a.threshold_or_rule) or
                    (a.reason and code in a.reason) or
                    (a.title and code in a.title)
                )
                for a in active_alerts
            )
            if not has_active:
                new_a = Alert(
                    telemetry_id=reading.id,
                    prediction_id=prediction.id,
                    machine_id=machine.machine_id,
                    machine_name=machine.name,
                    timestamp=now_ts,
                    risk_level="Critical" if viol["severity"] == "CRITICAL" else "High",
                    severity=viol["severity"],
                    alert_type=viol["alert_type"],
                    alert_source=viol["alert_source"],
                    title=viol["title"],
                    reason=viol["reason"],
                    threshold_or_rule=viol["threshold_or_rule"],
                    triggering_values=json.dumps(viol["triggering_values"]),
                    sensor_values=json.dumps(sensor_snapshot),
                    recommendation=viol["recommendation"],
                    status="ACTIVE"
                )
                db.add(new_a)
                created_alerts.append(new_a)

        # B. Create alert for ML failure risk if triggered
        if ml_failure_triggered:
            has_active_failure = any(
                a.status == "ACTIVE" and (a.alert_source == "ml_failure" or a.alert_type == "failure_risk")
                for a in active_alerts
            )
            if not has_active_failure:
                factors = pred_result.get("contributing_factors", [])
                factor_text = "; ".join(factors[:2]) if factors else "Elevated risk index"
                new_f_alert = Alert(
                    telemetry_id=reading.id,
                    prediction_id=prediction.id,
                    machine_id=machine.machine_id,
                    machine_name=machine.name,
                    timestamp=now_ts,
                    risk_level=risk,
                    severity="CRITICAL" if risk == "Critical" else "HIGH",
                    alert_type="failure_risk",
                    alert_source="ml_failure",
                    title=f"{risk.upper()} Failure Risk: {machine.name}",
                    reason=f"{risk} Risk Detected ({prob_pct:.1f}% failure probability). {factor_text}",
                    threshold_or_rule=f"AI4I Failure Probability >= {ALERT_RISK_THRESHOLD}%",
                    triggering_values=json.dumps({
                        "failure_probability_pct": round(prob_pct, 2),
                        "risk_category": risk,
                        "contributing_factors": factors
                    }),
                    sensor_values=json.dumps(sensor_snapshot),
                    recommendation=pred_result.get("recommendation", "Inspect machine telemetry."),
                    status="ACTIVE"
                )
                db.add(new_f_alert)
                created_alerts.append(new_f_alert)

        # C. Create alert for Anomaly if triggered and no higher failure alert was created
        if anomaly_triggered and not ml_failure_triggered and not op_violations:
            has_active_anomaly = any(
                a.status == "ACTIVE" and (a.alert_source == "anomaly" or a.alert_type == "anomaly")
                for a in active_alerts
            )
            if not has_active_anomaly:
                new_anom_alert = Alert(
                    telemetry_id=reading.id,
                    prediction_id=prediction.id,
                    machine_id=machine.machine_id,
                    machine_name=machine.name,
                    timestamp=now_ts,
                    risk_level="Medium",
                    severity="WARNING",
                    alert_type="anomaly",
                    alert_source="anomaly",
                    title=f"Operational Anomaly: {machine.name}",
                    reason=f"Isolation Forest flagged atypical sensor combination (anomaly score: {anomaly_score:+.4f}).",
                    threshold_or_rule=f"Isolation Forest Decision Score < {ANOMALY_ALERT_SCORE_THRESHOLD}",
                    triggering_values=json.dumps({
                        "anomaly_score": round(anomaly_score, 4),
                        "threshold": ANOMALY_ALERT_SCORE_THRESHOLD
                    }),
                    sensor_values=json.dumps(sensor_snapshot),
                    recommendation="Review operational parameters and verify sensor calibration.",
                    status="ACTIVE"
                )
                db.add(new_anom_alert)
                created_alerts.append(new_anom_alert)

        if created_alerts:
            db.flush()

        return created_alerts


alert_manager = AlertManager()
