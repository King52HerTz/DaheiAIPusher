"""Email channel: delivers the styled HTML card via SMTP (defaults tuned for QQ Mail)."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from ..feed import FeedItem
from ..render import build_message
from .base import PushError


DEFAULT_SMTP_HOST = "smtp.qq.com"
DEFAULT_SMTP_PORT = 465


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class EmailChannel:
    name = "email"

    def __init__(
        self,
        *,
        smtp_host: str,
        smtp_port: int,
        use_ssl: bool,
        username: str,
        password: str,
        recipients: list[str],
        sender: str | None = None,
        connect_timeout: float = 8,
        read_timeout: float = 15,
    ) -> None:
        self.smtp_host = smtp_host.strip()
        self.smtp_port = smtp_port
        self.use_ssl = use_ssl
        self.username = username.strip()
        self.password = password
        self.recipients = [address.strip() for address in recipients if address.strip()]
        self.sender = (sender or self.username).strip()
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

        if not self.smtp_host:
            raise ValueError("EMAIL_SMTP_HOST 不能为空")
        if not (0 < self.smtp_port < 65536):
            raise ValueError("EMAIL_SMTP_PORT 必须是 1-65535 之间的端口号")
        if not self.username:
            raise ValueError("EMAIL_SMTP_USER 不能为空")
        if not self.password:
            raise ValueError("EMAIL_SMTP_AUTH_CODE 不能为空（QQ 邮箱需使用授权码，而非登录密码）")
        if not self.sender:
            raise ValueError("发件地址不能为空")
        if not self.recipients:
            raise ValueError("EMAIL_TO 不能为空")

    @classmethod
    def from_env(cls, *, connect_timeout: float = 8, read_timeout: float = 15) -> "EmailChannel":
        port_raw = (os.getenv("EMAIL_SMTP_PORT") or "").strip()
        try:
            smtp_port = int(port_raw) if port_raw else DEFAULT_SMTP_PORT
        except ValueError as exc:
            raise ValueError("EMAIL_SMTP_PORT 必须是整数") from exc
        return cls(
            smtp_host=os.getenv("EMAIL_SMTP_HOST") or DEFAULT_SMTP_HOST,
            smtp_port=smtp_port,
            use_ssl=_env_bool("EMAIL_SMTP_SSL", True),
            username=os.getenv("EMAIL_SMTP_USER") or "",
            password=os.getenv("EMAIL_SMTP_AUTH_CODE") or "",
            recipients=[part for part in (os.getenv("EMAIL_TO") or "").split(",")],
            sender=os.getenv("EMAIL_FROM") or None,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )

    def send(self, item: FeedItem, *, content_mode: str) -> None:
        message = build_message(item, content_mode=content_mode)
        try:
            self._deliver(message)
        except (smtplib.SMTPException, OSError) as exc:
            raise PushError(f"邮件发送失败: {exc}") from exc

    def _deliver(self, message) -> None:
        email = EmailMessage()
        email["Subject"] = message.summary
        email["From"] = formataddr(("大黑AI速报", self.sender))
        email["To"] = ", ".join(self.recipients)
        email.set_content(message.content, subtype="html")

        timeout = self.read_timeout
        if self.use_ssl:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=timeout) as server:
                server.login(self.username, self.password)
                server.send_message(email)
        else:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=timeout) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(self.username, self.password)
                server.send_message(email)
