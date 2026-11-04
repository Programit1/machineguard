# AI-Driven Predictive Maintenance and Equipment Failure Forecasting Platform for Smart Manufacturing

> **Industrial Engineering & Smart Manufacturing Platform**  
> An industrial IoT condition monitoring and failure prediction system combining an independent Python sensor telemetry generator, high-throughput FastAPI ingestion pipeline, Scikit-Learn Random Forest probabilistic inference, SQLite persistence, and a modern React + Vite industrial monitoring dashboard.

---

## 1. Final Decoupled Architecture & Separation of Concerns

The platform strictly enforces a modern, decoupled edge-to-cloud architecture:

```
[ Local Workstation / Laptop ]
┌─────────────────────────────────┐
│ data_generator.py               │
│ (Discovers registered assets,   │
│  streams telemetry @ 1.0s)      │
└───────────────┬─────────────────┘
                │ HTTP POST /api/telemetry (http://localhost:8000)
                ▼
┌─────────────────────────────────┐
│ Local FastAPI Backend           │
│ • Validates telemetry payload   │
│ • Runs 3 ML Models locally:     │
│   - Failure Classifier (AI4I RF)│
│   - Anomaly Detector (AI4I IF)  │
│   - RUL Regressor (RUL RF)      │
│ • Incident & Alert Engine       │
│ • Maintenance Recovery Engine   │
└───────────────┬─────────────────┘
                │ Direct PostgreSQL Pooler Connection
                │ (or local SQLite offline buffer during outages)
                ▼
[ Cloud: Supabase Database ]
┌────────────────────────────────────────────────────────┐
│ PostgreSQL 17 + Realtime Engine                        │
│ • Tables: machines, sensor_readings, predictions,       │
│   alerts, incidents, maintenance_logs, verifications   │
│ • Row Level Security (RLS) Active                      │
│ • Realtime Publications Active on all 7 tables         │
└───────────────┬────────────────────────────────────────┘
                │ Direct Supabase Client + Realtime Subscriptions
                │ (Using safe publishable anon key)
                ▼
[ Cloud: Vercel Production Hosting ]
┌────────────────────────────────────────────────────────┐
│ React 19 + Vite Industrial SCADA Dashboard             │
│ • 1. Dashboard: Fleet health, stale badges, alerts     │
│ • 2. Machines: Machinery fleet, variant & filter cards │
│ • 3. Alerts & Incidents: Critical incident management  │
│ • 4. Maintenance History: Audit ledger & verification  │
│ • 5. System Status: Latency, DB & ML model diagnostics │
│ • Functions 24/7 even when local laptop is turned off  │
└────────────────────────────────────────────────────────┘
```

### Critical Architectural Guarantees:
1. **Model Training & Evaluation**: All dataset acquisition, feature engineering, model training, evaluation, and comparisons take place **outside the website** via terminal scripts in `ml/`. The website has **no fake training buttons, synthetic dataset generator, or retraining controls**.
2. **Sensor Data Origin**: The website **never produces or fabricates its own sensor readings**. All incoming telemetry arrives via HTTP POST requests from the independent standalone `data_generator.py` program.
3. **Local Inference Only**: The FastAPI backend loads serialized model and preprocessing pipeline artifacts from `ml/models/` for real-time local inference. No ML models or FastAPI servers are hosted on Render or Vercel.
4. **Cloud Persistence & Realtime**: Telemetry and prediction outputs are stored in Supabase PostgreSQL and broadcast instantly to the Vercel dashboard via Supabase Realtime.
5. **24/7 Resilience & Stale Detection**: When the local computer is closed or offline, the Vercel dashboard continues serving persisted records and displays a graceful **"System Offline / Telemetry Paused"** indicator when latest readings exceed 45 seconds.

---

## 2. Directory Structure

