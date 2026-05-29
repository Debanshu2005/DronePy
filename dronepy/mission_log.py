"""SQLite-backed mission logging for fully offline operation."""

from __future__ import annotations

from contextlib import closing
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any


class MissionLog:
    """Store missions, steps, sensor logs, and detections in SQLite."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    instruction TEXT,
                    task_type TEXT,
                    outcome TEXT,
                    duration_sec REAL,
                    battery_start_v REAL,
                    battery_end_v REAL,
                    config_snapshot TEXT
                );
                CREATE TABLE IF NOT EXISTS steps (
                    id INTEGER PRIMARY KEY,
                    mission_id INTEGER,
                    step_index INTEGER,
                    action TEXT,
                    device TEXT,
                    params TEXT,
                    status TEXT,
                    timestamp TEXT
                );
                CREATE TABLE IF NOT EXISTS sensor_logs (
                    id INTEGER PRIMARY KEY,
                    mission_id INTEGER,
                    timestamp TEXT,
                    sensor_name TEXT,
                    value TEXT
                );
                CREATE TABLE IF NOT EXISTS detections (
                    id INTEGER PRIMARY KEY,
                    mission_id INTEGER,
                    timestamp TEXT,
                    model_used TEXT,
                    label TEXT,
                    confidence REAL,
                    gps_lat REAL,
                    gps_lon REAL,
                    frame_path TEXT
                );
                """
            )
            connection.commit()

    def start_mission(self, instruction: str, task_type: str, battery_v: float | None, config: dict[str, Any]) -> int:
        """Insert a mission record and return its integer mission id."""
        timestamp = self._now()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO missions (
                    timestamp, instruction, task_type, outcome, duration_sec,
                    battery_start_v, battery_end_v, config_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    instruction,
                    task_type,
                    "started",
                    0.0,
                    battery_v,
                    None,
                    json.dumps(config, sort_keys=True),
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def log_step(
        self,
        mission_id: int,
        step_index: int,
        action: str,
        device: str,
        params: dict[str, Any],
        status: str,
    ) -> None:
        """Persist a single mission step."""
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO steps (mission_id, step_index, action, device, params, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mission_id,
                    step_index,
                    action,
                    device,
                    json.dumps(params, sort_keys=True),
                    status,
                    self._now(),
                ),
            )
            connection.commit()

    def log_sensor(self, mission_id: int, sensor_name: str, value: dict[str, Any]) -> None:
        """Persist a sensor reading payload."""
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO sensor_logs (mission_id, timestamp, sensor_name, value)
                VALUES (?, ?, ?, ?)
                """,
                (mission_id, self._now(), sensor_name, json.dumps(value, sort_keys=True)),
            )
            connection.commit()

    def log_detection(
        self,
        mission_id: int,
        model: str,
        label: str,
        conf: float,
        lat: float | None,
        lon: float | None,
        frame_path: str | None,
    ) -> None:
        """Persist an inference detection event."""
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO detections (
                    mission_id, timestamp, model_used, label, confidence, gps_lat, gps_lon, frame_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (mission_id, self._now(), model, label, conf, lat, lon, frame_path),
            )
            connection.commit()

    def end_mission(self, mission_id: int, outcome: str, battery_v: float | None) -> None:
        """Finalize a mission with outcome and battery end voltage."""
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT timestamp FROM missions WHERE id = ?", (mission_id,)).fetchone()
            start_time = datetime.fromisoformat(row[0]) if row else datetime.now(timezone.utc)
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            connection.execute(
                """
                UPDATE missions
                SET outcome = ?, duration_sec = ?, battery_end_v = ?
                WHERE id = ?
                """,
                (outcome, duration, battery_v, mission_id),
            )
            connection.commit()

    def recent_missions(self, n: int = 5) -> list[dict[str, Any]]:
        """Return the most recent missions, newest first."""
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                SELECT id, timestamp, instruction, task_type, outcome, duration_sec,
                       battery_start_v, battery_end_v, config_snapshot
                FROM missions
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (n,),
            )
            return [self._row_to_dict(cursor, row) for row in cursor.fetchall()]

    def cleanup_old(self, retain_days: int) -> None:
        """Delete mission data older than the retention window."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retain_days)).isoformat()
        with closing(self._connect()) as connection:
            mission_ids = [
                row[0]
                for row in connection.execute("SELECT id FROM missions WHERE timestamp < ?", (cutoff,)).fetchall()
            ]
            if not mission_ids:
                return
            placeholders = ", ".join("?" for _ in mission_ids)
            connection.execute(f"DELETE FROM steps WHERE mission_id IN ({placeholders})", mission_ids)
            connection.execute(f"DELETE FROM sensor_logs WHERE mission_id IN ({placeholders})", mission_ids)
            connection.execute(f"DELETE FROM detections WHERE mission_id IN ({placeholders})", mission_ids)
            connection.execute(f"DELETE FROM missions WHERE id IN ({placeholders})", mission_ids)
            connection.commit()

    @staticmethod
    def _row_to_dict(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
        return {description[0]: row[index] for index, description in enumerate(cursor.description)}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
