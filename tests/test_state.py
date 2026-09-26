import tempfile
import unittest
from pathlib import Path

from src.state import PushState, load_state, save_state


class StateTests(unittest.TestCase):
    def test_missing_state_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            state = load_state(Path(directory) / "missing.json")
            self.assertIsNone(state.last_guid)
            self.assertEqual(state.channels, {})

    def test_state_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "state.json"
            save_state(path, PushState(last_guid="issue-1495"))
            self.assertEqual(load_state(path).last_guid, "issue-1495")

    def test_channel_cursors_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            state = PushState(last_guid="issue-2", channels={"wxpusher": "issue-2", "email": "issue-1"})
            save_state(path, state)
            loaded = load_state(path)
            self.assertEqual(loaded.channels, {"wxpusher": "issue-2", "email": "issue-1"})

    def test_cursor_for_falls_back_to_last_guid(self):
        state = PushState(last_guid="issue-2", channels={"wxpusher": "issue-2"})
        self.assertEqual(state.cursor_for("email"), "issue-2")
        self.assertEqual(state.cursor_for("wxpusher"), "issue-2")

    def test_legacy_state_without_channels_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text('{"last_guid": "issue-1"}', encoding="utf-8")
            state = load_state(path)
            self.assertEqual(state.last_guid, "issue-1")
            self.assertEqual(state.channels, {})

    def test_invalid_channels_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text('{"last_guid": "a", "channels": ["wxpusher"]}', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                load_state(path)

    def test_invalid_channel_value_type_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text('{"last_guid": "a", "channels": {"wxpusher": 1}}', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                load_state(path)


if __name__ == "__main__":
    unittest.main()
