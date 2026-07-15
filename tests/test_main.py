import os
import unittest
from unittest.mock import patch

from src.main import env_topic_ids


class MainTests(unittest.TestCase):
    def test_topic_ids_support_comma_separated_values(self):
        with patch.dict(os.environ, {"WXPUSHER_TOPIC_IDS": "123, 456"}):
            self.assertEqual(env_topic_ids("WXPUSHER_TOPIC_IDS"), [123, 456])

    def test_topic_ids_reject_invalid_values(self):
        with patch.dict(os.environ, {"WXPUSHER_TOPIC_IDS": "123,abc"}):
            with self.assertRaises(ValueError):
                env_topic_ids("WXPUSHER_TOPIC_IDS")


if __name__ == "__main__":
    unittest.main()