```
predictive-maintenance/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, startup lifecycle, migrations & seed data
│   │   ├── config.py            # Paths, thresholds & environment settings
│   │   ├── database.py          # SQLAlchemy SQLite engine & sessionmaker
│   │   ├── models.py            # ORM models (Machine, SensorReading, Prediction, Alert)
│   │   ├── schemas.py           # Pydantic v2 validation schemas
│   │   ├── crud.py              # Database queries, migrations & transaction logic
│   │   ├── ml_service.py        # ML loader, exact preprocessing & diagnostics
│   │   └── routers/
│   │       ├── machines.py      # CRUD endpoints for machines
│   │       ├── telemetry.py     # Ingestion & sensor history endpoints
│   │       ├── predictions.py   # Historical ML predictions endpoint
│   │       ├── alerts.py        # Active alerts & triage endpoints
│   │       └── dashboard.py     # Aggregate statistics & KPI endpoint
│   ├── test_api.py              # Synchronous automated test suite (10/10 passed)
│   └── maintenance.db           # SQLite database
├── frontend/
│   ├── package.json
│   ├── vite.config.js           # Vite config with API proxy to localhost:8000
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx              # Main application shell & live polling
│       ├── index.css            # Light industrial SCADA theme
│       ├── api.js               # Centralized REST API client
│       ├── components/
│       │   ├── Navbar.jsx       # Connectivity status & model badge
│       │   ├── Sidebar.jsx      # Navigation sidebar with alert counters
│       │   ├── MetricCard.jsx   # Industrial telemetry stat cards
│       │   ├── RiskBadge.jsx    # Color-coded risk level badges
│       │   ├── StatusBadge.jsx  # Real-time online/offline indicators
│       │   └── MachineFormModal.jsx # Register and edit machine modal
│       └── pages/
│           ├── Dashboard.jsx    # Fleet metrics, risk pie chart & alerts
│           ├── Machines.jsx     # Fleet management & search/filter grid
│           ├── MachineDetail.jsx# Dedicated machine monitoring & sensor trends
│           ├── Alerts.jsx       # Alert triage, sensor snapshots & resolution
│           └── GeneratorGuide.jsx # Instructions & commands for data_generator.py
├── ml/
│   ├── data/
│   │   └── ai4i2020.csv         # Benchmark dataset: UCI AI4I 2020 (10,000 samples)
│   ├── models/
│   │   ├── failure_model.joblib # Trained Random Forest classifier
│   │   ├── scaler.joblib        # Fitted StandardScaler preprocessing artifact
│   │   └── xgb_model.joblib     # Comparison XGBoost classifier
│   ├── reports/
│   │   └── evaluation_report.md # Comprehensive metrics & edge-case validation report
│   ├── model_metadata.json      # Serialized evaluation metrics & feature metadata
│   ├── train_model.py           # Standalone training script with 80/20 stratified split
│   └── evaluate_model.py        # Standalone evaluation & physical scenario verification
├── data_generator.py            # Standalone telemetry simulator with fault injection
├── requirements.txt             # Python dependencies
└── README.md                    # Project documentation
```

---

## 3. Sensor Schema & Compatibility Resolution

The project legitimately bridges the **UCI AI4I 2020 Predictive Maintenance Dataset** with industrial condition monitoring without fabricating or substituting incompatible features:

| Feature Name | AI4I / ML Feature | Generator Field | Physical Unit | Description |
|---|---|---|---|---|
| `type_variant` | Yes (`Type_H`, `Type_L`, `Type_M`) | `type_variant` | Categorical | Machine product quality variant (L/M/H) |
| `air_temperature` | Yes (`Air temperature [K]`) | `air_temperature` | Kelvin (K) | Ambient inlet air temperature |
| `process_temperature` | Yes (`Process temperature [K]`) | `process_temperature` | Kelvin (K) | Thermal generation at tool/workpiece |
| `rotational_speed` | Yes (`Rotational speed [rpm]`) | `rotational_speed` | rpm | Spindle rotational speed |
| `torque` | Yes (`Torque [Nm]`) | `torque` | Newton-meters (Nm) | Spindle torque |
| `tool_wear` | Yes (`Tool wear [min]`) | `tool_wear` | Minutes (min) | Cumulative tool contact duration |
| `temperature` | Secondary (display) | `temperature` | Celsius (°C) | Converted ambient temperature |
| `vibration` | Plant condition | `vibration` | mm/s | Bearing vibration velocity |
| `pressure` | Plant condition | `pressure` | bar | Hydraulic lubrication line pressure |
| `power_consumption` | Derived / condition | `power_consumption` | kW | Motor electrical power draw |
| `operating_load` | Plant condition | `operating_load` | % | Relative duty cycle |

### Physics-Based Feature Engineering (applied consistently in training and inference):
1. `temp_difference` = `process_temperature` - `air_temperature` (critical for Heat Dissipation Failure detection)
2. `power_W` = `torque` × (`rotational_speed` × 2π / 60) (critical for Power Failure detection)
3. `overstrain` = `tool_wear` × `torque` (critical for Overstrain Failure detection)

