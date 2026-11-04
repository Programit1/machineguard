-- ==============================================================================
-- Migration 004: Critical Incident Management & Maintenance Verification
-- Target: Supabase PostgreSQL
-- ==============================================================================

-- 1. Incidents Table
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

-- 2. Extend maintenance_logs to reference incidents
ALTER TABLE maintenance_logs ADD COLUMN IF NOT EXISTS incident_id VARCHAR(64);
ALTER TABLE maintenance_logs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ DEFAULT NOW();

-- 3. Incident Verifications Table (Evidence-based recovery verification)
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

-- 4. Enable Row Level Security (RLS)
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE incident_verifications ENABLE ROW LEVEL SECURITY;

-- 5. Drop existing policies if reapplying
DROP POLICY IF EXISTS "service_role_all_incidents" ON incidents;
DROP POLICY IF EXISTS "service_role_all_verifications" ON incident_verifications;
DROP POLICY IF EXISTS "public_read_incidents" ON incidents;
DROP POLICY IF EXISTS "public_update_incidents" ON incidents;
DROP POLICY IF EXISTS "public_read_verifications" ON incident_verifications;
DROP POLICY IF EXISTS "public_insert_maintenance" ON maintenance_logs;
DROP POLICY IF EXISTS "public_update_alerts" ON alerts;

-- 6. Service Role Policies (Full access for local FastAPI backend)
CREATE POLICY "service_role_all_incidents" ON incidents
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "service_role_all_verifications" ON incident_verifications
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- 7. Public / Anon Policies (For Vercel React Dashboard)
-- Read-only access to incidents and verifications
CREATE POLICY "public_read_incidents" ON incidents
    FOR SELECT
    TO anon, authenticated
    USING (true);

-- Operators can acknowledge or change incident status (e.g. to 'Under Maintenance', 'Verification Pending')
CREATE POLICY "public_update_incidents" ON incidents
    FOR UPDATE
    TO anon, authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "public_read_verifications" ON incident_verifications
    FOR SELECT
    TO anon, authenticated
    USING (true);

-- Operators can log maintenance actions from the frontend
CREATE POLICY "public_insert_maintenance" ON maintenance_logs
    FOR INSERT
    TO anon, authenticated
    WITH CHECK (true);

-- Operators can acknowledge or resolve alerts
CREATE POLICY "public_update_alerts" ON alerts
    FOR UPDATE
    TO anon, authenticated
    USING (true)
    WITH CHECK (true);

-- 8. Enable Supabase Realtime Publication for condition monitoring
-- Add tables to the supabase_realtime publication safely
DO $$
BEGIN
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE machines;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END;

    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE sensor_readings;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END;

    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE predictions;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END;

    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE alerts;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END;

    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE incidents;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END;

    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE maintenance_logs;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END;

    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE incident_verifications;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END;
END $$;
