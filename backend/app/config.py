import os
from pathlib import Path

# Load local environment variables if python-dotenv is present
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
ML_DIR = Path(os.getenv("ML_DIR", str(BASE_DIR.parent / "ml")))

import re
import urllib.parse

# Database configuration: support SQLite locally and Supabase PostgreSQL in the cloud
RAW_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'maintenance.db'}")

def normalize_database_url(url: str) -> str:
    if not url:
        return url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    # Auto-encode passwords with special characters (e.g. '@' inside the password)
    match = re.match(r'^(postgresql://[^:]+):(.*)@([^@/]+(?::\d+)?(?:/.*)?)$', url)
    if match:
        prefix, raw_pass, host_part = match.groups()
        if '@' in raw_pass or '%' not in raw_pass:
            encoded_pass = urllib.parse.quote_plus(urllib.parse.unquote_plus(raw_pass))
            return f'{prefix}:{encoded_pass}@{host_part}'
    return url

DATABASE_URL = normalize_database_url(RAW_DATABASE_URL)

# CORS Origins for Cloud Deployment (e.g. Vercel dashboard and local development)
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")
if ALLOWED_ORIGINS_RAW.strip() == "*":
    ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]


def _resolve_model_path(relative_name: str, fallback_name: str) -> str:
    candidates = [
        ML_DIR / "models" / relative_name,
        ML_DIR / "models" / fallback_name,
        ML_DIR / fallback_name,
        BASE_DIR.parent / "ml" / "models" / relative_name,
        BASE_DIR.parent / "ml" / "models" / fallback_name,
        BASE_DIR / "ml" / "models" / relative_name,
        BASE_DIR / "ml" / "models" / fallback_name,
        BASE_DIR / "models" / relative_name,
        BASE_DIR / "models" / fallback_name,
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return str(ML_DIR / "models" / relative_name)


def _resolve_file_path(subfolder: str, filename: str, fallback_filename: str = None) -> str:
    candidates = [
        ML_DIR / subfolder / filename,
        BASE_DIR.parent / "ml" / subfolder / filename,
        BASE_DIR / "ml" / subfolder / filename,
        BASE_DIR / subfolder / filename,
    ]
    if fallback_filename:
        candidates.extend([
            ML_DIR / "models" / fallback_filename,
            BASE_DIR.parent / "ml" / "models" / fallback_filename,
            BASE_DIR / "ml" / "models" / fallback_filename,
            BASE_DIR / "models" / fallback_filename,
        ])
    for c in candidates:
        if c.exists():
            return str(c)
    return str(ML_DIR / subfolder / filename)


# Module 1: AI4I 2020 Random Forest Failure Classifier
FAILURE_MODEL_PATH = os.getenv(
    "FAILURE_MODEL_PATH",
    _resolve_model_path("failure_model.joblib", "predictive_maintenance_rf.joblib")
)
FAILURE_METADATA_PATH = _resolve_file_path("metadata", "failure_metadata.json", "metadata.json")

# Module 2: AI4I 2020 Isolation Forest Anomaly Detector
ANOMALY_MODEL_PATH = os.getenv(
    "ANOMALY_MODEL_PATH",
    _resolve_model_path("anomaly_model.joblib", "isolation_forest_ai4i.joblib")
)
ANOMALY_METADATA_PATH = _resolve_file_path("metadata", "anomaly_metadata.json", "anomaly_metadata.json")

# Module 3: Remaining Useful Life (RUL) Regressor
RUL_MODEL_PATH = os.getenv(
    "RUL_MODEL_PATH",
    _resolve_model_path("rul_model.joblib", "rul_phm2010_rf.joblib")
)
RUL_METADATA_PATH = _resolve_file_path("metadata", "rul_metadata.json", "rul_phm2010_rf_metrics.json")

# Evaluation Reports
FAILURE_REPORT_PATH = _resolve_file_path("evaluation/reports", "failure_evaluation.json")
ANOMALY_REPORT_PATH = _resolve_file_path("evaluation/reports", "anomaly_evaluation.json")
RUL_REPORT_PATH = _resolve_file_path("evaluation/reports", "rul_evaluation.json")

# Legacy compatibility
MODEL_PATH = FAILURE_MODEL_PATH
METADATA_PATH = FAILURE_METADATA_PATH

# Telemetry freshness threshold for Online / Offline status
OFFLINE_THRESHOLD_SECONDS = int(os.getenv("OFFLINE_THRESHOLD_SECONDS", "45"))

# Alert threshold: Failure probability percentage (0-100) above which an alert is automatically raised
ALERT_RISK_THRESHOLD = float(os.getenv("ALERT_RISK_THRESHOLD", "60.0"))

# Anomaly detection decision threshold (negative scores indicate outliers in Isolation Forest)
ANOMALY_ALERT_SCORE_THRESHOLD = float(os.getenv("ANOMALY_ALERT_SCORE_THRESHOLD", "0.0"))
