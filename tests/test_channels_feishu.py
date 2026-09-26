import json
import os
import unittest
from unittest.mock import Mock, patch

from src.channels.base import PushError
from src.channels.feishu import FeishuChannel, build_card, feishu_sign
from src.feed import FeedItem


def make_item(**overrides) -> FeedItem:
    base = dict(
        guid="issue-1",
        title="第1期 - 2026-09-26 20:05",
        link="https://example.com/1",
        summary="本期[重点]摘要",
        content_html=(
            "<ul>"
            "<li><strong>[模型动态] 新模型发布</strong><br/>能力显著提升。"
            "<br/><small>来源：<a href='https://source.example'>官方</a> [官网]</small></li>"
            "<li><strong>[行业资讯] 行业新闻</strong><br/>行业动态。</li>"
            "</ul>"
        ),
        published="",
    )
    base.update(overrides)
    return FeedItem(**base)


def make_response(data: dict) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = data
    return response


class FeishuSignTests(unittest.TestCase):
    def test_sign_matches_official_algorithm(self):
        # 官方算法：key = "{timestamp}\n{secret}"，对空内容签名，再 base64。
        self.assertEqual(feishu_sign("test-secret", 1700000000), "mbm4Y4oluIPQ00qlBIhX8vAZ0EKv3nw0LuTb91jPL84=")

    def test_sign_differs_by_timestamp_and_secret(self):
        self.assertNotEqual(feishu_sign("a", 1), feishu_sign("b", 1))
        self.assertNotEqual(feishu_sign("a", 1), feishu_sign("a", 2))


class FeishuCardTests(unittest.TestCase):
    def test_card_groups_categories_and_keeps_sources(self):
        card = build_card(make_item())
        self.assertEqual(card["header"]["template"], "orange")
        self.assertIn("大黑AI速报", card["header"]["title"]["content"])
        contents = [element.get("text", {}).get("content", "") for element in card["elements"]]
        joined = "\n".join(contents)
        self.assertIn("◆ AI 总结", joined)
        self.assertIn("**重点**", joined)
        self.assertIn("模型动态（1 条）", joined)
        self.assertIn("行业资讯（1 条）", joined)
        self.assertIn("01 新模型发布", joined)
        self.assertIn("[官方 ↗](https://source.example)", joined)
        actions = [element for element in card["elements"] if element.get("tag") == "action"]
        self.assertEqual(actions[0]["actions"][0]["url"], "https://example.com/1")

    def test_summary_mode_skips_category_sections(self):
        card = build_card(make_item(), content_mode="summary")
        contents = "\n".join(element.get("text", {}).get("content", "") for element in card["elements"])
        self.assertNotIn("模型动态（1 条）", contents)
        self.assertIn("◆ AI 总结", contents)


class FeishuChannelTests(unittest.TestCase):
    def make_channel(self, **kwargs) -> FeishuChannel:
        config = dict(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/x", secret="s")
        config.update(kwargs)
        return FeishuChannel(**config)

    def test_from_env_requires_webhook(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                FeishuChannel.from_env()

    def test_from_env_reads_config(self):
        env = {"FEISHU_WEBHOOK_URL": "https://hook", "FEISHU_SECRET": "sec"}
        with patch.dict(os.environ, env, clear=True):
            channel = FeishuChannel.from_env()
        self.assertEqual(channel.webhook_url, "https://hook")
        self.assertEqual(channel.secret, "sec")

    def test_send_payload_contains_card_and_signature(self):
        session = Mock()
        session.post.return_value = make_response({"code": 0, "msg": "success"})
        channel = self.make_channel(session=session)
        channel.send(make_item(), content_mode="full")

        payload = session.post.call_args.kwargs["json"]
        self.assertEqual(payload["msg_type"], "interactive")
        self.assertIn("timestamp", payload)
        self.assertIn("sign", payload)
        self.assertEqual(payload["sign"], feishu_sign("s", int(payload["timestamp"])))
        self.assertIn("大黑AI速报", payload["card"]["header"]["title"]["content"])

    def test_send_without_secret_omits_signature_fields(self):
        session = Mock()
        session.post.return_value = make_response({"StatusCode": 0, "StatusMessage": "success"})
        channel = self.make_channel(secret="", session=session)
        channel.send(make_item(), content_mode="full")

        payload = session.post.call_args.kwargs["json"]
        self.assertNotIn("timestamp", payload)
        self.assertNotIn("sign", payload)

    def test_send_accepts_legacy_response_format(self):
        session = Mock()
        session.post.return_value = make_response({"StatusCode": 0, "StatusMessage": "success"})
        channel = self.make_channel(session=session)
        channel.send(make_item(), content_mode="full")

    def test_send_rejects_business_error(self):
        session = Mock()
        session.post.return_value = make_response({"code": 19021, "msg": "Sign Match Fail"})
        channel = self.make_channel(session=session)
        with self.assertRaises(PushError):
            channel.send(make_item(), content_mode="full")

    def test_send_rejects_http_error(self):
        import requests

        session = Mock()
        session.post.side_effect = requests.RequestException("boom")
        channel = self.make_channel(session=session)
        with self.assertRaises(PushError):
            channel.send(make_item(), content_mode="full")

    def test_oversized_issue_degrades_to_summary_card(self):
        huge_list = "".join(
            f"<li><strong>[行业资讯] 条目{i}</strong><br/>{'内容' * 200}</li>" for i in range(120)
        )
        item = make_item(content_html=f"<ul>{huge_list}</ul>")
        session = Mock()
        session.post.return_value = make_response({"code": 0, "msg": "success"})
        channel = self.make_channel(session=session)
        channel.send(item, content_mode="full")

        payload = session.post.call_args.kwargs["json"]
        self.assertLessEqual(len(json.dumps(payload, ensure_ascii=False)), 28_000 + len(json.dumps({"msg_type": "interactive"})))
        contents = "\n".join(
            element.get("text", {}).get("content", "") for element in payload["card"]["elements"]
        )
        self.assertNotIn("行业资讯（", contents)


if __name__ == "__main__":
    unittest.main()
