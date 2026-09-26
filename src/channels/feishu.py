"""Feishu channel: posts an interactive message card via a custom group bot."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..feed import FeedItem
from ..render import CATEGORY_ORDER, NewsEntry, issue_meta, parse_news
from .base import PushError


CARD_SIZE_LIMIT = 28_000


def feishu_sign(secret: str, timestamp: int) -> str:
    # 飞书官方约定的特殊算法：把 "{timestamp}\n{secret}" 整串当作 HMAC-SHA256 的
    # key、对空内容签名，再 base64；与钉钉（secret 作 key）相反，不能凭直觉实现。
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def _md_summary(text: str) -> str:
    return re.sub(r"\[([^\]\n]{1,80})\]", r"**\1**", text or "（本期无摘要）")


def _entry_markdown(entry: NewsEntry) -> str:
    lines = [f"**{entry.index:02d} {entry.title}**"]
    description = BeautifulSoup(entry.description, "html.parser").get_text(" ", strip=True)
    if description:
        lines.append(description)
    if entry.source_url:
        source_name = entry.source_name or "查看信源"
        lines.append(f"[{source_name} ↗]({entry.source_url})")
    return "\n".join(lines)


def build_card(item: FeedItem, *, content_mode: str = "full") -> dict:
    summary_text, entries = parse_news(item)
    elements: list[dict] = [
        {"tag": "div", "text": {"tag": "lark_md", "content": f"**◆ AI 总结**\n{_md_summary(summary_text)}"}},
    ]

    if content_mode != "summary" and entries:
        groups: dict[str, list[NewsEntry]] = {}
        for entry in entries:
            groups.setdefault(entry.category, []).append(entry)
        category_rank = {name: index for index, name in enumerate(CATEGORY_ORDER)}
        for category in sorted(groups, key=lambda name: category_rank.get(name, len(CATEGORY_ORDER))):
            category_entries = groups[category]
            elements.append({"tag": "hr"})
            elements.append(
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**{category}（{len(category_entries)} 条）**"},
                }
            )
            elements.extend(
                {"tag": "div", "text": {"tag": "lark_md", "content": _entry_markdown(entry)}}
                for entry in category_entries
            )

    elements.append({"tag": "hr"})
    elements.append(
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "去原网页看完整速报 →"},
                    "type": "primary",
                    "url": item.link,
                }
            ],
        }
    )
    elements.append(
        {"tag": "note", "elements": [{"tag": "plain_text", "content": "DaheiAIPusher 自动转发 · 每 4 小时更新"}]}
    )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {"tag": "plain_text", "content": f"⚡ 大黑AI速报 · {issue_meta(item)}"},
        },
        "elements": elements,
    }


class FeishuChannel:
    name = "feishu"

    def __init__(
        self,
        webhook_url: str,
        secret: str = "",
        *,
        connect_timeout: float = 8,
        read_timeout: float = 15,
        session: requests.Session | None = None,
    ) -> None:
        self.webhook_url = webhook_url.strip()
        self.secret = secret.strip()
        self.timeout = (connect_timeout, read_timeout)
        self.session = session or self._new_session()
        if not self.webhook_url:
            raise ValueError("FEISHU_WEBHOOK_URL 不能为空")

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
    def from_env(cls, *, connect_timeout: float = 8, read_timeout: float = 15) -> "FeishuChannel":
        return cls(
            os.getenv("FEISHU_WEBHOOK_URL") or "",
            os.getenv("FEISHU_SECRET") or "",
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )

    def send(self, item: FeedItem, *, content_mode: str) -> None:
        card = build_card(item, content_mode=content_mode)
        if len(json.dumps(card, ensure_ascii=False)) > CARD_SIZE_LIMIT:
            card = build_card(item, content_mode="summary")

        payload: dict[str, object] = {"msg_type": "interactive", "card": card}
        if self.secret:
            timestamp = int(time.time())
            payload["timestamp"] = str(timestamp)
            payload["sign"] = feishu_sign(self.secret, timestamp)

        try:
            response = self.session.post(self.webhook_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PushError(f"飞书请求失败: {exc}") from exc

        code = data.get("code", data.get("StatusCode"))
        if code != 0:
            raise PushError(f"飞书拒绝消息: {data.get('msg') or data.get('StatusMessage') or data}")
