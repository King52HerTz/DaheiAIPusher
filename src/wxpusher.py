from __future__ import annotations

import html
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .feed import FeedItem


WXPUSHER_API_URL = "https://wxpusher.zjiecode.com/api/send/message"
MAX_WXPUSHER_CONTENT_LENGTH = 40_000
FULL_CONTENT_SOFT_LIMIT = 38_000


class PushError(RuntimeError):
    """Raised when WxPusher does not accept a message."""


@dataclass(frozen=True)
class PushMessage:
    summary: str
    content: str
    url: str


def build_message(item: FeedItem, *, content_mode: str = "full") -> PushMessage:
    content_mode = content_mode.strip().lower()
    if content_mode not in {"full", "summary"}:
        raise ValueError("CONTENT_MODE 只能是 full 或 summary")

    title = html.escape(item.title)
    link = html.escape(item.link, quote=True)
    published = html.escape(item.published)
    header = f"<h2>大黑AI速报 · {title}</h2>"
    if published:
        header += f"<p><small>{published}</small></p>"
    footer = (
        f'<hr/><p><a href="{link}">查看本期完整速报</a></p>'
        "<p><small>内容来源：大黑AI速报</small></p>"
    )

    if content_mode == "summary":
        body = f"<p>{html.escape(item.summary)}</p>"
    else:
        body = item.content_html

    full_content = f"{header}{body}{footer}"
    if len(full_content) > FULL_CONTENT_SOFT_LIMIT:
        safe_summary = item.summary or "本期内容较长，请点击下方链接查看完整速报。"
        full_content = f"{header}<p>{html.escape(safe_summary)}</p>{footer}"

    if len(full_content) > MAX_WXPUSHER_CONTENT_LENGTH:
        raise PushError("生成的推送内容超过 WxPusher 40000 字符限制")

    return PushMessage(
        summary=f"大黑AI速报｜{item.title}"[:100],
        content=full_content,
        url=item.link,
    )


class WxPusherClient:
    def __init__(
        self,
        app_token: str,
        uids: list[str] | None = None,
        topic_ids: list[int] | None = None,
        *,
        connect_timeout: float = 8,
        read_timeout: float = 15,
        session: requests.Session | None = None,
    ) -> None:
        self.app_token = app_token.strip()
        self.uids = [uid.strip() for uid in (uids or []) if uid.strip()]
        self.topic_ids = [topic_id for topic_id in (topic_ids or []) if topic_id > 0]
        self.timeout = (connect_timeout, read_timeout)
        self.session = session or self._new_session()

        if not self.app_token:
            raise ValueError("WXPUSHER_APP_TOKEN 不能为空")
        if not self.uids and not self.topic_ids:
            raise ValueError("WXPUSHER_UID 和 WXPUSHER_TOPIC_IDS 至少配置一个")

    @staticmethod
    def _new_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"POST"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        return session

    def send(self, message: PushMessage) -> None:
        payload: dict[str, object] = {
            "appToken": self.app_token,
            "content": message.content,
            "summary": message.summary,
            "contentType": 2,
            "url": message.url,
            "verifyPayType": 0,
        }
        if self.uids:
            payload["uids"] = self.uids
        if self.topic_ids:
            payload["topicIds"] = self.topic_ids
        try:
            response = self.session.post(
                WXPUSHER_API_URL,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PushError(f"WxPusher 请求失败: {exc}") from exc

        if data.get("code") != 1000 or data.get("success") is False:
            raise PushError(f"WxPusher 拒绝消息: {data.get('msg') or data}")

        failed = [
            result
            for result in (data.get("data") or [])
            if result.get("code") != 1000
        ]
        if failed:
            details = "; ".join(
                f"{result.get('uid') or result.get('topicId') or 'unknown'}: "
                f"{result.get('status', '发送失败')}"
                for result in failed
            )
            raise PushError(f"部分接收者推送失败: {details}")
