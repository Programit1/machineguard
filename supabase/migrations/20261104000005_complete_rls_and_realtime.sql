-- Migration: 20261104000005_complete_rls_and_realtime.sql
-- Description: Complete RLS policies for operator UI operations and enable REPLICA IDENTITY FULL for rich Realtime payloads

-- 1. Machines policies for operator UI (create, update, delete assets from Vercel dashboard)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'machines' AND policyname = 'public_insert_machines') THEN
        CREATE POLICY public_insert_machines ON machines FOR INSERT TO anon, authenticated WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'machines' AND policyname = 'public_update_machines') THEN
        CREATE POLICY public_update_machines ON machines FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'machines' AND policyname = 'public_delete_machines') THEN
        CREATE POLICY public_delete_machines ON machines FOR DELETE TO anon, authenticated USING (true);
    END IF;
END $$;

-- 2. Incidents policies for operator actions
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'incidents' AND policyname = 'public_insert_incidents') THEN
        CREATE POLICY public_insert_incidents ON incidents FOR INSERT TO anon, authenticated WITH CHECK (true);
    END IF;
END $$;

-- 3. Incident Verifications policies for operator maintenance submissions
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'incident_verifications' AND policyname = 'public_insert_verifications') THEN
        CREATE POLICY public_insert_verifications ON incident_verifications FOR INSERT TO anon, authenticated WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'incident_verifications' AND policyname = 'public_update_verifications') THEN
        CREATE POLICY public_update_verifications ON incident_verifications FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);
    END IF;
END $$;

-- 4. Maintenance logs update policy
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'maintenance_logs' AND policyname = 'public_update_maintenance') THEN
        CREATE POLICY public_update_maintenance ON maintenance_logs FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);
    END IF;
END $$;

-- 5. REPLICA IDENTITY FULL for seamless Realtime updates
ALTER TABLE machines REPLICA IDENTITY FULL;
ALTER TABLE alerts REPLICA IDENTITY FULL;
ALTER TABLE incidents REPLICA IDENTITY FULL;
ALTER TABLE incident_verifications REPLICA IDENTITY FULL;
ALTER TABLE maintenance_logs REPLICA IDENTITY FULL;
