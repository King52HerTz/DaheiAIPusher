import os
import unittest
from unittest.mock import Mock, patch

from src.channels.base import PushError
from src.channels.wxpusher import WxPusherChannel, WxPusherClient, env_topic_ids
from src.feed import FeedItem
from src.render import PushMessage, build_message


def make_item() -> FeedItem:
    return FeedItem("1", "1", "https://e/1", "s", "c", "")


class WxPusherChannelTests(unittest.TestCase):
    def test_topic_ids_support_comma_separated_values(self):
        with patch.dict(os.environ, {"WXPUSHER_TOPIC_IDS": "123, 456"}):
            self.assertEqual(env_topic_ids("WXPUSHER_TOPIC_IDS"), [123, 456])

    def test_topic_ids_reject_invalid_values(self):
        with patch.dict(os.environ, {"WXPUSHER_TOPIC_IDS": "123,abc"}):
            with self.assertRaises(ValueError):
                env_topic_ids("WXPUSHER_TOPIC_IDS")

    def test_from_env_requires_uid_or_topic(self):
        with patch.dict(os.environ, {"WXPUSHER_APP_TOKEN": "AT_test"}, clear=True):
            with self.assertRaises(ValueError):
                WxPusherChannel.from_env()

    def test_from_env_requires_token(self):
        with patch.dict(os.environ, {"WXPUSHER_UID": "UID_test"}, clear=True):
            with self.assertRaises(ValueError):
                WxPusherChannel.from_env()

    def test_channel_send_builds_message_and_delegates(self):
        client = Mock()
        channel = WxPusherChannel(client)
        channel.send(make_item(), content_mode="summary")
        message = client.send.call_args.args[0]
        self.assertIsInstance(message, PushMessage)
        self.assertIn("s", message.content)

    def test_send_accepts_success_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "code": 1000,
            "success": True,
            "data": [{"uid": "UID_test", "code": 1000, "status": "成功"}],
        }
        session = Mock()
        session.post.return_value = response
        client = WxPusherClient("AT_test", ["UID_test"], session=session)
        client.send(build_message(make_item()))
        session.post.assert_called_once()

    def test_send_supports_topic_broadcast(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "code": 1000,
            "success": True,
            "data": [{"topicId": 123, "code": 1000, "status": "成功"}],
        }
        session = Mock()
        session.post.return_value = response
        client = WxPusherClient("AT_test", topic_ids=[123], session=session)
        client.send(build_message(make_item()))
        payload = session.post.call_args.kwargs["json"]
        self.assertEqual(payload["topicIds"], [123])
        self.assertNotIn("uids", payload)

    def test_client_requires_uid_or_topic(self):
        with self.assertRaises(ValueError):
            WxPusherClient("AT_test", session=Mock())

    def test_send_rejects_partial_failure(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "code": 1000,
            "success": True,
            "data": [{"uid": "UID_test", "code": 1001, "status": "失败"}],
        }
        session = Mock()
        session.post.return_value = response
        client = WxPusherClient("AT_test", ["UID_test"], session=session)
        with self.assertRaises(PushError):
            client.send(build_message(make_item()))

    def test_send_rejects_content_over_wxpusher_limit(self):
        session = Mock()
        client = WxPusherClient("AT_test", ["UID_test"], session=session)
        oversized = PushMessage(summary="s", content="x" * 40_001, url="https://e/1")
        with self.assertRaises(PushError):
            client.send(oversized)
        session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
