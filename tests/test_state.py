import tempfile
import unittest
from pathlib import Path

from src.state import PushState, load_state, save_state


class StateTests(unittest.TestCase):
    def test_missing_state_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            state = load_state(Path(directory) / "missing.json")
            self.assertIsNone(state.last_guid)

    def test_state_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "state.json"
            save_state(path, PushState(last_guid="issue-1495"))
            self.assertEqual(load_state(path).last_guid, "issue-1495")


if __name__ == "__main__":
    unittest.main()

