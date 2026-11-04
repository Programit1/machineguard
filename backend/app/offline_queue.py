"""
MachinaGuard - Local Offline Queue & Resilient Cloud Synchronization
Buffers telemetry and predictions in local SQLite storage during cloud internet interruptions,
then safely syncs pending records to Supabase PostgreSQL when internet connectivity recovers.
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / "maintenance.db"


def get_local_queue_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(LOCAL_DB_PATH), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_sync_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            synced INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def buffer_offline_payload(item_type: str, data: Dict[str, Any]):
    """Stores a record in the local offline buffer when cloud database is temporarily unreachable."""
    try:
        conn = get_local_queue_connection()
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO pending_sync_queue (item_type, payload, created_at, synced) VALUES (?, ?, ?, 0)",
            (item_type, json.dumps(data, default=str), now_iso)
        )
        conn.commit()
        conn.close()
        logger.info(f"[OFFLINE QUEUE] Buffered {item_type} record locally for deferred cloud sync.")
    except Exception as e:
        logger.error(f"[OFFLINE QUEUE] Failed to buffer offline payload: {e}")


def has_pending_items() -> bool:
    try:
        conn = get_local_queue_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pending_sync_queue WHERE synced = 0")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def flush_pending_queue_to_supabase(target_session) -> int:
    """
    Replays queued records into the live Supabase session with duplicate detection.
    Returns the count of successfully synchronized items.
    """
    try:
        conn = get_local_queue_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, item_type, payload FROM pending_sync_queue WHERE synced = 0 ORDER BY id ASC LIMIT 50")
        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return 0

        synced_count = 0
        from .models import SensorReading, Prediction, Alert, Incident

        for row_id, item_type, payload_str in rows:
            data = json.loads(payload_str)
            try:
                if item_type == "sensor_reading":
                    # Duplicate check by machine_id and timestamp
                    ts = datetime.fromisoformat(data["timestamp"]) if isinstance(data["timestamp"], str) else data["timestamp"]
                    exists = target_session.query(SensorReading).filter(
                        SensorReading.machine_id == data["machine_id"],
                        SensorReading.timestamp == ts
                    ).first()
                    if not exists:
                        target_session.add(SensorReading(
                            machine_id=data["machine_id"],
                            timestamp=ts,
                            air_temperature=data.get("air_temperature"),
                            process_temperature=data.get("process_temperature"),
                            rotational_speed=data.get("rotational_speed"),
                            torque=data.get("torque"),
                            tool_wear=data.get("tool_wear"),
                            temperature=data.get("temperature"),
                            vibration=data.get("vibration"),
                            pressure=data.get("pressure"),
                            power_consumption=data.get("power_consumption"),
                            operating_load=data.get("operating_load")
                        ))
                cursor.execute("DELETE FROM pending_sync_queue WHERE id = ?", (row_id,))
                synced_count += 1
            except Exception as item_err:
                logger.warning(f"[OFFLINE QUEUE] Replay error on item #{row_id}: {item_err}")
                break

        target_session.commit()
        conn.commit()
        conn.close()
        if synced_count > 0:
            logger.info(f"[OFFLINE QUEUE] Successfully flushed {synced_count} pending items to Supabase cloud.")
        return synced_count
    except Exception as e:
        logger.warning(f"[OFFLINE QUEUE] Cloud replay check deferred: {e}")
        return 0
