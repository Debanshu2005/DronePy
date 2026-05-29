from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3
import tempfile
import unittest
from pathlib import Path

from dronepy.mission_log import MissionLog


class MissionLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "mission_log.db"
        self.log = MissionLog(self.db_path)
        self.config = {"planner": {"model_path": "models/drone_slm.gguf"}}

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_start_mission_returns_integer_id(self) -> None:
        mission_id = self.log.start_mission("monitor crops", "survey", 12.1, self.config)
        self.assertIsInstance(mission_id, int)

    def test_log_step_and_sensor_and_end_mission_persist_rows(self) -> None:
        mission_id = self.log.start_mission("monitor crops", "survey", 12.1, self.config)
        self.log.log_step(mission_id, 0, "activate", "camera", {"mode": "rgb"}, "completed")
        self.log.log_sensor(mission_id, "camera", {"temperature_c": 40.2})
        self.log.end_mission(mission_id, "success", 11.8)

        with closing(sqlite3.connect(self.db_path)) as connection:
            step_count = connection.execute("SELECT COUNT(*) FROM steps WHERE mission_id = ?", (mission_id,)).fetchone()[0]
            sensor_count = connection.execute(
                "SELECT COUNT(*) FROM sensor_logs WHERE mission_id = ?",
                (mission_id,),
            ).fetchone()[0]
            outcome = connection.execute("SELECT outcome FROM missions WHERE id = ?", (mission_id,)).fetchone()[0]

        self.assertEqual(step_count, 1)
        self.assertEqual(sensor_count, 1)
        self.assertEqual(outcome, "success")

    def test_recent_missions_returns_correct_count(self) -> None:
        for index in range(3):
            self.log.start_mission(f"instruction-{index}", "survey", 12.0, self.config)
        missions = self.log.recent_missions(n=2)
        self.assertEqual(len(missions), 2)

    def test_cleanup_old_removes_old_entries(self) -> None:
        old_id = self.log.start_mission("old mission", "survey", 12.0, self.config)
        new_id = self.log.start_mission("new mission", "survey", 12.0, self.config)
        old_timestamp = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("UPDATE missions SET timestamp = ? WHERE id = ?", (old_timestamp, old_id))
            connection.execute(
                "INSERT INTO steps (mission_id, step_index, action, device, params, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (old_id, 0, "activate", "camera", "{}", "completed", old_timestamp),
            )
            connection.commit()
        self.log.cleanup_old(retain_days=30)
        remaining = [mission["id"] for mission in self.log.recent_missions(n=10)]
        self.assertIn(new_id, remaining)
        self.assertNotIn(old_id, remaining)


if __name__ == "__main__":
    unittest.main()
