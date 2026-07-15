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
        self.assertIn("AI NEWS", build_message(item).content)
        self.assertIn("打开网站查看完整速报", build_message(item).content)

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

    def test_full_mode_turns_rss_items_into_styled_cards(self):
        item = FeedItem(
            guid="issue-2",
            title="第1496期 - 2026-07-16 00:01",
            link="https://example.com/2",
            summary="摘要",
            content_html=(
                "<h3>速报总结</h3><p>本期重点内容</p>"
                "<h3>本期内容（共1条）</h3><ul><li>"
                "<strong>[模型动态] 新模型正式发布</strong><br/>模型能力显著提升。"
                "<br/><small>来源：<a href='https://source.example'>官方</a></small>"
                "</li></ul>"
            ),
            published="",
        )
        message = build_message(item)
        self.assertIn("模型动态", message.content)
        self.assertIn("新模型正式发布", message.content)
        self.assertIn("border-radius:14px", message.content)
        self.assertIn("本期重点内容", message.content)

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
