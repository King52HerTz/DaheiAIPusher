"""WxPusher channel: API client plus the channel adapter."""

from __future__ import annotations

import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..feed import FeedItem
from ..render import PushMessage, build_message
from .base import PushError


WXPUSHER_API_URL = "https://wxpusher.zjiecode.com/api/send/message"
MAX_WXPUSHER_CONTENT_LENGTH = 40_000


def env_topic_ids(name: str) -> list[int]:
    values: list[int] = []
    for part in (os.getenv(name) or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            topic_id = int(part)
        except ValueError as exc:
            raise ValueError(f"{name} 必须是用英文逗号分隔的正整数") from exc
        if topic_id <= 0:
            raise ValueError(f"{name} 必须是用英文逗号分隔的正整数")
        values.append(topic_id)
    return values


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
        if len(message.content) > MAX_WXPUSHER_CONTENT_LENGTH:
            raise PushError("生成的推送内容超过 WxPusher 40000 字符限制")
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


class WxPusherChannel:
    name = "wxpusher"

    def __init__(self, client: WxPusherClient) -> None:
        self.client = client

    @classmethod
    def from_env(cls, *, connect_timeout: float = 8, read_timeout: float = 15) -> "WxPusherChannel":
        app_token = (os.getenv("WXPUSHER_APP_TOKEN") or "").strip()
        uids = [part.strip() for part in (os.getenv("WXPUSHER_UID") or "").split(",") if part.strip()]
        topic_ids = env_topic_ids("WXPUSHER_TOPIC_IDS")
        client = WxPusherClient(
            app_token,
            uids,
            topic_ids,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )
        return cls(client)

    def send(self, item: FeedItem, *, content_mode: str) -> None:
        self.client.send(build_message(item, content_mode=content_mode))
