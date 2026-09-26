import os
import unittest
from unittest.mock import Mock, patch

from src.channels import parse_push_channels
from src.channels.base import PushError
from src.channels.wxpusher import env_topic_ids
from src.feed import FeedItem
from src.main import run
from src.state import PushState


def make_item(guid: str, title: str = "第1期") -> FeedItem:
    return FeedItem(
        guid=guid,
        title=title,
        link=f"https://example.com/{guid}",
        summary="摘要",
        content_html="<p>内容</p>",
        published="",
    )


def make_channel(name: str) -> Mock:
    channel = Mock()
    channel.name = name
    return channel


class PushChannelParsingTests(unittest.TestCase):
    def test_unset_or_blank_keeps_legacy_wxpusher_only(self):
        self.assertEqual(parse_push_channels(None), ["wxpusher"])
        self.assertEqual(parse_push_channels("   "), ["wxpusher"])

    def test_parses_and_deduplicates_multiple_channels(self):
        # email 通道在后续提交才注册，这里临时扩充注册表验证解析逻辑。
        with patch.dict("src.channels.CHANNELS", {"email": object}):
            self.assertEqual(parse_push_channels(" Email , wxpusher , email "), ["email", "wxpusher"])

    def test_rejects_unknown_channel(self):
        with self.assertRaises(ValueError):
            parse_push_channels("email,carrier-pigeon")

    def test_rejects_all_blank_entries(self):
        with self.assertRaises(ValueError):
            parse_push_channels(" , ")


class MainTests(unittest.TestCase):
    def test_topic_ids_support_comma_separated_values(self):
        with patch.dict(os.environ, {"WXPUSHER_TOPIC_IDS": "123, 456"}):
            self.assertEqual(env_topic_ids("WXPUSHER_TOPIC_IDS"), [123, 456])

    def test_topic_ids_reject_invalid_values(self):
        with patch.dict(os.environ, {"WXPUSHER_TOPIC_IDS": "123,abc"}):
            with self.assertRaises(ValueError):
                env_topic_ids("WXPUSHER_TOPIC_IDS")

    @patch("src.main.save_state")
    @patch("src.main.create_channel")
    @patch("src.main.load_state")
    @patch("src.main.fetch_feed")
    def test_force_push_latest_resends_without_changing_state(
        self,
        fetch_feed_mock,
        load_state_mock,
        create_channel_mock,
        save_state_mock,
    ):
        item = make_item("issue-1")
        fetch_feed_mock.return_value = [item]
        load_state_mock.return_value = PushState(last_guid=item.guid)
        channel = make_channel("wxpusher")
        create_channel_mock.return_value = channel
        with patch.dict(os.environ, {"FORCE_PUSH_LATEST": "true"}, clear=True):
            self.assertEqual(run(), 0)

        channel.send.assert_called_once()
        save_state_mock.assert_not_called()

    @patch("src.main.save_state")
    @patch("src.main.create_channel")
    @patch("src.main.load_state")
    @patch("src.main.fetch_feed")
    def test_first_run_establishes_baseline_for_every_channel(
        self,
        fetch_feed_mock,
        load_state_mock,
        create_channel_mock,
        save_state_mock,
    ):
        item = make_item("issue-1")
        fetch_feed_mock.return_value = [item]
        load_state_mock.return_value = PushState()
        wxpusher = make_channel("wxpusher")
        email = make_channel("email")
        create_channel_mock.side_effect = lambda name, **kwargs: {"wxpusher": wxpusher, "email": email}[name]
        with patch.dict("src.channels.CHANNELS", {"email": object}):
            with patch.dict(os.environ, {"PUSH_CHANNELS": "wxpusher,email"}, clear=True):
                self.assertEqual(run(), 0)

        wxpusher.send.assert_not_called()
        email.send.assert_not_called()
        saved_state = save_state_mock.call_args.args[1]
        self.assertEqual(saved_state.channels, {"wxpusher": "issue-1", "email": "issue-1"})

    @patch("src.main.save_state")
    @patch("src.main.create_channel")
    @patch("src.main.load_state")
    @patch("src.main.fetch_feed")
    def test_new_channel_falls_back_to_global_cursor_then_records_own(
        self,
        fetch_feed_mock,
        load_state_mock,
        create_channel_mock,
        save_state_mock,
    ):
        items = [make_item("issue-3"), make_item("issue-2"), make_item("issue-1")]
        fetch_feed_mock.return_value = items
        # 旧状态：只有全局游标 issue-1；email 是新通道，应回退到全局游标并补发 2、3 两期。
        load_state_mock.return_value = PushState(
            last_guid="issue-1",
            channels={"wxpusher": "issue-1"},
        )
        wxpusher = make_channel("wxpusher")
        email = make_channel("email")
        create_channel_mock.side_effect = lambda name, **kwargs: {"wxpusher": wxpusher, "email": email}[name]
        with patch.dict("src.channels.CHANNELS", {"email": object}):
            with patch.dict(os.environ, {"PUSH_CHANNELS": "wxpusher,email"}, clear=True):
                self.assertEqual(run(), 0)

        self.assertEqual(wxpusher.send.call_count, 2)
        self.assertEqual(email.send.call_count, 2)
        final_state = save_state_mock.call_args.args[1]
        self.assertEqual(final_state.channels["wxpusher"], "issue-3")
        self.assertEqual(final_state.channels["email"], "issue-3")
        self.assertEqual(final_state.last_guid, "issue-3")

    @patch("src.main.save_state")
    @patch("src.main.create_channel")
    @patch("src.main.load_state")
    @patch("src.main.fetch_feed")
    def test_one_channel_failure_does_not_block_others(
        self,
        fetch_feed_mock,
        load_state_mock,
        create_channel_mock,
        save_state_mock,
    ):
        items = [make_item("issue-2"), make_item("issue-1")]
        fetch_feed_mock.return_value = items
        load_state_mock.return_value = PushState(last_guid="issue-1")
        failing = make_channel("wxpusher")
        failing.send.side_effect = PushError("WxPusher 拒绝消息")
        working = make_channel("email")
        create_channel_mock.side_effect = lambda name, **kwargs: {"wxpusher": failing, "email": working}[name]
        with patch.dict("src.channels.CHANNELS", {"email": object}):
            with patch.dict(os.environ, {"PUSH_CHANNELS": "wxpusher,email"}, clear=True):
                with self.assertRaises(RuntimeError):
                    run()

        failing.send.assert_called_once()
        working.send.assert_called_once()
        # email 推送成功后应记录自己的游标，wxpusher 不得记录。
        final_state = save_state_mock.call_args.args[1]
        self.assertEqual(final_state.channels, {"email": "issue-2"})

    @patch("src.main.create_channel")
    @patch("src.main.load_state")
    @patch("src.main.fetch_feed")
    def test_unknown_channel_in_env_fails_before_fetch(
        self,
        fetch_feed_mock,
        load_state_mock,
        create_channel_mock,
    ):
        with patch.dict(os.environ, {"PUSH_CHANNELS": "carrier-pigeon"}, clear=True):
            with self.assertRaises(ValueError):
                run()
        fetch_feed_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
