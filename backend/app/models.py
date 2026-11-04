from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from .database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    machine_type = Column(String(64), nullable=False)
    location = Column(String(128), nullable=False)
    description = Column(Text, default="")
    type_variant = Column(String(8), default="M") # 'L', 'M', or 'H' for AI4I type code
    status = Column(String(32), default="ONLINE") # 'ONLINE' or 'OFFLINE'
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Cloud migration entity compatibility aliases
    @property
    def machine_name(self) -> str:
        return self.name

    @machine_name.setter
    def machine_name(self, value: str):
        self.name = value

    @property
    def configuration(self) -> str:
        return self.description

    @configuration.setter
    def configuration(self, value: str):
        self.description = value

class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(String(64), ForeignKey("machines.machine_id", ondelete="CASCADE"), index=True, nullable=False)
    timestamp = Column(DateTime, default=utcnow, index=True, nullable=False)
    
    # AI4I 2020 Physical Sensor Features
    air_temperature = Column(Float, nullable=True)     # in K
    process_temperature = Column(Float, nullable=True) # in K
    rotational_speed = Column(Float, nullable=True)    # in rpm
    torque = Column(Float, nullable=True)              # in Nm
    tool_wear = Column(Float, nullable=True)           # in min

    # Plant Condition Monitoring Telemetry
    temperature = Column(Float, nullable=True)         # in °C
    vibration = Column(Float, nullable=True)           # in mm/s
    pressure = Column(Float, nullable=True)            # in bar
    power_consumption = Column(Float, nullable=True)   # in kW
    operating_load = Column(Float, nullable=True)      # in %

    __table_args__ = (
        Index("ix_readings_machine_time", "machine_id", "timestamp"),
    )

    @property
    def telemetry_id(self) -> int:
        return self.id

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    telemetry_id = Column(Integer, ForeignKey("sensor_readings.id", ondelete="CASCADE"), nullable=True, index=True)
    machine_id = Column(String(64), ForeignKey("machines.machine_id", ondelete="CASCADE"), index=True, nullable=False)
    timestamp = Column(DateTime, default=utcnow, index=True, nullable=False)
    
    # Failure Prediction (AI4I RandomForestClassifier)
    failure_probability = Column(Float, nullable=True) # Decimal probability [0.0, 1.0] or None if unavailable
    raw_probability = Column(Float, nullable=True)     # Raw unrounded model probability in [0.0, 1.0]
    risk_category = Column(String(32), default="Low")  # Low, Medium, High, Critical, Unavailable
    prediction_available = Column(Integer, default=1)   # 1 if valid prediction generated, 0 if unavailable
    failure_prediction = Column(Integer, default=0)    # 0 = Normal, 1 = Failure predicted
    
    # Anomaly Detection (AI4I IsolationForest)
    anomaly_detected = Column(Integer, default=0)      # 0 = Normal, 1 = Anomaly
    anomaly_score = Column(Float, nullable=True)       # Isolation Forest decision_function score
    anomaly_label = Column(String(32), default="Normal") # "Normal" or "Anomaly"
    
    # Remaining Useful Life (MachinaGuard RUL Regressor)
    estimated_remaining_cuts = Column(Float, nullable=True) # Estimated cycles remaining
    rul_unit = Column(String(32), default="cycles")
    rul_available = Column(Integer, default=0)         # 1 if compatible sensors present, 0 if unavailable
    
    # Health Assessment & Model Consistency
    machine_health_status = Column(String(32), default="Healthy") # Healthy, Warning, Critical, Warning (Model Disagreement)
    model_disagreement = Column(Integer, default=0)    # 1 if classifier and anomaly detector conflict
    disagreement_reason = Column(Text, default="")

    # Model Metadata
    model_name = Column(String(64), default="AI4I RandomForestClassifier")
    contributing_factors = Column(Text, default="[]")   # JSON array of strings
    recommendation = Column(Text, default="")

    __table_args__ = (
        Index("ix_predictions_machine_time", "machine_id", "timestamp"),
    )

    # Cloud migration entity compatibility aliases
    @property
    def failure_risk(self) -> str:
        return self.risk_category

    @property
    def anomaly_status(self) -> str:
        return self.anomaly_label

    @property
    def overall_machine_health(self) -> str:
        return self.machine_health_status

    @property
    def prediction_timestamp(self) -> datetime:
        return self.timestamp

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    telemetry_id = Column(Integer, ForeignKey("sensor_readings.id", ondelete="CASCADE"), nullable=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="CASCADE"), nullable=True, index=True)
    machine_id = Column(String(64), ForeignKey("machines.machine_id", ondelete="CASCADE"), index=True, nullable=False)
    machine_name = Column(String(128), nullable=False)
    timestamp = Column(DateTime, default=utcnow, index=True, nullable=False)
    risk_level = Column(String(32), nullable=False)     # Low, Medium, High, Critical
    severity = Column(String(32), default="HIGH")       # INFO, WARNING, HIGH, CRITICAL
    alert_type = Column(String(32), default="failure_risk") # failure_risk, anomaly, operational_rule, maintenance
    alert_source = Column(String(32), default="ml_failure") # ml_failure, anomaly, operational_rule
    title = Column(String(128), default="")
    reason = Column(String(255), nullable=False)
    threshold_or_rule = Column(String(128), default="") # e.g. "PWF: mechanical power > 9000 W"
    sensor_values = Column(Text, default="{}")          # JSON snapshot of reading
    triggering_values = Column(Text, default="{}")      # JSON snapshot of exact values causing alert
    recommendation = Column(Text, default="")
    status = Column(String(32), default="ACTIVE", index=True) # ACTIVE, ACKNOWLEDGED, RESOLVED
    resolution_note = Column(Text, default="")
    first_seen_at = Column(DateTime, default=utcnow)
    last_seen_at = Column(DateTime, default=utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Cloud migration entity compatibility aliases
    @property
    def description(self) -> str:
        return self.reason

    @description.setter
    def description(self, value: str):
        self.reason = value

    @property
    def recommended_action(self) -> str:
        return self.recommendation

    @recommended_action.setter
    def recommended_action(self, value: str):
        self.recommendation = value

class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(String(64), ForeignKey("machines.machine_id", ondelete="CASCADE"), index=True, nullable=False)
    incident_id = Column(String(64), nullable=True, index=True)
    action = Column(String(128), nullable=False)
    technician = Column(String(128), default="System Operator")
    notes = Column(Text, default="")
    timestamp = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, default=utcnow)

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(64), unique=True, index=True, nullable=False)
    machine_id = Column(String(64), ForeignKey("machines.machine_id", ondelete="CASCADE"), index=True, nullable=False)
    machine_name = Column(String(128), nullable=False)
    telemetry_id = Column(Integer, ForeignKey("sensor_readings.id", ondelete="SET NULL"), nullable=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True)
    condition_type = Column(String(64), nullable=False)
    severity = Column(String(32), default="CRITICAL") # CRITICAL, WARNING
    status = Column(String(32), default="Open", index=True) # Open, Acknowledged, Under Maintenance, Verification Pending, Resolved, Not Fixed
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    triggering_values = Column(Text, default="{}") # JSON snapshot of triggering values
    failure_probability = Column(Float, nullable=True)
    anomaly_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(128), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

class IncidentVerification(Base):
    __tablename__ = "incident_verifications"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(64), index=True, nullable=False)
    machine_id = Column(String(64), ForeignKey("machines.machine_id", ondelete="CASCADE"), index=True, nullable=False)
    maintenance_log_id = Column(Integer, ForeignKey("maintenance_logs.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(32), nullable=False) # RESOLVED, NOT FIXED, IN_PROGRESS
    consecutive_healthy_count = Column(Integer, default=0)
    required_healthy_count = Column(Integer, default=3)
    verification_timestamp = Column(DateTime, default=utcnow, index=True, nullable=False)
    evidence = Column(Text, default="")
    supporting_telemetry_ids = Column(Text, default="[]") # JSON array of telemetry IDs
    evaluated_predictions = Column(Text, default="{}") # JSON snapshot of evaluated predictions
    notes = Column(Text, default="")
