from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field

# --- Machine Schemas ---
class MachineBase(BaseModel):
    name: str = Field(..., example="CNC Milling Center A-1")
    machine_type: str = Field(..., example="CNC Mill")
    location: str = Field(..., example="Shop Floor - Bay 3")
    description: Optional[str] = Field(default="", example="5-axis precision vertical CNC mill")
    type_variant: Optional[str] = Field(default="M", example="M", description="Quality variant: 'L' (Low), 'M' (Medium), 'H' (High)")

class MachineCreate(MachineBase):
    machine_id: str = Field(..., example="CNC-001", min_length=2, max_length=64)

class MachineUpdate(BaseModel):
    name: Optional[str] = None
    machine_type: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    type_variant: Optional[str] = None

class MachineResponse(MachineBase):
    id: Union[str, int]
    machine_id: str
    status: str = "ONLINE"
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Telemetry Schemas ---
class TelemetryCreate(BaseModel):
    machine_id: str = Field(..., example="CNC-001")
    machine_name: Optional[str] = None
    equipment_type: Optional[str] = None
    
    # AI4I 2020 Physical Features (Required for ML failure prediction)
    air_temperature: Optional[float] = Field(None, description="Air temperature in K or °C (e.g. 298.15 K)")
    process_temperature: Optional[float] = Field(None, description="Process temperature in K or °C (e.g. 308.65 K)")
    rotational_speed: Optional[float] = Field(None, description="Spindle / rotor rotational speed in rpm")
    torque: Optional[float] = Field(None, description="Torque in Nm")
    tool_wear: Optional[float] = Field(None, description="Cumulative tool wear in minutes")
    
    # Plant Condition Monitoring Telemetry
    temperature: Optional[float] = Field(None, description="Core/bearing temperature in °C")
    vibration: Optional[float] = Field(None, description="Vibration velocity in mm/s")
    pressure: Optional[float] = Field(None, description="Hydraulic/pneumatic line pressure in bar")
    power_consumption: Optional[float] = Field(None, description="Power drawn in kW")
    operating_load: Optional[float] = Field(None, description="Operating Load in %")
    
    timestamp: Optional[datetime] = None

class TelemetryResponse(BaseModel):
    id: int
    machine_id: str
    timestamp: datetime
    air_temperature: Optional[float] = None
    process_temperature: Optional[float] = None
    rotational_speed: Optional[float] = None
    torque: Optional[float] = None
    tool_wear: Optional[float] = None
    temperature: Optional[float] = None
    vibration: Optional[float] = None
    pressure: Optional[float] = None
    power_consumption: Optional[float] = None
    operating_load: Optional[float] = None

    class Config:
        from_attributes = True

# --- Prediction Schemas ---
class PredictionResponse(BaseModel):
    id: Optional[int] = None
    telemetry_id: Optional[int] = None
    machine_id: str
    timestamp: datetime
    
    # Failure Prediction
    failure_probability: Optional[float] = None # Decimal probability [0.0, 1.0]
    raw_probability: Optional[float] = None     # Raw model probability in [0.0, 1.0]
    risk_category: str = "Low"
    prediction_available: bool = True
    failure_prediction: Optional[int] = 0
    
    # Anomaly Detection
    anomaly: Optional[bool] = False
    anomaly_detected: Optional[bool] = False
    anomaly_score: Optional[float] = None
    anomaly_label: Optional[str] = "Normal"
    
    # Remaining Useful Life
    estimated_remaining_cuts: Optional[float] = None
    rul_unit: str = "machining cuts"
    rul_available: bool = False
    
    # Health Assessment & Consistency
    machine_health_status: Optional[str] = "Healthy"
    model_disagreement: Optional[bool] = False
    disagreement_reason: Optional[str] = ""

    model_name: Optional[str] = "AI4I RandomForestClassifier"
    contributing_factors: List[str] = []
    recommendation: str = ""

    class Config:
        from_attributes = True

