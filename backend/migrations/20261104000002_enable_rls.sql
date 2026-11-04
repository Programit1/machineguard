-- ==============================================================================
-- Migration 002: Row Level Security (RLS) & Access Control
-- Target: Supabase PostgreSQL
-- ==============================================================================

-- 1. Enable RLS on all MachineGuard tables
ALTER TABLE machines ENABLE ROW LEVEL SECURITY;
ALTER TABLE sensor_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_logs ENABLE ROW LEVEL SECURITY;

-- 2. Drop existing policies if reapplying
DROP POLICY IF EXISTS "service_role_all_machines" ON machines;
DROP POLICY IF EXISTS "service_role_all_readings" ON sensor_readings;
DROP POLICY IF EXISTS "service_role_all_predictions" ON predictions;
DROP POLICY IF EXISTS "service_role_all_alerts" ON alerts;
DROP POLICY IF EXISTS "service_role_all_maintenance" ON maintenance_logs;

DROP POLICY IF EXISTS "public_read_machines" ON machines;
DROP POLICY IF EXISTS "public_read_readings" ON sensor_readings;
DROP POLICY IF EXISTS "public_read_predictions" ON predictions;
DROP POLICY IF EXISTS "public_read_alerts" ON alerts;
DROP POLICY IF EXISTS "public_read_maintenance" ON maintenance_logs;

-- 3. Service Role: Full administrative access for the FastAPI backend
-- The FastAPI backend connects with the PostgreSQL connection string or service role key
CREATE POLICY "service_role_all_machines" ON machines
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "service_role_all_readings" ON sensor_readings
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "service_role_all_predictions" ON predictions
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "service_role_all_alerts" ON alerts
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "service_role_all_maintenance" ON maintenance_logs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- 4. Public / Anon access: Read-Only for dashboards
-- All writes are strictly rejected unless coming from the trusted backend service
CREATE POLICY "public_read_machines" ON machines
    FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "public_read_readings" ON sensor_readings
    FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "public_read_predictions" ON predictions
    FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "public_read_alerts" ON alerts
    FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "public_read_maintenance" ON maintenance_logs
    FOR SELECT
    TO anon, authenticated
    USING (true);
