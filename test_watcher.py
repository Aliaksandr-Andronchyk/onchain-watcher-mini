import json
import sqlite3
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

import watcher


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


LOG_SAMPLE = {
    "blockNumber": "0x2",
    "transactionHash": "0xabc",
    "logIndex": "0x0",
    "address": "0xdead",
    "topics": ["0xtopic0"],
    "data": "0x01",
}


class WatcherTest(unittest.TestCase):
    def test_get_block_number_parses_hex(self):
        with patch.object(urllib.request, "urlopen", return_value=FakeResponse({"result": "0x10"})):
            self.assertEqual(watcher.get_block_number("http://rpc"), 16)

    def test_save_log_is_idempotent(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE находки (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                block_number INTEGER NOT NULL,
                tx_hash TEXT NOT NULL,
                log_index INTEGER NOT NULL,
                address TEXT NOT NULL,
                topics TEXT NOT NULL,
                data TEXT NOT NULL,
                найдено_в TEXT NOT NULL,
                UNIQUE(tx_hash, log_index)
            )
            """
        )
        self.assertTrue(watcher.save_log(conn, LOG_SAMPLE))
        self.assertFalse(watcher.save_log(conn, LOG_SAMPLE))
        rows = conn.execute("SELECT COUNT(*) FROM находки").fetchone()[0]
        self.assertEqual(rows, 1)

    def test_run_once_writes_new_log_to_db(self):
        db_path = Path("/tmp/test_watcher.db")
        db_path.unlink(missing_ok=True)

        responses = [
            {"result": "0x5"},
            {"result": [LOG_SAMPLE]},
        ]

        def fake_urlopen(req, timeout=15):
            return FakeResponse(responses.pop(0))

        with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            watcher.run(
                rpc_url="http://rpc",
                address="0xdead",
                topic=None,
                db_path=db_path,
                tg_token=None,
                tg_chat_id=None,
                poll_interval=0,
                once=True,
                start_block=4,
            )

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT tx_hash FROM находки").fetchall()
        self.assertEqual(rows, [("0xabc",)])
        db_path.unlink(missing_ok=True)

    def test_run_once_without_start_block_still_checks_current_block(self):
        db_path = Path("/tmp/test_watcher_no_start.db")
        db_path.unlink(missing_ok=True)

        responses = [
            {"result": "0x5"},
            {"result": "0x5"},
            {"result": [LOG_SAMPLE]},
        ]

        def fake_urlopen(req, timeout=15):
            return FakeResponse(responses.pop(0))

        with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            watcher.run(
                rpc_url="http://rpc",
                address="0xdead",
                topic=None,
                db_path=db_path,
                tg_token=None,
                tg_chat_id=None,
                poll_interval=0,
                once=True,
                start_block=None,
            )

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT tx_hash FROM находки").fetchall()
        self.assertEqual(rows, [("0xabc",)])
        db_path.unlink(missing_ok=True)

    def test_format_alert_contains_key_fields(self):
        text = watcher.format_alert(LOG_SAMPLE)
        self.assertIn("0xabc", text)
        self.assertIn("0xdead", text)


if __name__ == "__main__":
    unittest.main()
