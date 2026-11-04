-- ==============================================================================
-- Migration 001: MachineGuard Schema Initialization
-- Target: Supabase PostgreSQL
-- ==============================================================================

-- 1. Machines Table
CREATE TABLE IF NOT EXISTS machines (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL,
    machine_type VARCHAR(64) NOT NULL,
    location VARCHAR(128) NOT NULL,
    description TEXT DEFAULT '',
    type_variant VARCHAR(8) DEFAULT 'M', -- 'L' (Low), 'M' (Medium), 'H' (High) for AI4I classification
    status VARCHAR(32) DEFAULT 'ONLINE',  -- 'ONLINE' or 'OFFLINE'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_machines_machine_id ON machines(machine_id);

-- 2. Sensor Readings Table (AI4I physical sensors + condition monitoring)
CREATE TABLE IF NOT EXISTS sensor_readings (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(64) NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- AI4I 2020 Physical Features (Required for ML inference)
    air_temperature REAL,       -- Ambient temperature in K (e.g. 298.15 K)
    process_temperature REAL,   -- Process temperature in K (e.g. 308.65 K)
    rotational_speed REAL,      -- Spindle / rotor speed in rpm
    torque REAL,                -- Torque in Nm
    tool_wear REAL,             -- Cumulative tool contact wear in minutes

    -- Plant Condition Monitoring Telemetry
    temperature REAL,           -- Bearing / oil temperature in °C
    vibration REAL,             -- Vibration velocity RMS in mm/s
    pressure REAL,              -- Hydraulic / pneumatic pressure in bar
    power_consumption REAL,     -- Power consumption in kW
    operating_load REAL         -- Motor operating load in %
);

CREATE INDEX IF NOT EXISTS idx_readings_machine_timestamp ON sensor_readings(machine_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON sensor_readings(timestamp DESC);

-- 3. Predictions Table (Failure forecasting, anomaly detection, RUL)
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    telemetry_id INTEGER REFERENCES sensor_readings(id) ON DELETE CASCADE,
    machine_id VARCHAR(64) NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Module 1: Failure Prediction (AI4I Random Forest)
    failure_probability REAL,              -- Calibrated failure probability [0.0, 1.0]
    raw_probability REAL,                  -- Raw unrounded model probability
    risk_category VARCHAR(32) DEFAULT 'Low', -- 'Low', 'Medium', 'High', 'Critical'
    prediction_available INTEGER DEFAULT 1, -- 1 if valid, 0 if unavailable
    failure_prediction INTEGER DEFAULT 0,  -- 0 = Normal, 1 = Failure predicted

    -- Module 2: Anomaly Detection (AI4I Isolation Forest)
    anomaly_detected INTEGER DEFAULT 0,    -- 0 = Normal, 1 = Anomaly flagged
    anomaly_score REAL,                    -- Decision function score
    anomaly_label VARCHAR(32) DEFAULT 'Normal', -- 'Normal' or 'Anomaly'

    -- Module 3: Remaining Useful Life (MachinaGuard RUL Regressor)
    estimated_remaining_cuts REAL,         -- Estimated cycles/cuts remaining
    rul_unit VARCHAR(32) DEFAULT 'cycles',
    rul_available INTEGER DEFAULT 0,

    -- Unified Health Assessment & Cross-Model Consistency
    machine_health_status VARCHAR(32) DEFAULT 'Healthy',
    model_disagreement INTEGER DEFAULT 0,
    disagreement_reason TEXT DEFAULT '',

    -- Metadata & Prescriptive Advice
    model_name VARCHAR(64) DEFAULT 'AI4I RandomForestClassifier',
    contributing_factors TEXT DEFAULT '[]', -- JSON array
    recommendation TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_predictions_machine_timestamp ON predictions(machine_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_telemetry_id ON predictions(telemetry_id);

-- 4. Incident Alerts Table (Rule violations, ML high risk, anomaly alerts)
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    telemetry_id INTEGER REFERENCES sensor_readings(id) ON DELETE SET NULL,
    prediction_id INTEGER REFERENCES predictions(id) ON DELETE SET NULL,
    machine_id VARCHAR(64) NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    machine_name VARCHAR(128) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    risk_level VARCHAR(32) NOT NULL,        -- 'Low', 'Medium', 'High', 'Critical'
    severity VARCHAR(32) DEFAULT 'HIGH',    -- 'INFO', 'WARNING', 'HIGH', 'CRITICAL'
    alert_type VARCHAR(32) DEFAULT 'failure_risk',
    alert_source VARCHAR(32) DEFAULT 'ml_failure',
    title VARCHAR(128) DEFAULT '',
    reason VARCHAR(255) NOT NULL,
    threshold_or_rule VARCHAR(128) DEFAULT '',
    sensor_values TEXT DEFAULT '{}',        -- JSON snapshot of reading
    triggering_values TEXT DEFAULT '{}',    -- JSON snapshot of triggering values
    recommendation TEXT DEFAULT '',
    status VARCHAR(32) DEFAULT 'ACTIVE',    -- 'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED'
    resolution_note TEXT DEFAULT '',
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_machine_timestamp ON alerts(machine_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_prediction_id ON alerts(prediction_id);

-- 5. Maintenance Logs Table
CREATE TABLE IF NOT EXISTS maintenance_logs (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(64) NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    action VARCHAR(128) NOT NULL,
    technician VARCHAR(128) DEFAULT 'System Operator',
    notes TEXT DEFAULT '',
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_maintenance_machine_timestamp ON maintenance_logs(machine_id, timestamp DESC);

-- Trigger: Automatically update updated_at on machines table
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_machines_updated_at ON machines;
CREATE TRIGGER trigger_machines_updated_at
BEFORE UPDATE ON machines
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();
