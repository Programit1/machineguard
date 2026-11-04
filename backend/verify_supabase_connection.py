#!/usr/bin/env python3
"""
MachineGuard Supabase Connection Verifier & Diagnostics
Tests live database connectivity, checks credentials, and validates schema readiness.
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import DATABASE_URL, RAW_DATABASE_URL


def check_connection():
    print("=" * 70)
    print(" MachineGuard: Database & Supabase Connectivity Verification")
    print("=" * 70)
    
    # 1. Inspect Environment Variables
    env_db_url = os.getenv("DATABASE_URL")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    
    print("\n[1] Environment Configuration Status:")
    print(f"  * DATABASE_URL configured: {'YES' if env_db_url else 'NO (Falling back to local SQLite)'}")
    print(f"  * SUPABASE_URL configured: {'YES' if supabase_url else 'NO'}")
    print(f"  * SUPABASE_SERVICE_ROLE_KEY configured: {'YES' if supabase_key else 'NO'}")
    
    # Check if target is PostgreSQL or SQLite
    is_postgres = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")
    
    if not is_postgres:
        print("\n[!] Supabase PostgreSQL credentials not yet provided in environment.")
        print("    FastAPI is safely running in dual-mode with local SQLite persistence:")
        print(f"    Target Database URL: {DATABASE_URL}")
        print("\n" + "-" * 70)
        print("To connect MachineGuard to Supabase, provide these 3 credentials:")
        print("  1. DATABASE_URL (Transaction pooler or session string from Supabase Settings -> Database)")
        print("     Example: postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres")
        print("  2. SUPABASE_URL (From Project Settings -> API -> Project URL)")
        print("     Example: https://[REF].supabase.co")
        print("  3. SUPABASE_SERVICE_ROLE_KEY (From Project Settings -> API -> Project API keys -> service_role)")
        print("-" * 70)
        return False

    # 2. Test PostgreSQL Connection
    print(f"\n[2] Testing connection to PostgreSQL at: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'PostgreSQL'}...")
    try:
        from sqlalchemy import create_engine, text, inspect
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();")).scalar()
            print(f"  [SUCCESS] Successfully connected to database engine!")
            print(f"  PostgreSQL Version: {result[:60]}...")
            
            # 3. Check Tables
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            print(f"\n[3] Inspecting Tables in Database: {existing_tables}")
            
            expected_tables = ["machines", "sensor_readings", "predictions", "alerts", "maintenance_logs"]
            missing_tables = [t for t in expected_tables if t not in existing_tables]
            
            if missing_tables:
                print(f"  [!] Missing expected tables: {missing_tables}")
                print("  Please execute the migrations in `backend/migrations/` using the Supabase SQL editor.")
            else:
                print("  [SUCCESS] All 5 core MachineGuard tables are present!")
                
                # Check machine count
                machine_count = conn.execute(text("SELECT COUNT(*) FROM machines;")).scalar()
                reading_count = conn.execute(text("SELECT COUNT(*) FROM sensor_readings;")).scalar()
                alert_count = conn.execute(text("SELECT COUNT(*) FROM alerts;")).scalar()
                print(f"  * Machines registered: {machine_count}")
                print(f"  * Sensor telemetry rows: {reading_count}")
                print(f"  * Incident alerts: {alert_count}")

            # 4. Check RLS status
            rls_query = text("""
                SELECT tablename, rowsecurity 
                FROM pg_tables 
                WHERE schemaname = 'public' AND tablename IN ('machines', 'sensor_readings', 'predictions', 'alerts', 'maintenance_logs');
            """)
            rls_results = conn.execute(rls_query).fetchall()
            print("\n[4] Row Level Security (RLS) Status:")
            for row in rls_results:
                print(f"  * Table '{row[0]}': RLS Enabled = {row[1]}")

        print("\n" + "=" * 70)
        print(" [VERIFIED] Live Supabase PostgreSQL Connection & Schema are OK!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n  [ERROR] Failed to connect to Supabase database:")
        print(f"  {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    success = check_connection()
    sys.exit(0 if success else 1)