# --- Alert & Notification Schemas ---
class AlertResponse(BaseModel):
    id: int
    telemetry_id: Optional[int] = None
    prediction_id: Optional[int] = None
    machine_id: str
    machine_name: str
    timestamp: datetime
    risk_level: str
    severity: str = "HIGH"
    alert_type: str = "failure_risk" # failure_risk, anomaly, operational_rule
    alert_source: str = "ml_failure" # ml_failure, anomaly, operational_rule
    title: str = ""
    reason: str
    threshold_or_rule: Optional[str] = ""
    sensor_values: Any = {}
    triggering_values: Any = {}
    recommendation: str = ""
    status: str = "ACTIVE"
    resolution_note: Optional[str] = ""
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AlertStatusUpdate(BaseModel):
    status: str = Field(..., example="acknowledged", pattern="^(acknowledged|resolved|ACKNOWLEDGED|RESOLVED)$")

# --- Machine Card & Dashboard Summaries ---
class MachineCardSummary(BaseModel):
    id: str # Returns machine_id (e.g. CNC-001) to satisfy verification scripts and UI
    machine_id: str
    name: str
    machine_type: str
    location: str
    description: str
    type_variant: str = "M"
    is_online: bool
    status: str = "ONLINE" # ONLINE or OFFLINE
    last_telemetry_time: Optional[datetime] = None
    latest_reading: Optional[TelemetryResponse] = None
    latest_prediction: Optional[PredictionResponse] = None
    health_status: str # "Healthy", "Attention Required", "High Risk", "Critical Risk", "No Data"
    active_alerts_count: int

class DashboardSummaryResponse(BaseModel):
    total_machines: int
    online_machines: int
    healthy_machines: int
    attention_machines: int
    high_risk_machines: int
    critical_risk_machines: int
    active_alerts_count: int
    risk_distribution: Dict[str, int] # {"Low": x, "Medium": y, "High": z, "Critical": w}
    recent_alerts: List[AlertResponse]
    recent_telemetry: List[TelemetryResponse]

# --- Dedicated ML Endpoint Schemas ---
class FailurePredictionRequest(BaseModel):
    machine_id: Optional[str] = Field("CNC-001", example="CNC-001")
    Type: Optional[str] = Field("M", example="M", description="Quality type: L, M, or H")
    air_temperature: Optional[float] = Field(None, example=298.15, description="Air temperature in K (or °C if < 150)")
    process_temperature: Optional[float] = Field(None, example=308.65, description="Process temperature in K (or °C if < 150)")
    rotational_speed: Optional[float] = Field(None, example=1551.0, description="Rotational speed in rpm")
    torque: Optional[float] = Field(None, example=42.8, description="Torque in Nm")
    tool_wear: Optional[float] = Field(None, example=120.0, description="Tool wear in minutes")
    
    # Support alternate dict key formatting from raw AI4I CSV
    extra_features: Optional[Dict[str, Any]] = None

class FailurePredictionResponse(BaseModel):
    machine_id: Optional[str] = None
    failure_prediction: int
    failure_probability: float # Decimal [0.0, 1.0]
    failure_probability_pct: Optional[float] = None # Percentage [0.0%, 100.0%]
    risk_category: str
    model: str = "AI4I RandomForestClassifier"
    version: str = "1.0.0"
    timestamp: datetime
    contributing_factors: List[str] = []
    recommendation: str = ""

class AnomalyDetectionRequest(BaseModel):
    machine_id: Optional[str] = Field("CNC-001", example="CNC-001")
    Type: Optional[str] = Field("M", example="M")
    air_temperature: Optional[float] = Field(None, example=298.15)
    process_temperature: Optional[float] = Field(None, example=308.65)
    rotational_speed: Optional[float] = Field(None, example=1551.0)
    torque: Optional[float] = Field(None, example=42.8)
    tool_wear: Optional[float] = Field(None, example=120.0)

class AnomalyDetectionResponse(BaseModel):
    machine_id: Optional[str] = None
    anomaly: bool
    label: str # "Normal" or "Anomaly"
    anomaly_score: float # Isolation Forest decision function score
    model: str = "AI4I IsolationForest"
    version: str = "1.0.0"
    timestamp: datetime
    note: str = "Anomaly score is not failure probability."

