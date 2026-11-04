"""
AI-Driven Predictive Maintenance - Standalone Industrial Telemetry Generator
Simulates physics-coupled machinery telemetry compliant with the UCI AI4I 2020 dataset
and condition monitoring parameters. Transmits data via HTTP POST to FastAPI backend.
"""

import os
import sys
import time
import math
import json
import random
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import requests

# Reconfigure stdout for UTF-8 on Windows consoles to cleanly print °C and symbols
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load local environment configuration (.env)
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

DEFAULT_API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/api")
DEFAULT_INTERVAL = float(os.getenv("INTERVAL", "1.0"))


class IndustrialMachineSimulator:
    def __init__(self, machine_id: str, machine_type: str = "CNC Mill", type_variant: str = "M"):
        self.machine_id = machine_id
        self.machine_type = machine_type
        self.type_variant = type_variant.upper() if type_variant in ["L", "M", "H"] else "M"
        
        # Operational cycle counter & physical state
        self.cycle = random.randint(15, 60)
        self.tool_wear_min = random.uniform(15.0, 75.0)
        self.accumulated_hours = random.uniform(80.0, 600.0)
        self.fault_mode: Optional[str] = None
        self.fault_severity: float = 0.0

        # Physical baselines configured by machine equipment type
        self.base_air_temp = 298.15 + random.uniform(-1.0, 2.5) # ~25 - 28.5 °C
        m_lower = machine_type.lower()
        if "press" in m_lower:
            # Hydraulic Press: High pressing torque, slower cycle rpm, elevated hydraulic pressure
            self.base_speed = 1220.0 + random.uniform(-30.0, 30.0)
            self.base_torque = 52.0 + random.uniform(-3.0, 3.0)
            self.base_pressure = 6.8 + random.uniform(-0.3, 0.3)
            self.base_vibe = 1.8 + random.uniform(-0.2, 0.3)
        elif "pump" in m_lower:
            # Centrifugal Pump: Higher impeller rpm, lower fluid torque, moderate hydraulic head
            self.base_speed = 1780.0 + random.uniform(-40.0, 40.0)
            self.base_torque = 29.5 + random.uniform(-2.5, 2.5)
            self.base_pressure = 3.8 + random.uniform(-0.2, 0.2)
            self.base_vibe = 1.35 + random.uniform(-0.2, 0.2)
        elif "compressor" in m_lower:
            # Air Compressor: Steady synchronous speed, high delivery line pressure
            self.base_speed = 1500.0 + random.uniform(-20.0, 20.0)
            self.base_torque = 38.0 + random.uniform(-2.0, 2.0)
            self.base_pressure = 7.8 + random.uniform(-0.3, 0.3)
            self.base_vibe = 1.65 + random.uniform(-0.2, 0.2)
        elif "robot" in m_lower or "arm" in m_lower:
            # Robotic Arm: Articulated joint servo speeds, dynamic payload torque
            self.base_speed = 1420.0 + random.uniform(-30.0, 30.0)
            self.base_torque = 34.0 + random.uniform(-3.0, 3.0)
            self.base_pressure = 4.2 + random.uniform(-0.2, 0.2)
            self.base_vibe = 1.25 + random.uniform(-0.2, 0.2)
        elif "lathe" in m_lower or "turning" in m_lower:
            # CNC Lathe / Turning Center: Constant surface speed, high cutting torque
            self.base_speed = 1380.0 + random.uniform(-40.0, 40.0)
            self.base_torque = 46.0 + random.uniform(-3.5, 3.5)
            self.base_pressure = 4.0 + random.uniform(-0.2, 0.2)
            self.base_vibe = 1.45 + random.uniform(-0.2, 0.3)
        elif "fan" in m_lower or "blower" in m_lower:
            # Industrial Blower / Exhaust: Continuous high-speed airflow, low torque, very low vibration
            self.base_speed = 1820.0 + random.uniform(-30.0, 30.0)
            self.base_torque = 24.0 + random.uniform(-2.0, 2.0)
            self.base_pressure = 2.2 + random.uniform(-0.1, 0.1)
            self.base_vibe = 1.1 + random.uniform(-0.1, 0.2)
        elif "conveyor" in m_lower:
            # Assembly Conveyor Drive: Low rpm, stable torque drive
            self.base_speed = 960.0 + random.uniform(-20.0, 20.0)
            self.base_torque = 33.0 + random.uniform(-2.5, 2.5)
            self.base_pressure = 3.0 + random.uniform(-0.1, 0.1)
            self.base_vibe = 0.95 + random.uniform(-0.1, 0.2)
        else:
            # CNC Milling Center (Standard AI4I 2020 spindle envelope)
            self.base_speed = 1520.0 + random.uniform(-50.0, 50.0)  # ~1470 - 1570 rpm
            self.base_torque = 39.0 + random.uniform(-4.0, 4.0)     # ~35 - 43 Nm
            self.base_vibe = 1.6 + random.uniform(-0.3, 0.4)        # ~1.3 - 2.0 mm/s
            self.base_pressure = 4.5 + random.uniform(-0.2, 0.2)    # ~4.3 - 4.7 bar

    def inject_fault(self, mode: str, severity: float = 0.9):
        self.fault_mode = mode.lower()
        self.fault_severity = max(0.1, min(1.0, severity))
        print(f"\n >>> [FAULT INJECTED] Machine {self.machine_id} -> Mode: {self.fault_mode.upper()} (Severity: {self.fault_severity:.2f})")

    def clear_fault(self):
        print(f"\n >>> [FAULT CLEARED / MAINTENANCE REPAIR SIMULATED] Machine {self.machine_id} -> Restored to nominal healthy baseline.")
        self.fault_mode = None
        self.fault_severity = 0.0
        self.tool_wear_min = random.uniform(15.0, 35.0) # Reset tool contact wear after tool insert replacement

    def step(self, accelerate_wear: bool = False) -> Dict[str, Any]:
        """Calculates next physics-consistent reading adhering to AI4I and plant condition dynamics."""
        self.cycle += 1
        
        # Tool wear accumulation
        wear_increment = 0.8 if accelerate_wear else 0.15
        self.tool_wear_min = min(250.0, self.tool_wear_min + wear_increment)

        # Baseline physical parameters
        air_k = self.base_air_temp + random.gauss(0, 0.25)
        # Healthy process temp runs 9.5 to 11.5 K above ambient
        proc_k = air_k + 10.2 + random.gauss(0, 0.3)
        speed = self.base_speed + random.gauss(0, 18.0)
        torque = self.base_torque + random.gauss(0, 1.5)
        vibe = self.base_vibe + random.gauss(0, 0.1)
        pressure = self.base_pressure + random.gauss(0, 0.08)

        # Apply Physical Fault Modes
        if self.fault_mode in ["hdf", "thermal"]:
            # Heat Dissipation Failure: process-ambient delta drops < 8.6 K, speed drops < 1380 rpm
            speed = 1310.0 - 40.0 * self.fault_severity + random.gauss(0, 10.0)
            air_k += 3.5 * self.fault_severity
            proc_k = air_k + 4.2 * (1.0 - 0.4 * self.fault_severity) # Delta drops to 4-5 K
            torque += 5.0 * self.fault_severity
            vibe += 1.2 * self.fault_severity

        elif self.fault_mode in ["pwf", "power"]:
            # Power Failure: Power = Torque * speed * 2pi/60. PWF triggers if power < 3500W or > 9000W
            if random.random() > 0.4:
                # Torque overload spike (> 68 Nm)
                torque = 72.0 + 8.0 * self.fault_severity + random.gauss(0, 2.0)
                speed = 1420.0 + random.gauss(0, 25.0)
            else:
                # Rotational runaway overspeed (> 2500 rpm)
                speed = 2650.0 + 150.0 * self.fault_severity + random.gauss(0, 30.0)
                torque = 38.0
            vibe += 2.2 * self.fault_severity

        elif self.fault_mode in ["osf", "overstrain"]:
            # Overstrain Failure: Tool wear * Torque exceeds limit (11000 for L, 12000 for M)
            self.tool_wear_min = max(self.tool_wear_min, 195.0 + 35.0 * self.fault_severity)
            torque = 64.0 + 6.0 * self.fault_severity + random.gauss(0, 1.8)
            speed = 1440.0 + random.gauss(0, 20.0)
            vibe += 2.0 * self.fault_severity

        elif self.fault_mode in ["twf", "tool_wear"]:
            # Tool Wear Failure: Tool wear approaches/exceeds 240 minutes
            self.tool_wear_min = 238.0 + 10.0 * self.fault_severity
            torque += 8.0 * self.fault_severity
            vibe += 1.8 * self.fault_severity

        elif self.fault_mode == "bearing":
            # Bearing damage: Extreme vibration spike (> 6.0 mm/s), friction torque
            vibe = 6.8 + 4.5 * self.fault_severity + random.uniform(0.5, 2.0)
            torque += 12.0 * self.fault_severity
            proc_k += 8.0 * self.fault_severity

        elif self.fault_mode == "pressure":
            # Hydraulic seal leak or blockage
            if random.random() > 0.5:
                pressure = max(0.8, 1.8 - 0.8 * self.fault_severity) # Cavitation leak
            else:
                pressure = 7.8 + 2.5 * self.fault_severity # Relief blockage
            vibe += 1.5 * self.fault_severity

        # Derive engineering units
        power_kW = (torque * (speed * 2.0 * math.pi / 60.0)) / 1000.0
        temp_degC = proc_k - 273.15
        operating_load = min(100.0, max(15.0, (torque / 65.0) * 100.0))

        return {
            "machine_id": self.machine_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle": self.cycle,
            # AI4I Features
            "air_temperature": round(air_k, 2),
            "process_temperature": round(proc_k, 2),
            "rotational_speed": round(speed, 1),
            "torque": round(torque, 2),
            "tool_wear": round(self.tool_wear_min, 1),
            # RUL Dataset Synonyms
            "tool_wear_min": round(self.tool_wear_min, 1),
            "control_type": self.type_variant,
            # Condition Telemetry
            "temperature": round(temp_degC, 1),
            "vibration": round(max(0.1, vibe), 2),
            "pressure": round(max(0.2, pressure), 2),
            "power_consumption": round(max(1.0, power_kW), 2),
            "operating_load": round(operating_load, 1)
        }


