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
# Standard continuous multi-machine stream (1.0s interval)
python data_generator.py --api http://localhost:8000/api --interval 1.0

# Critical Incident Simulation: Inject Overstrain Failure (OSF)
python data_generator.py --target CNC-001 --fault osf --interval 1.0

# Automated Maintenance Recovery Simulation:
# Injects fault for 5 cycles, then automatically resets tool wear & torque to nominal
python data_generator.py --target CNC-001 --fault osf --recover-after 5 --interval 1.0
```

### Terminal 3: Local Frontend (Optional for local testing)
```powershell
cd frontend
npm run dev
```

---

## 4. Critical Incident Notification & Maintenance Verification Workflow

The system provides an audit-grade maintenance lifecycle:

1. **Incident Triggering:**
   - Any physical failure mode (OSF, TWF, PWF, HDF) or High/Critical ML failure risk automatically creates a **Critical Incident** in the `incidents` table (with duplicate cooldown deduplication).
   - High-severity visual banners and audio-style toasts alert plant operators immediately.

2. **Operator Triage:**
   - Operator acknowledges the incident (`ACKNOWLEDGED`), transitions to `UNDER_MAINTENANCE`, and inspects equipment.
   - When physical repair (e.g. tool insert replacement, cooling fluid flush) is done, the engineer records the maintenance intervention:
     - Component replaced (e.g. `Spindle Tool Insert C4-Carbide`).
     - Action type (`TOOL_REPLACEMENT`, `LUBRICATION_FLUSH`, `CALIBRATION`).
     - Technician name and notes.
   - The incident status transitions to **`VERIFICATION_PENDING`**.

3. **Automated Verification Engine:**
   - The backend `IncidentManager` monitors incoming telemetry for the specific machine.
   - It requires **3 consecutive nominal telemetry cycles** where tool wear, torque, speed, and temperatures remain strictly within safe operational thresholds.
   - If 3 nominal cycles are confirmed:
     - Incident transitions to **`RESOLVED`** with verified timestamp and telemetry evidence log in `incident_verifications`.
     - Linked critical alerts are automatically resolved.
   - If abnormal conditions persist or re-occur:
     - Incident transitions to **`NOT_FIXED`**.
     - An alarm is raised alerting the plant supervisor that maintenance was unsuccessful.

---

## 5. Laptop Independence & Offline Behavior
When your laptop is turned off:
1. All past telemetry, machine records, predictions, alerts, and maintenance logs remain fully preserved and queryable on the Vercel dashboard.
2. The Vercel dashboard detects that latest telemetry exceeds `OFFLINE_THRESHOLD_SECONDS` and displays a graceful **"System Offline / Telemetry Paused"** badge.
3. No fabricated or phantom sensor readings will be displayed.
4. When you turn your laptop back on and start the backend/generator, live streaming and ML predictions resume immediately with no duplicates.

---

## 6. Vercel Deployment Instructions

1. Push your repository to GitHub: `https://github.com/Programit1/machineguard`.
2. In your Vercel Dashboard, click **Add New Project** and select `machineguard`.
3. Configure Project Settings:
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
4. Environment Variables:
   - `VITE_SUPABASE_URL`: `https://jojwttixovrtmgfysbde.supabase.co`
   - `VITE_SUPABASE_ANON_KEY`: `[Your Supabase Publishable Anon Key]`
5. Click **Deploy**. Vercel will build and serve your industrial monitoring portal globally 24/7.