class RULPredictionRequest(BaseModel):
    machine_id: Optional[str] = Field("CNC-001", example="CNC-001")
    cycle: Optional[float] = Field(None, example=45, description="Current operational cycle number")
    tool_wear_min: Optional[float] = Field(None, example=52.0, description="Tool wear contact time in minutes")
    vibration_mm_s: Optional[float] = Field(None, example=0.82, description="Vibration velocity in mm/s")
    torque_nm: Optional[float] = Field(None, example=39.5, description="Torque in Nm")
    process_temperature_k: Optional[float] = Field(None, example=311.2, description="Process temperature in K")
    air_temperature_k: Optional[float] = Field(None, example=300.1, description="Ambient air temperature in K")
    rotational_speed_rpm: Optional[float] = Field(None, example=1560.0, description="Rotational speed in rpm")
    control_type: Optional[str] = Field("A", example="B", description="Control regime / sensor suite: A, B, or C")
    
    # Backward compatibility fields for legacy PHM tests
    force_x_rms: Optional[float] = None
    force_y_rms: Optional[float] = None
    force_z_rms: Optional[float] = None
    vibration_x_rms: Optional[float] = None
    vibration_y_rms: Optional[float] = None
    vibration_z_rms: Optional[float] = None
    ae_rms: Optional[float] = None

class RULPredictionResponse(BaseModel):
    machine_id: Optional[str] = None
    estimated_remaining_cycles: Optional[float] = None
    estimated_remaining_cuts: Optional[float] = None # Compatibility alias
    unit: str = "cycles"
    rul_available: bool = True
    model: str = "MachinaGuard RUL Regressor"
    version: str = "1.0.0"
    timestamp: datetime
    note: str = "Remaining useful life forecast in operational cycles based on machine degradation trajectory."
    explanation: Optional[str] = None

class ModelStatusDetail(BaseModel):
    name: str
    loaded: bool
    algorithm: str
    dataset: str
    features: List[str]
    status: str
    notes: Optional[str] = None

class MLModelsStatusResponse(BaseModel):
    failure_model: ModelStatusDetail
    anomaly_model: ModelStatusDetail
    rul_model: ModelStatusDetail
    all_ready: bool

class MLMetadataResponse(BaseModel):
    failure_model: Optional[Dict[str, Any]] = None
    anomaly_model: Optional[Dict[str, Any]] = None
    rul_model: Optional[Dict[str, Any]] = None

class MLEvaluationReportsResponse(BaseModel):
    failure_evaluation: Optional[Dict[str, Any]] = None
    anomaly_evaluation: Optional[Dict[str, Any]] = None
    rul_evaluation: Optional[Dict[str, Any]] = None

# --- Incident Management & Verification Schemas ---
class IncidentResponse(BaseModel):
    id: int
    incident_id: str
    machine_id: str
    machine_name: str
    telemetry_id: Optional[int] = None
    prediction_id: Optional[int] = None
    alert_id: Optional[int] = None
    condition_type: str
    severity: str = "CRITICAL"
    status: str = "Open"
    title: str
    description: str
    triggering_values: Any = {}
    failure_probability: Optional[float] = None
    anomaly_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class IncidentStatusUpdate(BaseModel):
    status: str = Field(..., example="Acknowledged", description="Status: Open, Acknowledged, Under Maintenance, Verification Pending, Resolved, Not Fixed")
    operator_name: Optional[str] = Field("Operator", example="Operator John")

class MaintenanceCreate(BaseModel):
    machine_id: str = Field(..., example="CNC-001")
    incident_id: Optional[str] = Field(None, example="INC-20261104-001")
    action: str = Field(..., example="Replaced worn cutter insert and recalibrated coolant pressure")
    technician: Optional[str] = Field("System Operator", example="Tech Lead Alex")
    notes: Optional[str] = Field("", example="Spindle inspected; tool wear counter reset")

class MaintenanceResponse(BaseModel):
    id: int
    machine_id: str
    incident_id: Optional[str] = None
    action: str
    technician: str
    notes: Optional[str] = ""
    timestamp: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class IncidentVerificationResponse(BaseModel):
    id: int
    incident_id: str
    machine_id: str
    maintenance_log_id: Optional[int] = None
    status: str # RESOLVED, NOT FIXED, IN_PROGRESS
    consecutive_healthy_count: int
    required_healthy_count: int = 3
    verification_timestamp: datetime
    evidence: str
    supporting_telemetry_ids: Any = []
    evaluated_predictions: Any = {}
    notes: Optional[str] = ""

    class Config:
        from_attributes = True

