"""
MachinaGuard - Centralized Machine Health & Consistency Assessment Service
Evaluates multi-model consensus between:
1. AI4I 2020 Random Forest Failure Classifier
2. AI4I Isolation Forest Operational Anomaly Detector
3. MachinaGuard RUL Regressor
4. Physical Operational Rules & Active Alert State
"""

from typing import Dict, Any, List, Optional, Tuple


class MachineHealthService:
    """
    Centralized health aggregation service enforcing scientific consistency.
    States:
      - 'Healthy': Low failure risk (<20%), nominal sensor dynamics (score >= 0.0),
                   no active unresolved critical/warning alerts.
      - 'Warning': Elevated failure risk (20-50%), OR operational anomaly (score < 0.0),
                   OR non-critical operational threshold exceeded, OR unresolved warning alert.
      - 'Critical': Failure risk exceeds threshold (>=50%), OR validated critical physical failure (PWF/OSF),
                    OR unresolved critical alert.
      - 'Warning (Model Disagreement)': When the failure classifier and anomaly detector
                    diverge (e.g. Failure Classifier predicts 0.1% risk, but Isolation Forest flags
                    an unusual operational regime with score < 0.0). Reasons are explicitly recorded.
    """

    @staticmethod
    def evaluate_health(
        failure_prob: Optional[float],
        failure_risk_category: str,
        is_anomaly: bool,
        anomaly_score: Optional[float],
        rul_cycles: Optional[float],
        active_critical_alerts: int = 0,
        active_warning_alerts: int = 0,
        operational_violations: Optional[List[str]] = None
    ) -> Tuple[str, bool, str]:
        """
        Determines the unified machine health status.
        Returns:
            (health_status, model_disagreement_flag, disagreement_reason)
        """
        violations = operational_violations or []
        prob = failure_prob if failure_prob is not None else 0.0
        # Normalize prob to [0, 1] if represented as percentage
        prob_norm = prob / 100.0 if prob > 1.0 else prob
        risk = failure_risk_category or "Low"

        model_disagreement = False
        disagreement_reason = ""

        # 1. Check for Model Disagreement
        # Scenario A: Failure Classifier says Low Risk (< 0.20), but Isolation Forest flags an Outlier (score < 0.0)
        if prob_norm < 0.20 and is_anomaly and anomaly_score is not None and anomaly_score < 0.0:
            model_disagreement = True
            disagreement_reason = (
                f"Model Disagreement: AI4I Failure Classifier indicates Low Risk ({prob_norm*100:.1f}%), "
                f"but Isolation Forest detected an operational anomaly (score: {anomaly_score:+.4f}). "
                f"The machinery is operating in an atypical state that has not historically caused sudden failure."
            )

        # Scenario B: Failure Classifier predicts High/Critical Risk (>= 0.50), but Isolation Forest considers it Normal (score >= 0.05)
        elif prob_norm >= 0.50 and not is_anomaly and anomaly_score is not None and anomaly_score >= 0.05:
            model_disagreement = True
            disagreement_reason = (
                f"Model Disagreement: AI4I Failure Classifier indicates {risk} Risk ({prob_norm*100:.1f}%), "
                f"while Isolation Forest identifies the sensor combination as nominal density (score: {anomaly_score:+.4f}). "
                f"High risk may be driven by cumulative tool wear or power thresholds rather than novel outlier dynamics."
            )

        # 2. Determine Overall Health Status
        # CRITICAL conditions
        has_critical_violation = any(v in violations for v in ["PWF", "OSF"])
        if (
            risk in ["Critical", "High"]
            or prob_norm >= 0.50
            or active_critical_alerts > 0
            or has_critical_violation
        ):
            return "Critical", model_disagreement, disagreement_reason

        # MODEL DISAGREEMENT condition (Elevates to Warning with explicit diagnostic notes)
        if model_disagreement:
            return "Warning (Model Disagreement)", model_disagreement, disagreement_reason

        # WARNING conditions
        has_warning_violation = any(v in violations for v in ["HDF", "TWF", "VIBRATION"])
        if (
            risk == "Medium"
            or (0.20 <= prob_norm < 0.50)
            or is_anomaly
            or active_warning_alerts > 0
            or has_warning_violation
            or (rul_cycles is not None and rul_cycles < 25.0)
        ):
            return "Warning", False, ""

        # HEALTHY condition
        return "Healthy", False, ""


health_service = MachineHealthService()
