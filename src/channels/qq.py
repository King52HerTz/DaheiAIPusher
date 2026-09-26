"""QQ 官方群机器人通道：通过开放平台 API 向群聊发送纯文本速报。"""

from __future__ import annotations

import itertools
import os
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..feed import FeedItem
from ..render import build_text_message
from .base import PushError


QQ_TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
QQ_API_BASE = "https://api.sgroup.qq.com"

# 官方未公布群文本消息的精确长度上限，这里保守设置：
# 超过软限自动降级为摘要版；降级后仍超硬限则报错（内容极端时宁可报错也不发半截）。
QQ_TEXT_SOFT_LIMIT = 2_500
QQ_TEXT_HARD_LIMIT = 4_500


def _error_snippet(response: requests.Response) -> str:
    try:
        return response.text[:200]
    except Exception:  # pragma: no cover - response.text 极少抛错
        return "<无响应体>"


class QQBotChannel:
    """通过 QQ 开放平台机器人 API 向群聊推送。

    - 鉴权：appId + clientSecret 换 access_token（约 2 小时有效，每次运行现取并缓存）；
    - 发送：POST /v2/groups/{group_openid}/messages，msg_type=0 纯文本；
    - group_openid 不是群号，只能从机器人收到的事件里拿到（scripts/dev/listen_qq.py 可采集）；
    - 主动消息需要开放平台审核开通额度，未开通时接口会拒绝（错误原文会带出便于排查）。
    """

    name = "qq"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        group_openids: list[str],
        *,
        api_base: str = QQ_API_BASE,
        connect_timeout: float = 8,
        read_timeout: float = 15,
        session: requests.Session | None = None,
    ) -> None:
        self.app_id = app_id.strip()
        self.app_secret = app_secret.strip()
        self.group_openids = [openid.strip() for openid in group_openids if openid.strip()]
        self.api_base = api_base.rstrip("/")
        self.timeout = (connect_timeout, read_timeout)
        self.session = session or self._new_session()
        self._token: str | None = None
        # 主动消息要求 msg_seq 递增区分内容相同的消息；用当前秒数做起点足够。
        self._msg_seq = itertools.count(int(time.time()))

        if not self.app_id:
            raise ValueError("QQ_BOT_APP_ID 不能为空")
        if not self.app_secret:
            raise ValueError("QQ_BOT_APP_SECRET 不能为空")
        if not self.group_openids:
            raise ValueError("QQ_BOT_GROUP_OPENIDS 不能为空")

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

    @classmethod
    def from_env(cls, *, connect_timeout: float = 8, read_timeout: float = 15) -> "QQBotChannel":
        openids = [part for part in (os.getenv("QQ_BOT_GROUP_OPENIDS") or "").split(",")]
        return cls(
            os.getenv("QQ_BOT_APP_ID") or "",
            os.getenv("QQ_BOT_APP_SECRET") or "",
            openids,
            api_base=(os.getenv("QQ_BOT_API_BASE") or "").strip() or QQ_API_BASE,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )

    def _fetch_token(self) -> str:
        try:
            response = self.session.post(
                QQ_TOKEN_URL,
                json={"appId": self.app_id, "clientSecret": self.app_secret},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PushError(f"QQ 开放平台签发令牌失败: {exc}") from exc
        token = data.get("access_token")
        if not token:
            raise PushError(f"QQ 开放平台未返回令牌: {data}")
        self._token = str(token)
        return self._token

    def send(self, item: FeedItem, *, content_mode: str) -> None:
        text = build_text_message(item, content_mode=content_mode)
        if len(text) > QQ_TEXT_SOFT_LIMIT:
            text = build_text_message(item, content_mode="summary")
        if len(text) > QQ_TEXT_HARD_LIMIT:
            raise PushError(f"QQ 群消息超过 {QQ_TEXT_HARD_LIMIT} 字符硬限，摘要降级后仍超限")

        token = self._token or self._fetch_token()
        for group_openid in self.group_openids:
            self._post_group_message(token, group_openid, text)

    def _post_group_message(self, token: str, group_openid: str, text: str) -> None:
        payload = {"content": text, "msg_type": 0, "msg_seq": next(self._msg_seq)}
        url = f"{self.api_base}/v2/groups/{group_openid}/messages"
        try:
            response = self.session.post(
                url,
                json=payload,
                headers={"Authorization": f"QQBot {token}"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise PushError(f"QQ 群 {group_openid} 消息发送失败: {exc}") from exc

        if response.status_code >= 400:
            raise PushError(
                f"QQ 群 {group_openid} 消息被拒绝 (HTTP {response.status_code}): {_error_snippet(response)}"
            )