If incoming telemetry does not contain the required AI4I physical features, the ML service returns `prediction_available: False` rather than silently fabricating a prediction.

---

## 4. Multi-Model AI & Machine Learning Architecture

MachinaGuard integrates three specialized, non-interfering machine learning models:

### Module 1: Machine Failure Prediction
- **Dataset:** UCI AI4I 2020 Predictive Maintenance Dataset (10,000 industrial records).
- **Algorithm:** Random Forest Classifier (`ml/models/predictive_maintenance_rf.joblib`).
- **Input Features (6):** `Type`, `Air temperature [K]`, `Process temperature [K]`, `Rotational speed [rpm]`, `Torque [Nm]`, `Tool wear [min]`.
- **Output:** Failure Probability (0–100%) and Risk Category (`Low`, `Medium`, `High`, `Critical`).
- **Endpoint:** `POST /api/ml/failure/predict`

### Module 2: Operational Anomaly Detection
- **Dataset:** UCI AI4I 2020 Dataset (Trained exclusively on nominal operating records, `Machine failure == 0`).
- **Algorithm:** Isolation Forest (`ml/models/isolation_forest_ai4i.joblib`, 100 estimators).
- **Input Features (6):** Same physical parameters as Module 1.
- **Output:** Label (`Normal` / `Anomaly`) and continuous Anomaly Score.
- **Crucial Rigor:** Anomaly score indicates statistical outlier behavior. *It is not a machine-failure probability.*
- **Endpoint:** `POST /api/ml/anomaly/detect`

### Module 3: Remaining Useful Life (RUL) Prediction
- **Dataset Target:** PHM 2010 CNC Milling Tool Wear dataset (Cutters c1, c4, c6).
- **Algorithm:** Random Forest Regressor (`ml/train_rul.py`).
- **Validation Protocol:** Leave-One-Cutter-Out (train on c1 & c4, evaluate on c6) to strictly eliminate data leakage.
- **Input Features (7 high-frequency signals):**
  - Force RMS: `force_x_rms`, `force_y_rms`, `force_z_rms` [N]
  - Vibration RMS: `vibration_x_rms`, `vibration_y_rms`, `vibration_z_rms` [g]
  - Acoustic Emission RMS: `ae_rms` [V]
- **Output:** Estimated Remaining Machining Cuts (integer cuts, flank wear threshold $VB \ge 0.11$ mm).
- **Honest ML Guarantee:** Synthetic training data is never fabricated. When PHM high-frequency sensor measurements are not available for a machine, the system marks RUL as unavailable rather than outputting invented numbers.
- **Dataset Placement:** Place `phm2010_cut_features.csv` in `ml/data/` and execute `python ml/train_rul.py`.
- **Endpoint:** `POST /api/ml/rul/predict` (returns HTTP 503 with placement instructions if model not yet trained).

---

## 5. Machine Learning & Backend API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | `GET` | Health check, DB connectivity, and models readiness |
| `/api/ml/models/status` | `GET` | Loaded models, feature counts, and pipeline versions |
| `/api/ml/failure/predict` | `POST` | Supervised failure probability prediction (AI4I) |
| `/api/ml/anomaly/detect` | `POST` | Unsupervised isolation forest anomaly detection (AI4I) |
| `/api/ml/rul/predict` | `POST` | Remaining machining cuts prediction (PHM 2010) |
| `/api/machines` | `GET`, `POST` | List and register industrial assets |
| `/api/machines/{id}/latest` | `GET` | Latest telemetry packet and prediction status |
| `/api/machines/{id}/history`| `GET` | Combined sensor history and inference log |
| `/api/telemetry` | `POST` | Ingest external sensor telemetry from `data_generator.py` |
| `/api/notifications` | `GET` | Real alerts feed with triage actions |
| `/api/notifications/{id}/acknowledge` | `POST` | Mark alert as acknowledged |
| `/api/notifications/{id}/resolve` | `POST` | Mark alert as resolved |

---

## 6. Step-by-Step Windows PowerShell Commands

### Terminal 1: Model Training & Evaluation (Run Manually)

```powershell
# 1. Install required Python packages
pip install -r requirements.txt

# 2. Run model training manually (trains Random Forest + XGBoost, saves artifacts to ml/models/)
python ml/train_model.py

# 3. Run model evaluation manually (validates held-out test set & 5 edge-case scenarios)
python ml/evaluate_model.py
```

### Terminal 2: Start FastAPI Backend Server

