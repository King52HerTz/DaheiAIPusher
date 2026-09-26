import os
import unittest
from unittest.mock import Mock, patch

from src.channels.base import PushError
from src.channels.email import EmailChannel
from src.feed import FeedItem


def make_item() -> FeedItem:
    return FeedItem(
        guid="issue-1",
        title="第1期",
        link="https://example.com/1",
        summary="摘要",
        content_html="<p>内容</p>",
        published="",
    )


def make_channel(**overrides) -> EmailChannel:
    config = dict(
        smtp_host="smtp.qq.com",
        smtp_port=465,
        use_ssl=True,
        username="sender@qq.com",
        password="auth-code",
        recipients=["reader@qq.com"],
    )
    config.update(overrides)
    return EmailChannel(**config)


class EmailConfigTests(unittest.TestCase):
    def test_from_env_uses_qq_defaults(self):
        env = {
            "EMAIL_SMTP_USER": "sender@qq.com",
            "EMAIL_SMTP_AUTH_CODE": "auth-code",
            "EMAIL_TO": "reader@qq.com",
        }
        with patch.dict(os.environ, env, clear=True):
            channel = EmailChannel.from_env()
        self.assertEqual(channel.smtp_host, "smtp.qq.com")
        self.assertEqual(channel.smtp_port, 465)
        self.assertTrue(channel.use_ssl)
        self.assertEqual(channel.sender, "sender@qq.com")

    def test_from_env_parses_custom_values(self):
        env = {
            "EMAIL_SMTP_HOST": "smtp.163.com",
            "EMAIL_SMTP_PORT": "587",
            "EMAIL_SMTP_SSL": "false",
            "EMAIL_SMTP_USER": "sender@163.com",
            "EMAIL_SMTP_AUTH_CODE": "auth-code",
            "EMAIL_TO": "a@x.com, b@x.com",
            "EMAIL_FROM": "noreply@163.com",
        }
        with patch.dict(os.environ, env, clear=True):
            channel = EmailChannel.from_env()
        self.assertEqual(channel.smtp_host, "smtp.163.com")
        self.assertEqual(channel.smtp_port, 587)
        self.assertFalse(channel.use_ssl)
        self.assertEqual(channel.recipients, ["a@x.com", "b@x.com"])
        self.assertEqual(channel.sender, "noreply@163.com")

    def test_from_env_rejects_invalid_port(self):
        env = {
            "EMAIL_SMTP_PORT": "not-a-number",
            "EMAIL_SMTP_USER": "sender@qq.com",
            "EMAIL_SMTP_AUTH_CODE": "auth-code",
            "EMAIL_TO": "reader@qq.com",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError):
                EmailChannel.from_env()

    def test_requires_username(self):
        with self.assertRaises(ValueError):
            make_channel(username="  ")

    def test_requires_password(self):
        with self.assertRaises(ValueError):
            make_channel(password="")

    def test_requires_recipients(self):
        with self.assertRaises(ValueError):
            make_channel(recipients=[])


class EmailSendTests(unittest.TestCase):
    @patch("src.channels.email.smtplib.SMTP_SSL")
    def test_send_delivers_html_message_with_headers(self, smtp_ssl_mock):
        server = smtp_ssl_mock.return_value.__enter__.return_value
        channel = make_channel()
        channel.send(make_item(), content_mode="summary")

        server.login.assert_called_once_with("sender@qq.com", "auth-code")
        email = server.send_message.call_args.args[0]
        self.assertEqual(email["Subject"], "⚡ 大黑AI速报｜第1期")
        self.assertEqual(email["From"], "大黑AI速报 <sender@qq.com>")
        self.assertEqual(email["To"], "reader@qq.com")
        content = email.get_content()
        self.assertEqual(email.get_content_type(), "text/html")
        self.assertIn("大黑 AI 速报", content)

    @patch("src.channels.email.smtplib.SMTP")
    def test_plain_mode_uses_starttls(self, smtp_mock):
        server = smtp_mock.return_value.__enter__.return_value
        channel = make_channel(use_ssl=False, smtp_port=587)
        channel.send(make_item(), content_mode="full")

        smtp_mock.assert_called_once()
        server.starttls.assert_called_once()
        server.login.assert_called_once()

    @patch("src.channels.email.smtplib.SMTP_SSL")
    def test_send_failure_raises_push_error(self, smtp_ssl_mock):
        server = smtp_ssl_mock.return_value.__enter__.return_value
        server.login.side_effect = OSError("connection refused")
        channel = make_channel()
        with self.assertRaises(PushError):
            channel.send(make_item(), content_mode="full")


if __name__ == "__main__":
    unittest.main()
