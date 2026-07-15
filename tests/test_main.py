import os
import unittest
from unittest.mock import patch

from src.feed import FeedItem
from src.main import env_topic_ids, run
from src.state import PushState


class MainTests(unittest.TestCase):
    def test_topic_ids_support_comma_separated_values(self):
        with patch.dict(os.environ, {"WXPUSHER_TOPIC_IDS": "123, 456"}):
            self.assertEqual(env_topic_ids("WXPUSHER_TOPIC_IDS"), [123, 456])

    def test_topic_ids_reject_invalid_values(self):
        with patch.dict(os.environ, {"WXPUSHER_TOPIC_IDS": "123,abc"}):
            with self.assertRaises(ValueError):
                env_topic_ids("WXPUSHER_TOPIC_IDS")

    @patch("src.main.save_state")
    @patch("src.main.WxPusherClient")
    @patch("src.main.load_state")
    @patch("src.main.fetch_feed")
    def test_force_push_latest_resends_without_changing_state(
        self,
        fetch_feed_mock,
        load_state_mock,
        client_class_mock,
        save_state_mock,
    ):
        item = FeedItem(
            guid="issue-1",
            title="第1期",
            link="https://example.com/1",
            summary="摘要",
            content_html="<p>内容</p>",
            published="",
        )
        fetch_feed_mock.return_value = [item]
        load_state_mock.return_value = PushState(last_guid=item.guid)
        with patch.dict(
            os.environ,
            {
                "FORCE_PUSH_LATEST": "true",
                "WXPUSHER_APP_TOKEN": "AT_test",
                "WXPUSHER_UID": "UID_test",
            },
            clear=True,
        ):
            self.assertEqual(run(), 0)

        client_class_mock.return_value.send.assert_called_once()
        save_state_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
