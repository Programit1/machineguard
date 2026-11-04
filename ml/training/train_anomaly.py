"""
MachinaGuard Operational Anomaly Detection Pipeline
Dataset: UCI AI4I 2020 Predictive Maintenance Dataset
Training Scope: Exclusively nominal operational records (Machine failure == 0)
Algorithm: Isolation Forest (300 estimators, contamination=0.02)
Score Interpretation: Unsupervised decision_function score. Values < 0 indicate anomalous / outlier behavior.
Crucial Rigor: Anomaly score is NOT failure probability.
"""

import os
import sys
import json
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Resolve paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
DATA_PATH = os.path.join(ML_DIR, "data", "ai4i2020.csv")
MODELS_DIR = os.path.join(ML_DIR, "models")
PREPROCESSING_DIR = os.path.join(ML_DIR, "preprocessing")
METADATA_DIR = os.path.join(ML_DIR, "metadata")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(PREPROCESSING_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

FEATURE_CATEGORICAL = ["Type"]
FEATURE_NUMERIC = [
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
]
ALL_FEATURES = FEATURE_CATEGORICAL + FEATURE_NUMERIC


def build_pipeline():
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), FEATURE_NUMERIC),
            (
                "cat",
                OneHotEncoder(categories=[["L", "M", "H"]], handle_unknown="ignore"),
                FEATURE_CATEGORICAL,
            ),
        ]
    )

    model = Pipeline([
        ("preprocessor", preprocessor),
        (
            "detector",
            IsolationForest(
                n_estimators=300,
                contamination=0.02,
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ])

    return model, preprocessor


def train_and_evaluate(data_path=DATA_PATH):
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Dataset not found at: {data_path}")

    df = pd.read_csv(data_path)
    total_samples = len(df)

    # Train ONLY on nominal operational records (Machine failure == 0)
    normal_df = df[df["Machine failure"] == 0].copy()
    fit_samples = len(normal_df)

    X_train = normal_df[ALL_FEATURES]

    pipeline, preprocessor = build_pipeline()

    print(f"[TRAIN] Fitting Isolation Forest on {fit_samples} nominal operating records (contamination=0.02)...")
    pipeline.fit(X_train)

    # Evaluate decision scores across both normal records and failure records
    X_all = df[ALL_FEATURES]
    detector = pipeline.named_steps["detector"]
    prep = pipeline.named_steps["preprocessor"]

    transformed_all = prep.transform(X_all)
    scores_all = detector.decision_function(transformed_all)
    preds_all = detector.predict(transformed_all)  # +1 = normal, -1 = anomaly

    normal_scores = scores_all[df["Machine failure"] == 0]
    failure_scores = scores_all[df["Machine failure"] == 1]

    anomaly_count = (preds_all == -1).sum()
    normal_detected = (preds_all[df["Machine failure"] == 0] == 1).sum()
    failures_detected = (preds_all[df["Machine failure"] == 1] == -1).sum()

    print(f"[RESULTS] Total dataset samples: {total_samples}")
    print(f"[RESULTS] Anomaly flags raised: {anomaly_count} / {total_samples} ({anomaly_count/total_samples*100:.2f}%)")
    print(f"[RESULTS] Normal records classified as normal: {normal_detected} / {len(normal_scores)} ({normal_detected/len(normal_scores)*100:.2f}%)")
    print(f"[RESULTS] Failures exhibiting anomalous outlier dynamics: {failures_detected} / {len(failure_scores)} ({failures_detected/len(failure_scores)*100:.2f}%)")
    print(f"[RESULTS] Normal score stats:  mean={normal_scores.mean():.4f}, std={normal_scores.std():.4f}, min={normal_scores.min():.4f}, max={normal_scores.max():.4f}")
    print(f"[RESULTS] Failure score stats: mean={failure_scores.mean():.4f}, std={failure_scores.std():.4f}, min={failure_scores.min():.4f}, max={failure_scores.max():.4f}")

    # Save artifacts
    primary_model_path = os.path.join(MODELS_DIR, "anomaly_model.joblib")
    compat_model_path = os.path.join(MODELS_DIR, "isolation_forest_ai4i.joblib")
    prep_path = os.path.join(PREPROCESSING_DIR, "anomaly_preprocessor.joblib")

    joblib.dump(pipeline, primary_model_path)
    joblib.dump(pipeline, compat_model_path)
    joblib.dump(pipeline.named_steps["preprocessor"], prep_path)
    print(f"[SAVE] Saved anomaly model to {primary_model_path}")
    print(f"[SAVE] Saved preprocessor to {prep_path}")

    # Save metadata
    metadata = {
        "model_name": "MachinaGuard Operational Anomaly Detector",
        "model_version": "1.0.0",
        "algorithm": "IsolationForest (300 estimators, contamination=0.02)",
        "dataset_name": "UCI AI4I 2020 Predictive Maintenance Dataset",
        "dataset_source": "ml/data/ai4i2020.csv",
        "dataset_type": "nominal operational records only (Machine failure == 0)",
        "training_date": datetime.now(timezone.utc).isoformat(),
        "input_features": {
            "categorical": FEATURE_CATEGORICAL,
            "numeric": FEATURE_NUMERIC,
            "feature_order": ALL_FEATURES,
        },
        "target_variable": "unsupervised outlier / anomaly flag",
        "decision_threshold": 0.0,
        "contamination": 0.02,
        "preprocessing_steps": [
            "StandardScaler normalization on numeric features",
            "OneHotEncoder on Type categorical [L, M, H]",
        ],
        "training_parameters": {
            "n_estimators": 300,
            "contamination": 0.02,
            "random_state": 42,
        },
        "training_record_count": int(fit_samples),
        "validation_record_count": int(total_samples),
        "evaluation_metrics": {
            "total_samples_evaluated": int(total_samples),
            "total_anomalies_flagged": int(anomaly_count),
            "nominal_detection_rate": round(float(normal_detected / len(normal_scores)), 4),
            "failure_overlap_rate": round(float(failures_detected / len(failure_scores)), 4),
            "normal_score_mean": round(float(normal_scores.mean()), 4),
            "normal_score_std": round(float(normal_scores.std()), 4),
            "failure_score_mean": round(float(failure_scores.mean()), 4),
            "failure_score_std": round(float(failure_scores.std()), 4),
        },
        "model_artifact_filename": "anomaly_model.joblib",
        "validation_strategy": "Unsupervised distribution evaluation on normal baseline vs. known failure records",
        "interpretation": "Decision score < 0 indicates anomalous outlier behavior. Anomaly score is an unsupervised distance measure, NOT a machine-failure probability.",
        "known_limitations": [
            "Detects geometric anomalies in feature space; physical failures with nominal signatures (e.g. subtle heat dissipation) may not appear anomalous.",
            "Contamination parameter set to 0.02 based on expected nominal outlier tolerance.",
        ],
    }

    metadata_path = os.path.join(METADATA_DIR, "anomaly_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[SAVE] Saved anomaly metadata to {metadata_path}")

    return metadata


if __name__ == "__main__":
    train_and_evaluate()
