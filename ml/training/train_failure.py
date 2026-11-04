"""
MachinaGuard Machine Failure Prediction Model Training Pipeline
Dataset: UCI AI4I 2020 Predictive Maintenance Dataset (10,000 samples)
Algorithm: Random Forest Classifier with Balanced Class Weighting
Target: Machine failure (0 = Nominal, 1 = Failure)
Validation Strategy: Stratified 80/20 train/test split (random_state=42)
"""

import os
import sys
import json
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Resolve paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
DATA_PATH = os.path.join(ML_DIR, "data", "ai4i2020.csv")
TEST_DATA_PATH = os.path.join(ML_DIR, "data", "test_data.csv")
MODELS_DIR = os.path.join(ML_DIR, "models")
PREPROCESSING_DIR = os.path.join(ML_DIR, "preprocessing")
METADATA_DIR = os.path.join(ML_DIR, "metadata")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(PREPROCESSING_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

# Feature definitions
FEATURE_CATEGORICAL = ["Type"]
FEATURE_NUMERIC = [
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
]
ALL_FEATURES = FEATURE_CATEGORICAL + FEATURE_NUMERIC
TARGET_COLUMN = "Machine failure"


def load_data(data_path=DATA_PATH):
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"AI4I 2020 dataset not found at: {data_path}")
    df = pd.read_csv(data_path)
    return df


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
            "classifier",
            RandomForestClassifier(
                n_estimators=100,
                max_depth=12,
                min_samples_split=4,
                min_samples_leaf=2,
                random_state=42,
                class_weight="balanced",
                n_jobs=-1,
            ),
        ),
    ])

    return model, preprocessor


def train_and_evaluate(data_path=DATA_PATH):
    df = load_data(data_path)

    X = df[ALL_FEATURES]
    y = df[TARGET_COLUMN]

    # Stratified 80/20 train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # Persist held-out test data for reproducible evaluation
    test_df = X_test.copy()
    test_df[TARGET_COLUMN] = y_test
    test_df.to_csv(TEST_DATA_PATH, index=False)

    pipeline, preprocessor = build_pipeline()

    print(f"[TRAIN] Fitting Failure Classifier on {len(X_train)} samples...")
    pipeline.fit(X_train, y_train)

    print(f"[EVAL] Evaluating on {len(X_test)} held-out test samples...")
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred))
    rec = float(recall_score(y_test, y_pred))
    f1 = float(f1_score(y_test, y_pred))
    roc_auc = float(roc_auc_score(y_test, y_proba))
    pr_auc = float(average_precision_score(y_test, y_proba))
    cm = confusion_matrix(y_test, y_pred).tolist()

    print(f"[RESULTS] Test Accuracy:  {acc:.4f}")
    print(f"[RESULTS] Test Precision: {prec:.4f}")
    print(f"[RESULTS] Test Recall:    {rec:.4f} (Priority metric: identifies real machine failures)")
    print(f"[RESULTS] Test F1-Score:  {f1:.4f}")
    print(f"[RESULTS] Test ROC-AUC:   {roc_auc:.4f}")
    print(f"[RESULTS] Test PR-AUC:    {pr_auc:.4f}")
    print(f"[RESULTS] Confusion Matrix: TN={cm[0][0]}, FP={cm[0][1]}, FN={cm[1][0]}, TP={cm[1][1]}")

    # Save model artifacts (save both failure_model.joblib and maintain predictive_maintenance_rf.joblib for compatibility)
    primary_model_path = os.path.join(MODELS_DIR, "failure_model.joblib")
    compat_model_path = os.path.join(MODELS_DIR, "predictive_maintenance_rf.joblib")
    prep_path = os.path.join(PREPROCESSING_DIR, "failure_preprocessor.joblib")

    joblib.dump(pipeline, primary_model_path)
    joblib.dump(pipeline, compat_model_path)
    joblib.dump(pipeline.named_steps["preprocessor"], prep_path)
    print(f"[SAVE] Saved failure model to {primary_model_path}")
    print(f"[SAVE] Saved preprocessor to {prep_path}")

    # Save model metadata
    metadata = {
        "model_name": "MachinaGuard Machine Failure Classifier",
        "model_version": "1.0.0",
        "algorithm": "RandomForestClassifier (100 estimators, max_depth=12, class_weight='balanced')",
        "dataset_name": "UCI AI4I 2020 Predictive Maintenance Dataset",
        "dataset_source": "ml/data/ai4i2020.csv",
        "dataset_type": "real industrial manufacturing dataset (10,000 samples)",
        "training_date": datetime.now(timezone.utc).isoformat(),
        "input_features": {
            "categorical": FEATURE_CATEGORICAL,
            "numeric": FEATURE_NUMERIC,
            "feature_order": ALL_FEATURES,
        },
        "target_variable": TARGET_COLUMN,
        "target_mapping": {"0": "Nominal / Healthy", "1": "Machine Failure"},
        "preprocessing_steps": [
            "StandardScaler normalization on 5 continuous sensor parameters",
            "OneHotEncoder on Type categorical [L, M, H]",
        ],
        "training_parameters": {
            "n_estimators": 100,
            "max_depth": 12,
            "min_samples_split": 4,
            "min_samples_leaf": 2,
            "class_weight": "balanced",
            "random_state": 42,
        },
        "training_record_count": int(len(X_train)),
        "validation_record_count": int(len(X_test)),
        "evaluation_metrics": {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "confusion_matrix": {
                "true_negative": cm[0][0],
                "false_positive": cm[0][1],
                "false_negative": cm[1][0],
                "true_positive": cm[1][1],
            },
        },
        "model_artifact_filename": "failure_model.joblib",
        "prediction_threshold": 0.5,
        "risk_categorization_thresholds": {
            "Low": "0.0 - 0.29 (Nominal)",
            "Medium": "0.30 - 0.59 (Elevated)",
            "High": "0.60 - 0.79 (Warning)",
            "Critical": "0.80 - 1.00 (Imminent Action Required)",
        },
        "validation_strategy": "Stratified 80/20 train/test split on machine failure class",
        "known_limitations": [
            "Trained on AI4I 2020 distribution; physical extremes outside dataset bounds may need domain clamping.",
            "Balanced class weights prioritize recall over precision to minimize costly missed failures.",
        ],
    }

    metadata_path = os.path.join(METADATA_DIR, "failure_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[SAVE] Saved failure metadata to {metadata_path}")

    return metadata


if __name__ == "__main__":
    train_and_evaluate()
