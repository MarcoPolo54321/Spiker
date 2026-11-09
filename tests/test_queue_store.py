import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from queue_store import QueueStore


class QueueStoreTests(unittest.TestCase):
    def test_round_trip_and_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = QueueStore(Path(tmp) / "queue.db")
            task = {"id": "task-1", "path": "sample.mp4", "status": "processing", "segments": [{"text": "Привет"}]}
            changed, deleted = store.save_tasks([task])
            self.assertEqual((changed, deleted), (1, 0))
            self.assertEqual(store.load_tasks(), [task])
            self.assertTrue(store.integrity_check())
            with store._connect() as db:
                meta = db.execute("SELECT value FROM queue_meta WHERE key='schema_version'").fetchone()
            self.assertEqual(meta[0], "1")
            store.checkpoint()

    def test_large_queue_avoids_sqlite_parameter_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = QueueStore(Path(tmp) / "queue.db")
            tasks = [
                {"id": f"task-{index:04d}", "path": f"{index}.wav", "status": "queued"}
                for index in range(1205)
            ]
            changed, deleted = store.save_tasks(tasks)
            self.assertEqual((changed, deleted), (1205, 0))
            loaded = store.load_tasks()
            self.assertEqual(len(loaded), 1205)
            changed, deleted = store.save_tasks(tasks[:2])
            self.assertEqual(changed, 0)
            self.assertEqual(deleted, 1203)

    def test_unchanged_rows_are_not_rewritten_and_removed_tasks_are_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = QueueStore(Path(tmp) / "queue.db")
            one = {"id": "one", "path": "one.wav", "status": "queued"}
            two = {"id": "two", "path": "two.wav", "status": "queued"}
            store.save_tasks([one, two])
            changed, deleted = store.save_tasks([one])
            self.assertEqual(changed, 0)
            self.assertEqual(deleted, 1)
            self.assertEqual([item["id"] for item in store.load_tasks()], ["one"])


if __name__ == "__main__":
    unittest.main()
