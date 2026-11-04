# MachineGuard: Cloud Deployment & Integration Guide (Render + Supabase + Vercel)

This guide provides exact step-by-step instructions to deploy MachineGuard to **Render** (FastAPI backend + ML models) and **Vercel** (React frontend), connected to your live **Supabase PostgreSQL** database.

---

## Architecture Overview

```
[ Laptop: data_generator.py ]
          │  HTTP POST /api/telemetry (runs locally on your laptop)
          ▼
[ Render: FastAPI Backend + 3 ML Models ] (https://<your-app>.onrender.com)
          │  • Loads AI4I Random Forest Failure Classifier
          │  • Loads AI4I Isolation Forest Anomaly Detector
          │  • Loads RUL Random Forest Regressor
          │  • Synchronizes reading.id, prediction.id, alert.prediction_id
          ▼
[ Cloud Database: Supabase PostgreSQL ] (aws-0-ap-southeast-2.pooler.supabase.com)
          │  • 5 core tables with RLS: machines, sensor_readings, predictions, alerts, maintenance_logs
          ▼
[ Vercel: React Production Dashboard ] (https://<your-app>.vercel.app)
          • Automatically retrieves updated machine fleet status
          • Real-time failure alerts, multi-sensor trend charts, model health status
```

> **Laptop Independence:** The cloud application on Vercel remains accessible 24/7 even when your laptop is turned off. When you turn off your laptop, only the generation of new simulated telemetry pauses; all past data, alerts, machine states, and ML predictions remain live in Supabase.

---

## Step 1: Push Repository to GitHub

Open PowerShell in the project directory:

```powershell
cd C:\Users\samyu\.gemini\antigravity\scratch\predictive-maintenance
```

1. Create a new repository on [GitHub](https://github.com/new) (e.g., `machineguard`).
2. Link your local repository and push:

```powershell
git remote add origin https://github.com/<your-github-username>/machineguard.git
git branch -M main
git push -u origin main
```

*(Note: Sensitive files like `.env`, local SQLite `.db` files, and temporary caches are already safely ignored by `.gitignore` and will never be pushed to GitHub.)*

---

## Step 2: Deploy FastAPI Backend to Render

1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** -> **Blueprint** (or **Web Service**).
3. Connect your GitHub repository (`machineguard`).
4. Render will automatically detect [`render.yaml`](./render.yaml):
   - **Service Name:** `machineguard-backend`
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
5. Configure the **Environment Variables** in the Render Dashboard:

| Environment Variable | Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres` | Live Supabase Session Pooler |
| `SUPABASE_URL` | `https://[PROJECT-REF].supabase.co` | Supabase Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | `[YOUR-SUPABASE-SERVICE-ROLE-KEY]` | Supabase Service Role Key |
| `ALLOWED_ORIGINS` | `*` | Or your Vercel URL once deployed |
| `ALERT_RISK_THRESHOLD` | `50.0` | Failure risk threshold (%) |
| `OFFLINE_THRESHOLD_SECONDS` | `45` | Machine telemetry timeout |
| `ANOMALY_ALERT_SCORE_THRESHOLD` | `0.0` | Isolation Forest decision threshold |

6. Click **Apply** or **Deploy**.
7. Once deployment finishes, Render provides your backend service URL:
   `https://machineguard-backend.onrender.com` (copy this URL).

8. **Verify Backend Cloud Deployment:**
   - Health check: `https://<your-render-url>/api/health`
   - ML models status: `https://<your-render-url>/api/ml/models/status`
   - Swagger interactive docs: `https://<your-render-url>/docs`

---

## Step 3: Deploy Frontend Dashboard to Vercel

1. Log in to [Vercel Dashboard](https://vercel.com).
2. Click **Add New...** -> **Project**.
3. Import your GitHub repository (`machineguard`).
4. In the project setup screen:
   - **Framework Preset:** `Vite` (automatically detected)
   - **Root Directory:** Click **Edit** and choose `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
5. Expand **Environment Variables** and add:

| Key | Value |
| :--- | :--- |
| `VITE_API_URL` | `https://<your-render-url>/api` |

*(Make sure to append `/api` to your Render URL)*

6. Click **Deploy**.
7. Vercel will build the frontend and provide your production URL (e.g. `https://machineguard.vercel.app`).

---

## Step 4: Run Telemetry Generator from Laptop

With your cloud backend and frontend deployed, run the telemetry generator on your laptop targeting the cloud backend:

```powershell
python data_generator.py --api https://<your-render-url>/api --interval 2.0
```

### Telemetry Generator Scenarios:
- **Normal Operation (Continuous Stream):**
  ```powershell
  python data_generator.py --api https://<your-render-url>/api --interval 2.0
  ```
- **Inject Overstrain Failure (OSF):**
  ```powershell
  python data_generator.py --api https://<your-render-url>/api --fault osf --interval 2.0
  ```
- **Inject Heat Dissipation Failure (HDF):**
  ```powershell
  python data_generator.py --api https://<your-render-url>/api --fault hdf --interval 2.0
  ```
- **Inject Power Envelope Failure (PWF):**
  ```powershell
  python data_generator.py --api https://<your-render-url>/api --fault pwf --interval 2.0
  ```
- **Inject Tool Wear Critical Degradation (TWF):**
  ```powershell
  python data_generator.py --api https://<your-render-url>/api --fault twf --interval 2.0
  ```
- **Target a Single Specific Machine (e.g., CNC-101):**
  ```powershell
  python data_generator.py --api https://<your-render-url>/api --target CNC-101 --fault osf
  ```

---

## Verification Checklist

- [x] All 3 ML models loaded in backend memory
- [x] Feature validation rejects invalid/missing data with HTTP 422
- [x] Risk thresholds (<20%, 20-<50%, 50-<80%, >=80%) verified
- [x] RUL reporting cycles with safe null fallback when features missing
- [x] Consistent foreign keys (`reading.id` $\leftrightarrow$ `prediction.telemetry_id` $\leftrightarrow$ `alert.prediction_id`)
- [x] Auto-resolution and deduplication of alerts
- [x] Supabase PostgreSQL connected with RLS enabled across 5 tables
- [x] Render manifest (`render.yaml`) and Vercel manifest (`vercel.json`) prepared
- [x] All 36 automated unit and integration tests passing
