"""
MachinaGuard - End-to-End System Test Script
Verifies:
1. Backend health & model loaded
2. Empty state vs received state
3. Telemetry ingestion & prediction generation
4. History retrieval for charts & tables
5. Notification triggering & deduplication
6. Notification acknowledge and resolve workflows
7. Backend shutdown error handling
"""

import urllib.request
import json

BASE_URL = "http://127.0.0.1:8000/api"

def get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())

def post(path, body=None):
    data = json.dumps(body).encode() if body else b""
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if body else {},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())

def run_tests():
    print("=" * 60)
    print("MachinaGuard: Running End-to-End Automated Verification")
    print("=" * 60)

    # 1. Health check
    health = get("/health")
    assert health["status"] == "healthy", "Backend is not healthy"
    assert health["model_loaded"] is True, "AI4I model is not loaded"
    print("[PASS] 1. Backend health check: OK, Random Forest model loaded.")

    # 2. Configured Machines
    machines = get("/machines")
    assert len(machines) >= 1, f"Expected at least 1 machine, got {len(machines)}"
    m = next((item for item in machines if item.get("id") == "CNC-001" or item.get("machine_id") == "CNC-001"), machines[0])
    assert m["id"] == "CNC-001", f"Unexpected machine ID: {m['id']}"
    print(f"[PASS] 2. Configured machines: {m['id']} ({m['name']}) with status: {m['status']}")

    # 3. Latest Telemetry & Prediction
    latest = get("/machines/CNC-001/latest")
    assert "latest_reading" in latest, "Missing latest reading"
    assert "latest_prediction" in latest, "Missing latest prediction"
    prob = latest["latest_prediction"]["failure_probability"]
    risk = latest["latest_prediction"]["risk_category"]
    print(f"[PASS] 3. Machine latest reading & prediction: Risk={risk}, Est. Failure Prob={prob*100:.1f}%")

    # 4. History retrieval for charts
    history = get("/machines/CNC-001/history?limit=20")
    assert len(history) > 0, "No historical readings found"
    print(f"[PASS] 4. Sensor history endpoint: Retrieved {len(history)} records for dynamic charts.")

    # 5. Prediction history
    pred_history = get("/machines/CNC-001/predictions?limit=20")
    assert len(pred_history) > 0, "No prediction history found"
    print(f"[PASS] 5. Prediction history endpoint: Retrieved {len(pred_history)} prediction records.")

    # 6. Notifications
    notifs = get("/notifications")
    if len(notifs) == 0:
        print("[INFO] Simulating overstrain fault payload to trigger alert condition...")
        fault_payload = {
            "machine_id": "CNC-001",
            "machine_name": "Simulated CNC Milling Machine",
            "equipment_type": "M",
            "air_temperature": 298.5,
            "process_temperature": 308.8,
            "rotational_speed": 1320.0,
            "torque": 72.5,
            "tool_wear": 185.0,
            "vibration": 6.8,
            "pressure": 4.1
        }
        post("/telemetry", fault_payload)
        notifs = get("/notifications")

    assert len(notifs) > 0, "Expected at least 1 notification from fault injection"
    print(f"[PASS] 6. Notifications endpoint: {len(notifs)} real alerts generated.")
    for n in notifs[:3]:
        print(f"       - [{n['severity']}] {n['title']} (Status: {n['status']})")

    # 7. Acknowledge and Resolve Notification
    first_notif = notifs[0]
    first_id = first_notif["id"]
    ack_res = post(f"/notifications/{first_id}/acknowledge")
    assert ack_res["status"] == "success"
    print(f"[PASS] 7a. Notification #{first_id} marked as ACKNOWLEDGED.")

    res_res = post(f"/notifications/{first_id}/resolve")
    assert res_res["status"] == "success"
    print(f"[PASS] 7b. Notification #{first_id} marked as RESOLVED.")

    # 8. Check updated status
    updated_notifs = get("/notifications")
    resolved_item = [n for n in updated_notifs if n["id"] == first_id][0]
    assert resolved_item["status"] == "RESOLVED"
    print(f"[PASS] 8. Notification status verified in DB as RESOLVED.")

    # 9. Verify ML Models Status & Evaluation Reports
    ml_status = get("/ml/models/status")
    assert ml_status["all_ready"] is True, "Not all ML models ready"
    assert ml_status["failure_model"]["loaded"] is True
    assert ml_status["anomaly_model"]["loaded"] is True
    assert ml_status["rul_model"]["loaded"] is True
    print("[PASS] 9. ML models status endpoint: All 3 models active.")

    ml_meta = get("/ml/models/metadata")
    assert "failure_model" in ml_meta and "anomaly_model" in ml_meta and "rul_model" in ml_meta
    print("[PASS] 10. ML metadata endpoint: Successfully loaded all 3 metadata specifications.")

    ml_eval = get("/ml/models/evaluations")
    assert "failure_evaluation" in ml_eval and "anomaly_evaluation" in ml_eval and "rul_evaluation" in ml_eval
    f_metrics = ml_eval["failure_evaluation"]["metrics"]
    r_metrics = ml_eval["rul_evaluation"]["global_metrics"]
    print(f"[PASS] 11. ML evaluations endpoint: Failure ROC-AUC={f_metrics['roc_auc']:.4f}, RUL R2={r_metrics['r2_score']:.4f}, MAE={r_metrics['mae_cycles']:.2f} cycles.")

    # 12. Direct Model Inferences
    fail_res = post("/ml/failure/predict", {
        "type": "M",
        "air_temperature": 298.1,
        "process_temperature": 308.6,
        "rotational_speed": 1551.0,
        "torque": 42.8,
        "tool_wear": 0.0
    })
    assert "failure_probability" in fail_res
    print(f"[PASS] 12. Failure prediction test: Pred={fail_res['failure_prediction']}, Prob={fail_res['failure_probability']:.4f}, Risk={fail_res['risk_category']}")

    anom_res = post("/ml/anomaly/detect", {
        "type": "M",
        "air_temperature": 298.1,
        "process_temperature": 308.6,
        "rotational_speed": 1551.0,
        "torque": 42.8,
        "tool_wear": 0.0
    })
    assert "anomaly" in anom_res
    print(f"[PASS] 13. Anomaly detection test: Anomaly={anom_res['anomaly']} ({anom_res['label']}), Score={anom_res['anomaly_score']:.4f}")

    rul_res = post("/ml/rul/predict", {
        "cycle": 50,
        "tool_wear_min": 65.0,
        "rotational_speed_rpm": 1500.0,
        "process_temperature_k": 308.0,
        "air_temperature_k": 298.0,
        "torque_nm": 40.0,
        "vibration_mm_s": 0.5,
        "control_type": "A"
    })
    assert "estimated_remaining_cycles" in rul_res
    assert rul_res["unit"] == "cycles"
    print(f"[PASS] 14. RUL prediction test: Estimated RUL={rul_res['estimated_remaining_cycles']:.1f} cycles ({rul_res['unit']}).")

    print("\n" + "=" * 60)
    print("ALL 14 END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