```powershell
# Starts FastAPI server on http://localhost:8000
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

*Backend Health Check URL:* `http://localhost:8000/api/health`  
*Model Status URL:* `http://localhost:8000/api/model/status`  
*Swagger Documentation:* `http://localhost:8000/docs`

### Terminal 3: Start React/Vite Frontend

```powershell
# Navigate to frontend directory and start Vite dev server
cd frontend
npm install
npm run dev
```

*Website URL:* `http://localhost:5173`

### Terminal 4: Run External Telemetry Generator

Once the backend is up and machines are registered, run the standalone generator:

```powershell
# 1. Standard continuous multi-machine telemetry stream (normal nominal operation)
python data_generator.py

# 2. Fault Injection: Overstrain Failure (OSF)
python data_generator.py --fault osf --interval 2.5

# 3. Fault Injection: Heat Dissipation Failure (HDF)
python data_generator.py --fault hdf --interval 2.5

# 4. Fault Injection: Power Failure (PWF)
python data_generator.py --fault pwf --interval 2.5

# 5. Fault Injection: Tool Wear Failure (TWF)
python data_generator.py --fault twf --interval 2.5

# 6. Fault Injection: Severe Vibration / Bearing Defect
python data_generator.py --fault bearing --interval 2.5

# 7. Gradual tool wear and friction deterioration
python data_generator.py --deteriorate --interval 2.0

# 8. Target a single registered machine
python data_generator.py --target CNC-101 --fault osf
```

---

## 6. End-to-End Demonstration Workflow

1. **Verify Backend:** Open `http://localhost:8000/api/health` in your browser. It should report `{"status": "healthy", "ml_model_loaded": true, "model_name": "RandomForestClassifier"}`.
2. **Open Dashboard:** Navigate to `http://localhost:5173`. Notice the top navbar displays `Model Active: RandomForestClassifier (v1.0.0)` with a green indicator.
3. **Register Machinery:** Go to **Equipment Fleet** (`/machines`) and click **Register New Machine** to add an industrial machine (e.g. `CNC-500`, Type Variant `M`, CNC Milling Center). Notice that registering a machine does **not** generate fake readings.
4. **Start Telemetry Stream:** In a separate terminal, execute:
   ```powershell
   python data_generator.py --count 10 --interval 2.0
   ```
   Watch the live telemetry ingestion table and metric cards on the Dashboard update in real time every 3 seconds.
5. **Inject Fault:** In your generator terminal, run an Overstrain Failure fault:
   ```powershell
   python data_generator.py --target CNC-101 --fault osf --count 5
   ```
6. **Observe Failure Prediction:** The Random Forest model evaluates the high torque (68+ Nm) and tool wear (220+ min), predicting a **94%+ Critical Failure Probability**.
7. **Inspect Alerts:** An automated alarm appears in **Failure Risk Alarms & Corrective Triage** (`/alerts`) with the message:
   `"Critical failure risk (94.0%) predicted. Anomaly: Overstrain Failure (OSF). Recommended action: Immediate spindle shutdown and tool replacement."`
8. **Critical Incident & Automated Maintenance Verification:**
   - In your generator terminal, simulate an Overstrain Failure (OSF) with recovery:
     ```powershell
     python data_generator.py --target CNC-001 --fault osf --recover-after 5 --interval 1.0
     ```
   - Watch the Critical Incident banner appear and open the **Alerts & Incidents** tab (`/alerts`).
   - Click **Record Maintenance Intervention**, enter technician notes (e.g., `Replaced worn tungsten carbide tool insert`), and submit.
   - The status updates to `VERIFICATION_PENDING`.
   - The engine gathers incoming telemetry. After **3 consecutive nominal cycles**, the system automatically verifies recovery, setting status to `RESOLVED` and creating an entry in the **Maintenance History** ledger.

---

## 7. Verification & Automated Test Results

Run the complete multi-suite automated test suite:
```powershell
pytest -p no:xdist
```

Results: **40 passed, 0 failed** across all test suites:
- `backend/test_api.py`: 11 passed
- `backend/test_consistency_and_alerts.py`: 9 passed
- `backend/test_incident_and_verification.py`: 4 passed
- `backend/test_supabase_integration.py`: 7 passed
- `ml/tests/test_ml_models.py`: 9 passed

Frontend production build:
```powershell
cd frontend
npm run build
```
Result: **Exit code 0** (2564 modules transformed, cleanly packaged with Vite in ~1.0s).
