-- ==============================================================================
-- MachineGuard: Master Supabase Schema, RLS, Seed & Realtime Setup
-- Execute this script in the Supabase SQL Editor of your new project.
-- ==============================================================================

-- 1. MACHINES TABLE
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

-- 2. SENSOR READINGS TABLE (AI4I physical sensors + plant conditions)
CREATE TABLE IF NOT EXISTS sensor_readings (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(64) NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- AI4I 2020 Physical Features (Required for ML inference)
    air_temperature REAL,       -- Ambient temperature in K
    process_temperature REAL,   -- Process temperature in K
    rotational_speed REAL,      -- Spindle speed in rpm
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

-- 3. PREDICTIONS TABLE (Failure forecasting, anomaly detection, RUL)
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

-- 4. ALERTS TABLE (Rule violations, ML high risk, anomaly alerts)
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

-- 5. MAINTENANCE LOGS TABLE
CREATE TABLE IF NOT EXISTS maintenance_logs (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(64) NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    incident_id VARCHAR(64),
    action VARCHAR(128) NOT NULL,
    technician VARCHAR(128) DEFAULT 'System Operator',
    notes TEXT DEFAULT '',
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    completed_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_maintenance_machine_timestamp ON maintenance_logs(machine_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_maintenance_incident_id ON maintenance_logs(incident_id);

-- 6. INCIDENTS TABLE
CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(64) UNIQUE NOT NULL,
    machine_id VARCHAR(64) NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    machine_name VARCHAR(128) NOT NULL,
    telemetry_id INTEGER REFERENCES sensor_readings(id) ON DELETE SET NULL,
    prediction_id INTEGER REFERENCES predictions(id) ON DELETE SET NULL,
    alert_id INTEGER REFERENCES alerts(id) ON DELETE SET NULL,
    condition_type VARCHAR(64) NOT NULL,
    severity VARCHAR(32) DEFAULT 'CRITICAL',     -- 'CRITICAL', 'WARNING'
    status VARCHAR(32) DEFAULT 'Open',           -- 'Open', 'Acknowledged', 'Under Maintenance', 'Verification Pending', 'Resolved', 'Not Fixed'
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    triggering_values TEXT DEFAULT '{}',         -- JSON string of triggering sensor values
    failure_probability REAL,
    anomaly_score REAL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(128),
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_incidents_machine_status ON incidents(machine_id, status);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at DESC);

-- 7. INCIDENT VERIFICATIONS TABLE (Evidence-based recovery verification)
CREATE TABLE IF NOT EXISTS incident_verifications (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(64) NOT NULL,
    machine_id VARCHAR(64) NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    maintenance_log_id INTEGER REFERENCES maintenance_logs(id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL,                 -- 'RESOLVED', 'NOT FIXED', 'IN_PROGRESS'
    consecutive_healthy_count INTEGER DEFAULT 0,
    required_healthy_count INTEGER DEFAULT 3,
    verification_timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    evidence TEXT DEFAULT '',
    supporting_telemetry_ids TEXT DEFAULT '[]',  -- JSON array of reading IDs
    evaluated_predictions TEXT DEFAULT '{}',     -- JSON snapshot of re-evaluated ML predictions
    notes TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_verifications_incident ON incident_verifications(incident_id);
CREATE INDEX IF NOT EXISTS idx_verifications_timestamp ON incident_verifications(verification_timestamp DESC);

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

-- ==============================================================================
-- SEED INITIAL FLEET MACHINES (IDEMPOTENT)
-- ==============================================================================
INSERT INTO machines (machine_id, name, machine_type, location, description, type_variant, status)
VALUES
    (
        'CNC-001',
        'Simulated CNC Milling Machine',
        'CNC Mill',
        'Bay 1 - Precision Milling Cell',
        '3-axis precision milling machine instrumented with AI4I physical telemetry sensors.',
        'M',
        'ONLINE'
    ),
    (
        'CNC-101',
        'Vertical CNC Milling Center 1',
        'CNC Mill',
        'Bay A - Precision Machining Cell',
        '5-axis vertical machining center for titanium aerostructure components.',
        'M',
        'ONLINE'
    ),
    (
        'PUMP-201',
        'High-Pressure Centrifugal Pump A',
        'Centrifugal Pump',
        'Utility Plant - Cooling Loop 2',
        'Variable-speed cooling fluid circulation pump rated for 350 GPM.',
        'L',
        'ONLINE'
    ),
    (
        'PRESS-301',
        'Hydraulic Stamping Press 300T',
        'Hydraulic Press',
        'Stamping Line 3',
        'Heavy duty 300-ton hydraulic sheet metal forming press.',
        'H',
        'ONLINE'
    ),
    (
        'COMP-401',
        'Rotary Screw Air Compressor B',
        'Air Compressor',
        'Compressor House 1',
        'Primary pneumatic supply rotary compressor operating at 7.5 bar nominal.',
        'M',
        'ONLINE'
    ),
    (
        'ROBOT-501',
        '6-Axis Articulated Welding Robot',
        'Robotic Arm',
        'Assembly Cell 4',
        'High-precision robotic welding arm equipped with load torque feedback.',
        'L',
        'ONLINE'
    )
ON CONFLICT (machine_id) DO NOTHING;

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE machines ENABLE ROW LEVEL SECURITY;
ALTER TABLE sensor_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE incident_verifications ENABLE ROW LEVEL SECURITY;

-- 1. Service Role Policies (Unrestricted access for local backend)
DO $$
BEGIN
    DROP POLICY IF EXISTS service_role_all_machines ON machines;
    CREATE POLICY service_role_all_machines ON machines FOR ALL TO service_role USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS service_role_all_readings ON sensor_readings;
    CREATE POLICY service_role_all_readings ON sensor_readings FOR ALL TO service_role USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS service_role_all_predictions ON predictions;
    CREATE POLICY service_role_all_predictions ON predictions FOR ALL TO service_role USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS service_role_all_alerts ON alerts;
    CREATE POLICY service_role_all_alerts ON alerts FOR ALL TO service_role USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS service_role_all_maintenance ON maintenance_logs;
    CREATE POLICY service_role_all_maintenance ON maintenance_logs FOR ALL TO service_role USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS service_role_all_incidents ON incidents;
    CREATE POLICY service_role_all_incidents ON incidents FOR ALL TO service_role USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS service_role_all_verifications ON incident_verifications;
    CREATE POLICY service_role_all_verifications ON incident_verifications FOR ALL TO service_role USING (true) WITH CHECK (true);
END $$;

-- 2. Public / Anon & Authenticated Policies (For Vercel React Dashboard)
DO $$
BEGIN
    -- Machines: Full CRUD for operators on Vercel
    DROP POLICY IF EXISTS public_read_machines ON machines;
    CREATE POLICY public_read_machines ON machines FOR SELECT TO anon, authenticated USING (true);

    DROP POLICY IF EXISTS public_insert_machines ON machines;
    CREATE POLICY public_insert_machines ON machines FOR INSERT TO anon, authenticated WITH CHECK (true);

    DROP POLICY IF EXISTS public_update_machines ON machines;
    CREATE POLICY public_update_machines ON machines FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS public_delete_machines ON machines;
    CREATE POLICY public_delete_machines ON machines FOR DELETE TO anon, authenticated USING (true);

    -- Sensor readings & Predictions: Read-only for dashboard (writes come from local ML backend)
    DROP POLICY IF EXISTS public_read_readings ON sensor_readings;
    CREATE POLICY public_read_readings ON sensor_readings FOR SELECT TO anon, authenticated USING (true);

    DROP POLICY IF EXISTS public_read_predictions ON predictions;
    CREATE POLICY public_read_predictions ON predictions FOR SELECT TO anon, authenticated USING (true);

    -- Alerts: Read & Update status (Acknowledge / Resolve)
    DROP POLICY IF EXISTS public_read_alerts ON alerts;
    CREATE POLICY public_read_alerts ON alerts FOR SELECT TO anon, authenticated USING (true);

    DROP POLICY IF EXISTS public_update_alerts ON alerts;
    CREATE POLICY public_update_alerts ON alerts FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);

    -- Maintenance logs: Read, Insert & Update for field technicians
    DROP POLICY IF EXISTS public_read_maintenance ON maintenance_logs;
    CREATE POLICY public_read_maintenance ON maintenance_logs FOR SELECT TO anon, authenticated USING (true);

    DROP POLICY IF EXISTS public_insert_maintenance ON maintenance_logs;
    CREATE POLICY public_insert_maintenance ON maintenance_logs FOR INSERT TO anon, authenticated WITH CHECK (true);

    DROP POLICY IF EXISTS public_update_maintenance ON maintenance_logs;
    CREATE POLICY public_update_maintenance ON maintenance_logs FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);

    -- Incidents: Read, Insert & Update (lifecycle transitions)
    DROP POLICY IF EXISTS public_read_incidents ON incidents;
    CREATE POLICY public_read_incidents ON incidents FOR SELECT TO anon, authenticated USING (true);

    DROP POLICY IF EXISTS public_insert_incidents ON incidents;
    CREATE POLICY public_insert_incidents ON incidents FOR INSERT TO anon, authenticated WITH CHECK (true);

    DROP POLICY IF EXISTS public_update_incidents ON incidents;
    CREATE POLICY public_update_incidents ON incidents FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);

    -- Incident Verifications: Read, Insert & Update
    DROP POLICY IF EXISTS public_read_verifications ON incident_verifications;
    CREATE POLICY public_read_verifications ON incident_verifications FOR SELECT TO anon, authenticated USING (true);

    DROP POLICY IF EXISTS public_insert_verifications ON incident_verifications;
    CREATE POLICY public_insert_verifications ON incident_verifications FOR INSERT TO anon, authenticated WITH CHECK (true);

    DROP POLICY IF EXISTS public_update_verifications ON incident_verifications;
    CREATE POLICY public_update_verifications ON incident_verifications FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);
END $$;

-- ==============================================================================
-- REPLICA IDENTITY FULL (For Instant Realtime Diff Events)
-- ==============================================================================
ALTER TABLE machines REPLICA IDENTITY FULL;
ALTER TABLE alerts REPLICA IDENTITY FULL;
ALTER TABLE incidents REPLICA IDENTITY FULL;
ALTER TABLE incident_verifications REPLICA IDENTITY FULL;
ALTER TABLE maintenance_logs REPLICA IDENTITY FULL;

-- ==============================================================================
-- SUPABASE REALTIME PUBLICATION
-- ==============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        CREATE PUBLICATION supabase_realtime;
    END IF;
END $$;

ALTER PUBLICATION supabase_realtime ADD TABLE machines;
ALTER PUBLICATION supabase_realtime ADD TABLE sensor_readings;
ALTER PUBLICATION supabase_realtime ADD TABLE predictions;
ALTER PUBLICATION supabase_realtime ADD TABLE alerts;
ALTER PUBLICATION supabase_realtime ADD TABLE incidents;
ALTER PUBLICATION supabase_realtime ADD TABLE maintenance_logs;
ALTER PUBLICATION supabase_realtime ADD TABLE incident_verifications;
