# MachineGuard: Deployment & Architecture Guide (Local + Supabase + Vercel)

This guide documents the final decoupled architecture for MachineGuard:
- **Local Workstation / Laptop:** Python Telemetry Generator, FastAPI Backend, 3 Scikit-Learn ML Models, Prediction and Incident Verification Engine.
- **Cloud Database:** Supabase PostgreSQL with Row Level Security (RLS) and Supabase Realtime publications.
- **Cloud Web Dashboard:** React 19 + Vite Dashboard deployed on Vercel, reading directly from Supabase via the publishable Anon key.

---

## 1. System Architecture & Data Flow

```
[ Local Workstation / Laptop ]
┌─────────────────────────────────┐
│ data_generator.py               │
│ (Discovers machines, sends      │
│  telemetry every 1-2s)          │
└───────────────┬─────────────────┘
                │ HTTP POST /api/telemetry (http://localhost:8000)
                ▼
┌─────────────────────────────────┐
│ Local FastAPI Backend           │
│ • Runs 3 ML Models locally      │
│   - Failure Classifier (AI4I RF)│
│   - Anomaly Detector (AI4I IF)  │
│   - RUL Regressor (RUL RF)      │
│ • Alert & Incident Engine       │
│ • Maintenance Verification Logic│
└───────────────┬─────────────────┘
                │ Direct PostgreSQL (aws-0-ap-southeast-2.pooler.supabase.com)
                │ or Supabase Service-Role API
                ▼
[ Cloud: Supabase Database ]
┌────────────────────────────────────────────────────────┐
│ PostgreSQL 17 + Realtime Engine                        │
│ • Tables: machines, sensor_readings, predictions,       │
│   alerts, incidents, maintenance_logs, verifications   │
│ • Row Level Security (RLS) Active                      │
│ • Realtime Publications Active                         │
└───────────────┬────────────────────────────────────────┘
                │ Direct Supabase Client + Realtime Subscriptions
                │ (Using safe publishable anon key)
                ▼
[ Cloud: Vercel Production Hosting ]
┌────────────────────────────────────────────────────────┐
│ React 19 + Vite Web Dashboard                          │
│ • Accessible 24/7 globally                             │
│ • Live condition monitoring via Realtime               │
│ • Operator Incident Triage & Maintenance Logging       │
│ • Displays Stale / Offline when laptop is turned off   │
└────────────────────────────────────────────────────────┘
```

---

## 2. Environment Variables Summary

### Local Backend (`.env` in project root or `backend/.env`):
- `PORT=8000`
- `DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres`
- `SUPABASE_URL=https://[PROJECT-REF].supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY=[YOUR-SUPABASE-SERVICE-ROLE-KEY]`
- `ALLOWED_ORIGINS=*`
- `ALERT_RISK_THRESHOLD=50.0`
- `OFFLINE_THRESHOLD_SECONDS=45`
- `ANOMALY_ALERT_SCORE_THRESHOLD=0.0`

### Vercel Frontend (Configured in Vercel Project Dashboard):
- `VITE_SUPABASE_URL=https://[PROJECT-REF].supabase.co`
- `VITE_SUPABASE_ANON_KEY=[YOUR-SUPABASE-ANON-PUBLISHABLE-KEY]`

---

## 3. Local Execution Commands

### Terminal 1: Local FastAPI Backend
```powershell
python run.py
# Or: uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2: Standalone Telemetry Generator
```powershell
python data_generator.py --api http://localhost:8000/api --interval 1.0
```

### Terminal 3: Local Frontend (Optional for local testing)
```powershell
cd frontend
npm run dev
```

---

## 4. Laptop Independence & Offline Behavior
When your laptop is turned off:
1. All past telemetry, machine records, predictions, alerts, and maintenance logs remain fully preserved and queryable on the Vercel dashboard.
2. The Vercel dashboard detects that latest telemetry exceeds `OFFLINE_THRESHOLD_SECONDS` and displays a graceful **"System Offline / Telemetry Paused"** badge.
3. No fabricated or phantom sensor readings will be displayed.
4. When you turn your laptop back on and start the backend/generator, live streaming and ML predictions resume immediately with no duplicates.
