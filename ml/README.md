# MachinaGuard Machine Learning Architecture & Modules

This directory contains the machine learning pipelines, models, evaluations, and inference services for the MachinaGuard Predictive Maintenance Platform.

---

## 1. Directory Structure

```text
ml/
├── data/
│   ├── ai4i2020.csv             # UCI AI4I 2020 predictive maintenance dataset (10,000 samples)
│   ├── test_data.csv            # Stratified 20% test partition for failure model evaluation
│   └── rul_dataset/
│       ├── readings.csv         # 23,118 sensor cycle readings across 100 industrial units
│       ├── units.csv            # Total lifetime cycles and failure modes per unit
│       └── ground_truth.csv     # Cumulative damage trajectory per cycle
│
├── models/
│   ├── failure_model.joblib     # RandomForestClassifier for binary failure probability
│   ├── anomaly_model.joblib     # IsolationForest for unsupervised outlier detection
│   └── rul_model.joblib         # RandomForestRegressor for remaining cycles estimation
│
├── preprocessing/
│   ├── failure_preprocessor.joblib  # ColumnTransformer for failure classification
│   ├── anomaly_preprocessor.joblib  # ColumnTransformer for anomaly detection
│   └── rul_preprocessor.joblib      # ColumnTransformer with median imputer & scaler
│
├── training/
│   ├── train_failure.py         # Trains Failure Classifier (Stratified 80/20 AI4I split)
│   ├── train_anomaly.py         # Trains Isolation Forest on normal operational records (y=0)
│   └── train_rul.py             # Trains RUL Regressor on 80 train units (disjoint from 20 test units)
│
├── evaluation/
│   ├── evaluate_failure.py      # Computes accuracy, recall, precision, F1, ROC-AUC, confusion matrix
│   ├── evaluate_anomaly.py      # Evaluates score distributions, contamination cutoffs, outlier rates
│   ├── evaluate_rul.py          # Computes MAE, RMSE, R², median AE, per-unit metrics
│   └── reports/
│       ├── failure_evaluation.json  / .txt
│       ├── failure_confusion_matrix.png
│       ├── failure_roc_curve.png
│       ├── anomaly_evaluation.json  / .txt
│       ├── anomaly_score_distribution.png
│       ├── rul_evaluation.json      / .txt
│       ├── rul_actual_vs_predicted.png
│       └── rul_residuals.png
│
├── metadata/
│   ├── failure_metadata.json    # Verified metadata, hyperparameters, metrics & limitations
│   ├── anomaly_metadata.json    # Contamination threshold, score interpretation & training bounds
│   └── rul_metadata.json        # Unit validation split, target cycle semantics & feature list
│
├── inference/
│   └── prediction_service.py    # Reusable, singleton prediction services for real-time inference
│
├── tests/
│   └── test_ml_models.py        # Automated test suite validating all 3 models & edge cases
│
├── requirements.txt             # Python ML dependencies
└── README.md                    # Architecture and documentation
```

---

## 2. Model Overview & Input Schemas

| Module | Model Name | Algorithm | Training Dataset | Input Features | Output Target |
|---|---|---|---|---|---|
| **Module 1** | Machine Failure Classifier | `RandomForestClassifier` (100 trees, max_depth=12, balanced) | UCI AI4I 2020 (8,000 train records) | `Type`, `Air temperature [K]`, `Process temperature [K]`, `Rotational speed [rpm]`, `Torque [Nm]`, `Tool wear [min]` | Failure Probability (0-100%) & Risk Category (Low, Medium, High, Critical) |
| **Module 2** | Operational Anomaly Detector | `IsolationForest` (300 trees, contamination=0.02) | UCI AI4I 2020 Nominal (9,661 normal records) | Same 6 physical sensor features as Module 1 | Normal / Anomaly status & Decision Score (scores < 0.0 indicate outliers) |
| **Module 3** | Remaining Useful Life Regressor | `RandomForestRegressor` (100 trees, max_depth=15) | RUL Dataset (18,801 train records across 80 units) | `cycle`, `tool_wear_min`, `vibration_mm_s`, `torque_nm`, `process_temperature_k`, `air_temperature_k`, `rotational_speed_rpm`, `control_type` | Estimated Remaining Life in **cycles** |

---

## 3. Strict Methodological Guarantees

1. **Zero Data Leakage:**
   - The RUL regressor is split **by machine unit ID** (80 train units, 20 test units). Individual rows from the same machine are never randomly distributed across train and test sets.
   - Ground truth cumulative damage and failure indicators are strictly excluded from input features.
2. **Anomaly Score != Failure Probability:**
   - The Isolation Forest measures statistical isolation in high-dimensional sensor space. Negative decision scores indicate unusual operational points, NOT a failure probability percentage.
3. **Reproducibility:**
   - All random states are fixed (`random_state=42`).
   - Every model has an independent evaluation script generating reproducible text, JSON, and graphical reports.

---

## 4. Execution Commands

### Train all models:
```powershell
python ml/training/train_failure.py
python ml/training/train_anomaly.py
python ml/training/train_rul.py
```

### Run independent evaluations:
```powershell
python ml/evaluation/evaluate_failure.py
python ml/evaluation/evaluate_anomaly.py
python ml/evaluation/evaluate_rul.py
```

### Run automated ML test suite:
```powershell
python -m pytest ml/tests/test_ml_models.py -v
```
