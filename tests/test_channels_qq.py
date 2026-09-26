import os
import unittest
from unittest.mock import Mock, patch

import requests

from src.channels.base import PushError
from src.channels.qq import QQ_API_BASE, QQ_TOKEN_URL, QQBotChannel
from src.feed import FeedItem


def make_item() -> FeedItem:
    return FeedItem(
        guid="issue-1",
        title="第1期 - 2026-09-26 20:05",
        link="https://example.com/1",
        summary="本期[重点]摘要",
        content_html=(
            "<ul>"
            "<li><strong>[模型动态] 新模型发布</strong><br/>能力显著提升。"
            "<br/><small>来源：<a href='https://source.example'>官方</a></small></li>"
            "</ul>"
        ),
        published="",
    )


def make_response(status_code: int = 200, json_data=None, text: str = "") -> Mock:
    response = Mock()
    response.status_code = status_code
    response.text = text
    response.json.return_value = json_data if json_data is not None else {"id": "msg-1"}
    return response


def make_channel(session: Mock, **overrides) -> QQBotChannel:
    config = dict(
        app_id="1905684026",
        app_secret="secret",
        group_openids=["GROUP_A"],
        session=session,
    )
    config.update(overrides)
    return QQBotChannel(**config)


class QQConfigTests(unittest.TestCase):
    def test_from_env_reads_config(self):
        env = {
            "QQ_BOT_APP_ID": "1905684026",
            "QQ_BOT_APP_SECRET": "secret",
            "QQ_BOT_GROUP_OPENIDS": " GROUP_A , GROUP_B ",
            "QQ_BOT_API_BASE": "https://sandbox.api.sgroup.qq.com/",
        }
        with patch.dict(os.environ, env, clear=True):
            channel = QQBotChannel.from_env()
        self.assertEqual(channel.app_id, "1905684026")
        self.assertEqual(channel.group_openids, ["GROUP_A", "GROUP_B"])
        self.assertEqual(channel.api_base, "https://sandbox.api.sgroup.qq.com")

    def test_from_env_defaults_to_official_api(self):
        env = {"QQ_BOT_APP_ID": "1", "QQ_BOT_APP_SECRET": "s", "QQ_BOT_GROUP_OPENIDS": "G1"}
        with patch.dict(os.environ, env, clear=True):
            channel = QQBotChannel.from_env()
        self.assertEqual(channel.api_base, QQ_API_BASE)

    def test_requires_app_id(self):
        with self.assertRaises(ValueError):
            QQBotChannel("", "secret", ["G1"])

    def test_requires_app_secret(self):
        with self.assertRaises(ValueError):
            QQBotChannel("1", "", ["G1"])

    def test_requires_group_openids(self):
        with self.assertRaises(ValueError):
            QQBotChannel("1", "secret", [])


class QQSendTests(unittest.TestCase):
    def test_send_fetches_token_then_posts_text(self):
        session = Mock()
        session.post.side_effect = [
            make_response(json_data={"access_token": "tok-1", "expires_in": "7200"}),
            make_response(json_data={"id": "msg-1"}),
        ]
        channel = make_channel(session)
        channel.send(make_item(), content_mode="full")

        token_call, message_call = session.post.call_args_list
        self.assertEqual(token_call.args[0], QQ_TOKEN_URL)
        self.assertEqual(token_call.kwargs["json"], {"appId": "1905684026", "clientSecret": "secret"})

        self.assertEqual(message_call.args[0], f"{QQ_API_BASE}/v2/groups/GROUP_A/messages")
        self.assertEqual(message_call.kwargs["headers"]["Authorization"], "QQBot tok-1")
        payload = message_call.kwargs["json"]
        self.assertEqual(payload["msg_type"], 0)
        self.assertIsInstance(payload["msg_seq"], int)
        self.assertIn("大黑AI速报", payload["content"])
        self.assertIn("新模型发布", payload["content"])
        self.assertIn("https://source.example", payload["content"])

    def test_token_is_cached_across_sends(self):
        session = Mock()
        session.post.side_effect = [
            make_response(json_data={"access_token": "tok-1"}),
            make_response(json_data={"id": "m1"}),
            make_response(json_data={"id": "m2"}),
        ]
        channel = make_channel(session)
        channel.send(make_item(), content_mode="full")
        channel.send(make_item(), content_mode="full")
        # 第 1 次调用是签发令牌，之后两次都是发消息：令牌只取一次。
        self.assertEqual(session.post.call_count, 3)

    def test_sends_to_all_groups(self):
        session = Mock()
        session.post.side_effect = [
            make_response(json_data={"access_token": "tok-1"}),
            make_response(json_data={"id": "m1"}),
            make_response(json_data={"id": "m2"}),
        ]
        channel = make_channel(session, group_openids=["GROUP_A", "GROUP_B"])
        channel.send(make_item(), content_mode="full")
        urls = [call.args[0] for call in session.post.call_args_list[1:]]
        self.assertEqual(
            urls,
            [
                f"{QQ_API_BASE}/v2/groups/GROUP_A/messages",
                f"{QQ_API_BASE}/v2/groups/GROUP_B/messages",
            ],
        )

    def test_oversized_content_degrades_to_summary(self):
        long_entries = "".join(
            f"<li><strong>[行业资讯] 条目{i}</strong><br/>{'内容' * 200}</li>" for i in range(120)
        )
        item = make_item()
        item = FeedItem(
            guid=item.guid,
            title=item.title,
            link=item.link,
            summary=item.summary,
            content_html=f"<ul>{long_entries}</ul>",
            published="",
        )
        session = Mock()
        session.post.side_effect = [
            make_response(json_data={"access_token": "tok-1"}),
            make_response(json_data={"id": "m1"}),
        ]
        channel = make_channel(session)
        channel.send(item, content_mode="full")

        payload = session.post.call_args_list[1].kwargs["json"]
        self.assertLess(len(payload["content"]), 2_500)
        self.assertNotIn("【行业资讯】", payload["content"])

    def test_http_error_raises_push_error(self):
        session = Mock()
        session.post.side_effect = [
            make_response(json_data={"access_token": "tok-1"}),
            make_response(status_code=400, text='{"message":"主动消息未开通"}'),
        ]
        channel = make_channel(session)
        with self.assertRaises(PushError) as ctx:
            channel.send(make_item(), content_mode="full")
        self.assertIn("HTTP 400", str(ctx.exception))
        self.assertIn("主动消息未开通", str(ctx.exception))

    def test_token_without_access_token_raises(self):
        session = Mock()
        session.post.return_value = make_response(json_data={"message": "invalid appid"})
        channel = make_channel(session)
        with self.assertRaises(PushError) as ctx:
            channel.send(make_item(), content_mode="full")
        self.assertIn("未返回令牌", str(ctx.exception))

    def test_network_error_raises_push_error(self):
        session = Mock()
        session.post.side_effect = [
            make_response(json_data={"access_token": "tok-1"}),
            requests.RequestException("boom"),
        ]
        channel = make_channel(session)
        with self.assertRaises(PushError):
            channel.send(make_item(), content_mode="full")


if __name__ == "__main__":
    unittest.main()
