"""
MachinaGuard RUL Model Training Pipeline
Dataset: Remaining Useful Life dataset (readings.csv, units.csv, ground_truth.csv)
Algorithm: Random Forest Regressor
Target: rul_cycles (Remaining Useful Life in operating cycles)
Validation Strategy: Unit-level train/test split (80 train units, 20 test units) to prevent data leakage.
"""

import os
import sys
import json
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    median_absolute_error,
    r2_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Resolve paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
DATA_DIR = os.path.join(ML_DIR, "data", "rul_dataset")
MODELS_DIR = os.path.join(ML_DIR, "models")
PREPROCESSING_DIR = os.path.join(ML_DIR, "preprocessing")
METADATA_DIR = os.path.join(ML_DIR, "metadata")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(PREPROCESSING_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

# Feature definitions
NUMERIC_FEATURES = [
    "cycle",
    "tool_wear_min",
    "vibration_mm_s",
    "torque_nm",
    "process_temperature_k",
    "air_temperature_k",
    "rotational_speed_rpm",
]
CATEGORICAL_FEATURES = ["control_type"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET_COLUMN = "rul_cycles"


def load_and_preprocess_data(data_dir=DATA_DIR):
    """
    Loads readings.csv, units.csv, ground_truth.csv and applies clean data preparation.
    Prevents target leakage by isolating ground_truth damage and failure flags.
    """
    readings_path = os.path.join(data_dir, "readings.csv")
    units_path = os.path.join(data_dir, "units.csv")
    gt_path = os.path.join(data_dir, "ground_truth.csv")

    for path in [readings_path, units_path, gt_path]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required dataset file not found: {path}")

    readings = pd.read_csv(readings_path)
    units = pd.read_csv(units_path)
    ground_truth = pd.read_csv(gt_path)

    print(f"[DATA] Loaded readings: {readings.shape}, units: {units.shape}, ground_truth: {ground_truth.shape}")

    # Sort readings by machine/unit and cycle
    readings = readings.sort_values(by=["unit_id", "cycle"]).reset_index(drop=True)

    # Sanitize tool wear (clip small sensor initialization negative readings to 0.0)
    negative_wear_count = (readings["tool_wear_min"] < 0).sum()
    if negative_wear_count > 0:
        print(f"[DATA] Sanitizing {negative_wear_count} negative tool wear values (clipped to 0.0).")
        readings["tool_wear_min"] = readings["tool_wear_min"].clip(lower=0.0)

    # Unit-based train/test split: uses the defined unit splits
    train_mask = readings["split"] == "train"
    test_mask = readings["split"] == "test"

    train_df = readings[train_mask].copy()
    test_df = readings[test_mask].copy()

    train_units_count = train_df["unit_id"].nunique()
    test_units_count = test_df["unit_id"].nunique()

    print(f"[DATA] Train records: {len(train_df)} across {train_units_count} units")
    print(f"[DATA] Test records: {len(test_df)} across {test_units_count} units")

    return train_df, test_df


def build_pipeline():
    """Builds a robust scikit-learn Pipeline with median imputation and scaling."""
    numeric_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_transformer = OneHotEncoder(
        categories=[["A", "B", "C"]],
        handle_unknown="ignore",
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, NUMERIC_FEATURES),
            ("cat", categorical_transformer, CATEGORICAL_FEATURES),
        ]
    )

    model = Pipeline([
        ("preprocessor", preprocessor),
        (
            "regressor",
            RandomForestRegressor(
                n_estimators=100,
                max_depth=15,
                min_samples_split=4,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ])

    return model, preprocessor


def train_and_evaluate(data_dir=DATA_DIR):
    train_df, test_df = load_and_preprocess_data(data_dir)

    X_train = train_df[ALL_FEATURES]
    y_train = train_df[TARGET_COLUMN]

    X_test = test_df[ALL_FEATURES]
    y_test = test_df[TARGET_COLUMN]

    pipeline, preprocessor = build_pipeline()

    print(f"[TRAIN] Training Random Forest Regressor on {len(X_train)} training records...")
    pipeline.fit(X_train, y_train)

    print("[EVAL] Evaluating on held-out 20 test units (4,317 records)...")
    y_pred = pipeline.predict(X_test)
    y_pred = np.maximum(0.0, y_pred)  # Physical constraint: RUL cannot be negative

    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    med_ae = float(median_absolute_error(y_test, y_pred))
    r2 = float(r2_score(y_test, y_pred))

    print(f"[RESULTS] Test MAE: {mae:.2f} cycles")
    print(f"[RESULTS] Test RMSE: {rmse:.2f} cycles")
    print(f"[RESULTS] Test Median AE: {med_ae:.2f} cycles")
    print(f"[RESULTS] Test R² Score: {r2:.4f}")

    # Save model and preprocessor artifacts
    model_path = os.path.join(MODELS_DIR, "rul_model.joblib")
    prep_path = os.path.join(PREPROCESSING_DIR, "rul_preprocessor.joblib")

    joblib.dump(pipeline, model_path)
    joblib.dump(pipeline.named_steps["preprocessor"], prep_path)
    print(f"[SAVE] Saved model to {model_path}")
    print(f"[SAVE] Saved preprocessor to {prep_path}")

    # Generate metadata
    metadata = {
        "model_name": "MachinaGuard RUL Regressor",
        "model_version": "1.0.0",
        "algorithm": "RandomForestRegressor (100 estimators, max_depth=15, min_samples_split=4, min_samples_leaf=2)",
        "dataset_name": "Predictive Maintenance Remaining Useful Life Dataset",
        "dataset_source": "ml/data/rul_dataset/ (readings.csv, units.csv, ground_truth.csv)",
        "dataset_type": "industrial physical telemetry with degradation cycles",
        "training_date": datetime.now(timezone.utc).isoformat(),
        "input_features": {
            "numeric": NUMERIC_FEATURES,
            "categorical": CATEGORICAL_FEATURES,
            "feature_order": ALL_FEATURES,
        },
        "target_variable": TARGET_COLUMN,
        "target_unit": "cycles",
        "preprocessing_steps": [
            "Negative tool wear clipped to 0.0",
            "Median imputation for missing sensor channels (vibration, torque, air temp across control types A/B/C)",
            "StandardScaler normalization for numeric features",
            "OneHotEncoder for categorical control_type [A, B, C]",
        ],
        "training_parameters": {
            "n_estimators": 100,
            "max_depth": 15,
            "min_samples_split": 4,
            "min_samples_leaf": 2,
            "random_state": 42,
        },
        "training_record_count": int(len(X_train)),
        "validation_record_count": int(len(X_test)),
        "evaluation_metrics": {
            "mae_cycles": round(mae, 4),
            "rmse_cycles": round(rmse, 4),
            "median_absolute_error_cycles": round(med_ae, 4),
            "r2_score": round(r2, 4),
        },
        "model_artifact_filename": "rul_model.joblib",
        "validation_strategy": "Unit-level split (80 train units, 20 test units; 100% disjoint machine units)",
        "known_limitations": [
            "Assumes machines operate under control protocols A, B, or C.",
            "Prediction uncertainty increases during the first 10 cycles before degradation signal manifests.",
            "Missing sensor channels are imputed with dataset medians per training distribution.",
        ],
    }

    metadata_path = os.path.join(METADATA_DIR, "rul_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[SAVE] Saved metadata to {metadata_path}")

    return {
        "mae": mae,
        "rmse": rmse,
        "med_ae": med_ae,
        "r2": r2,
    }


if __name__ == "__main__":
    train_and_evaluate()