def fetch_registered_machines(api_url: str) -> List[Dict[str, Any]]:
    try:
        url = f"{api_url.rstrip('/')}/machines"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[WARN] Could not connect to backend at {api_url}: {e}")
    return []


def main():
    parser = argparse.ArgumentParser(
        description="External Industrial Sensor Telemetry Generator for AI Predictive Maintenance Platform."
    )
    parser.add_argument("--api", type=str, default=DEFAULT_API_URL, help=f"Backend API URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--machines", type=str, default="", help="Comma-separated machine IDs to simulate (e.g. CNC-101,PUMP-201). If omitted, queries backend.")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL, help="Transmission interval in seconds (default: 1.0)")
    parser.add_argument("--fault", choices=["none", "hdf", "pwf", "osf", "twf", "bearing", "pressure", "random"], default="none", help="Fault mode to inject")
    parser.add_argument("--target", type=str, default="", help="Specific machine ID to inject fault into (default: first machine or all)")
    parser.add_argument("--deteriorate", action="store_true", help="Enable accelerated wear progression")
    parser.add_argument("--recover-after", type=int, default=0, help="Automatically clear fault after N cycles to simulate maintenance repair and verify recovery")
    parser.add_argument("--count", type=int, default=0, help="Number of telemetry cycles to emit (0 = continuous loop)")
    parser.add_argument("--list", action="store_true", help="List registered machines from backend and exit")

    args = parser.parse_args()
    api_url = args.api.rstrip("/")
    telemetry_url = f"{api_url}/telemetry"

    # List machines and exit if requested
    if args.list:
        print(f"Connecting to {api_url}/machines ...")
        m_list = fetch_registered_machines(api_url)
        if m_list:
            print(f"\nDiscovered {len(m_list)} registered machine(s):")
            for m in m_list:
                print(f"  - [{m['machine_id']}] {m.get('name', 'Unit')} | Type: {m.get('machine_type')} | Variant: {m.get('type_variant', 'M')} | Status: {m.get('status')}")
        else:
            print("No machines found or backend is offline.")
        sys.exit(0)

    print("=" * 115)
    print(" Industrial Telemetry Generator - AI-Driven Predictive Maintenance Platform")
    print("=" * 115)
    print(f" Target Endpoint:    {telemetry_url}")
    print(f" Polling Interval:  {args.interval}s")
    print(f" Fault Simulation:  {args.fault.upper()}")
    print(f" Tool Wear Deterioration: {'ENABLED' if args.deteriorate else 'DISABLED'}")
    print("=" * 115)

    # Resolve machines
    simulators: List[IndustrialMachineSimulator] = []
    if args.machines.strip():
        m_ids = [m.strip().upper() for m in args.machines.split(",") if m.strip()]
        for mid in m_ids:
            simulators.append(IndustrialMachineSimulator(mid))
    else:
        print(f"Querying registered machinery from {api_url}/machines ...")
        fetched = fetch_registered_machines(api_url)
        if fetched:
            print(f"Discovered {len(fetched)} registered machine(s) in database:")
            for m in fetched:
                mid = m["machine_id"]
                mname = m.get("name", "Unit")
                mtype = m.get("machine_type", "Generic")
                tvar = m.get("type_variant", "M")
                print(f" - [{mid}] {mname} ({mtype}) [Variant: {tvar}]")
                simulators.append(IndustrialMachineSimulator(mid, mtype, tvar))
        else:
            print("[INFO] Backend unreachable or no machines yet. Initializing default industrial demo units:")
            defaults = [
                ("CNC-001", "CNC Mill", "M"),
                ("CNC-101", "CNC Mill", "M"),
                ("PUMP-201", "Centrifugal Pump", "L"),
                ("PRESS-301", "Hydraulic Press", "H"),
                ("COMP-401", "Air Compressor", "M")
            ]
            for mid, mtype, tvar in defaults:
                print(f" - [{mid}] {mtype} (Variant {tvar})")
                simulators.append(IndustrialMachineSimulator(mid, mtype, tvar))

    # Apply fault injection
    if args.fault != "none":
        target_mid = args.target.strip().upper()
        modes = ["hdf", "pwf", "osf", "twf", "bearing", "pressure"]
        
        for sim in simulators:
            if not target_mid or sim.machine_id == target_mid:
                mode = random.choice(modes) if args.fault == "random" else args.fault
                sim.inject_fault(mode, severity=0.92)

    cycles = 0
    print("\nStreaming real-time telemetry to backend via machine ID. Press Ctrl+C to stop.\n")

    try:
        while True:
            cycles += 1
            now_str = datetime.now().strftime("%H:%M:%S")
            print(f"--- Telemetry Cycle #{cycles} [{now_str}] ---")

            # Periodic fleet discovery: re-query registered machinery every 5 cycles
            if not args.machines.strip() and cycles % 5 == 0:
                fresh_list = fetch_registered_machines(api_url)
                if fresh_list:
                    existing_mids = {s.machine_id for s in simulators}
                    fresh_mids = {m["machine_id"] for m in fresh_list}
                    for m in fresh_list:
                        if m["machine_id"] not in existing_mids:
                            print(f"  [FLEET DISCOVERY] Auto-detected newly registered machine: {m['machine_id']} ({m.get('machine_type')})")
                            simulators.append(IndustrialMachineSimulator(
                                m["machine_id"],
                                m.get("machine_type", "CNC Mill"),
                                m.get("type_variant", "M")
                            ))
                    # Retain only machines currently active in the database
                    simulators = [s for s in simulators if s.machine_id in fresh_mids]

            # Automated recovery simulation after configured cycles
            if args.recover_after > 0 and cycles == (args.recover_after + 1):
                print(f"\n[MAINTENANCE TRIGGER] Simulating maintenance completion after {args.recover_after} cycles. Restoring nominal machine states...")
                for sim in simulators:
                    if sim.fault_mode:
                        sim.clear_fault()

            for sim in simulators:
                payload = sim.step(accelerate_wear=args.deteriorate)
                try:
                    resp = requests.post(telemetry_url, json=payload, timeout=15)
                    if resp.status_code == 201:
                        data = resp.json()
                        pred = data.get("prediction", {})
                        
                        # Failure Prediction
                        raw_prob = pred.get("failure_probability")
                        if raw_prob is not None:
                            prob_pct = raw_prob * 100.0 if raw_prob <= 1.0 else raw_prob
                            prob_str = f"{prob_pct:5.1f}%"
                        else:
                            prob_str = " N/A "
                        risk = pred.get("risk_category", "Low")

                        # Anomaly Detection
                        is_anom = pred.get("anomaly", False)
                        anom_lbl = pred.get("anomaly_label", "Anomaly" if is_anom else "Normal")
                        anom_score = pred.get("anomaly_score")
                        score_str = f"({anom_score:+.2f})" if anom_score is not None else ""
                        anom_display = f"{anom_lbl} {score_str}".strip()

                        # Remaining Useful Life (RUL)
                        rul_val = pred.get("estimated_remaining_cuts")
                        rul_unit = pred.get("rul_unit", "cycles")
                        rul_display = f"{int(round(rul_val))} {rul_unit}" if rul_val is not None else "Active"

                        alert_flag = " [!] ALARM ACTIVE" if data.get("alert_generated") else ""

                        print(
                            f"  [{sim.machine_id:<8}] "
                            f"RPM: {payload['rotational_speed']:5.0f} | "
                            f"Torq: {payload['torque']:4.1f} Nm | "
                            f"Wear: {payload['tool_wear']:4.1f}m | "
                            f"Temp: {payload['temperature']:4.1f}°C | "
                            f"Vibe: {payload['vibration']:4.2f} mm/s | "
                            f"Risk: {prob_str} ({risk:<8}) | "
                            f"Anomaly: {anom_display:<14} | "
                            f"RUL: {rul_display:<10}{alert_flag}"
                        )
                    elif resp.status_code == 404:
                        print(f"  [{sim.machine_id:<8}] Machine not found (HTTP 404): Register machine in dashboard first.")
                    else:
                        print(f"  [{sim.machine_id:<8}] Ingestion status {resp.status_code}: {resp.text}")
                except requests.exceptions.RequestException as e:
                    print(f"  [{sim.machine_id}] Error connecting to {telemetry_url}: {type(e).__name__} - {e}")

            if args.count > 0 and cycles >= args.count:
                print(f"\nCompleted {args.count} requested cycle(s).")
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n\nTelemetry generation stopped by operator.")


if __name__ == "__main__":
    main()
