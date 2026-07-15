import unittest
from unittest.mock import Mock

from src.feed import FeedItem
from src.wxpusher import PushError, WxPusherClient, build_message


class WxPusherTests(unittest.TestCase):
    def test_build_message_is_deterministic(self):
        item = FeedItem(
            guid="issue-1",
            title="第1期",
            link="https://example.com/1",
            summary="摘要",
            content_html="<p>完整内容</p>",
            published="2026-07-15 20:01",
        )
        self.assertEqual(build_message(item), build_message(item))
        self.assertIn("完整内容", build_message(item).content)

    def test_summary_mode_does_not_include_full_content(self):
        item = FeedItem(
            guid="issue-1",
            title="第1期",
            link="https://example.com/1",
            summary="本期摘要",
            content_html="<p>完整内容</p>",
            published="",
        )
        message = build_message(item, content_mode="summary")
        self.assertIn("本期摘要", message.content)
        self.assertNotIn("完整内容", message.content)

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
        client.send(build_message(FeedItem("1", "1", "https://e/1", "s", "c", "")))
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
        client.send(build_message(FeedItem("1", "1", "https://e/1", "s", "c", "")))
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
            client.send(build_message(FeedItem("1", "1", "https://e/1", "s", "c", "")))


if __name__ == "__main__":
    unittest.main()
