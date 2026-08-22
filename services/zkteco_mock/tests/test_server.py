import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from collections import defaultdict
from contextlib import closing
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

from server import create_server, initialize_database  # noqa: E402


class ZKTecoMockTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "zkteco.db")
        initialize_database(self.db_path, "2026-07", reset=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seed_is_realistic_and_contains_known_anomaly(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM employees").fetchone()[0], 9)
            punches = connection.execute(
                "SELECT device_user_id, local_datetime, punch_type FROM punches ORDER BY local_datetime"
            ).fetchall()
            self.assertGreater(len(punches), 350)
            self.assertEqual(
                connection.execute("SELECT COUNT(*) - COUNT(DISTINCT external_uid) FROM punches").fetchone()[0],
                0,
            )

        grouped = defaultdict(dict)
        for employee_id, timestamp, punch_type in punches:
            local_at = datetime.fromisoformat(timestamp)
            self.assertLess(local_at.weekday(), 5)
            self.assertNotEqual(local_at.date().isoformat(), "2026-07-30")
            grouped[(employee_id, local_at.date().isoformat())][punch_type] = local_at

        missing_checkout = grouped[("1007", "2026-07-22")]
        self.assertIn("check_in", missing_checkout)
        self.assertNotIn("check_out", missing_checkout)

        for key, pair in grouped.items():
            if key == ("1007", "2026-07-22"):
                continue
            self.assertEqual(set(pair), {"check_in", "check_out"})
            duration = pair["check_out"] - pair["check_in"]
            self.assertGreater(duration.total_seconds(), 6 * 3600)
            self.assertLess(duration.total_seconds(), 11 * 3600)

    def test_api_authentication_and_cursor_pagination(self):
        server = create_server("127.0.0.1", 0, self.db_path, "test-key")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            with self.assertRaises(HTTPError) as unauthorized:
                urlopen(f"{base_url}/api/v1/punches", timeout=3)
            self.assertEqual(unauthorized.exception.code, 401)

            with urlopen(f"{base_url}/demo", timeout=3) as response:
                demo_page = response.read().decode("utf-8")
            self.assertIn("ZKTeco mock attendance data", demo_page)
            self.assertIn("383", demo_page)

            request = Request(
                f"{base_url}/api/v1/punches?after_id=0&limit=5",
                headers={"X-API-Key": "test-key"},
            )
            with urlopen(request, timeout=3) as response:
                payload = json.load(response)
            self.assertEqual(len(payload["data"]), 5)
            self.assertTrue(payload["pagination"]["has_more"])
            self.assertEqual(payload["pagination"]["next_after_id"], payload["data"][-1]["id"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
