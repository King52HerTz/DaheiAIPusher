from __future__ import annotations

import html
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
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


FONT_STACK = "-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif"

CATEGORY_COLORS = {
    "模型动态": ("#ede9fe", "#6d28d9"),
    "产品工具": ("#e0e7ff", "#4338ca"),
    "技巧教程": ("#cffafe", "#0e7490"),
    "硬件动态": ("#fef3c7", "#b45309"),
    "行业资讯": ("#ffe4e6", "#be123c"),
}


def _category_badge(category: str) -> str:
    background, foreground = CATEGORY_COLORS.get(category, ("#e2e8f0", "#475569"))
    return (
        f'<span style="display:inline-block;padding:4px 9px;border-radius:999px;'
        f'background:{background};color:{foreground};font-size:12px;font-weight:700;'
        f'line-height:1.2;letter-spacing:.2px;">{html.escape(category)}</span>'
    )


def _issue_meta(item: FeedItem) -> str:
    match = re.search(r"第\s*(\d+)\s*期\s*[-·]?\s*(.*)", item.title)
    if match:
        issue, timestamp = match.groups()
        parts = [f"第 {issue} 期"]
        if timestamp.strip():
            parts.append(timestamp.strip())
        return " · ".join(parts)
    return item.title


def _style_links(fragment: BeautifulSoup) -> None:
    for link in fragment.find_all("a"):
        link["style"] = (
            "color:#4f46e5;text-decoration:none;font-weight:600;"
            "word-break:break-all;"
        )


def _styled_feed_body(item: FeedItem) -> tuple[str, int]:
    """Convert the predictable RSS list into mobile-friendly news cards."""
    soup = BeautifulSoup(item.content_html, "html.parser")
    list_items = soup.find_all("li")

    summary_text = item.summary
    first_heading = soup.find(["h2", "h3"])
    if first_heading:
        summary_node = first_heading.find_next_sibling("p")
        if summary_node:
            summary_text = summary_node.get_text(" ", strip=True) or summary_text

    cards: list[str] = []
    for index, source_item in enumerate(list_items, start=1):
        fragment = BeautifulSoup(str(source_item), "html.parser")
        li = fragment.find("li")
        if li is None:
            continue

        strong = li.find("strong")
        heading_text = strong.get_text(" ", strip=True) if strong else f"第 {index} 条快讯"
        category_match = re.match(r"^\[([^]]+)]\s*(.*)$", heading_text)
        if category_match:
            category, news_title = category_match.groups()
        else:
            category, news_title = "AI 快讯", heading_text
        if strong:
            strong.extract()

        while li.contents and getattr(li.contents[0], "name", None) == "br":
            li.contents[0].extract()

        _style_links(fragment)
        for small in li.find_all("small"):
            small["style"] = (
                "display:block;margin-top:11px;padding-top:9px;border-top:1px solid #eef2f7;"
                "color:#64748b;font-size:12px;line-height:1.65;"
            )

        description = "".join(str(node) for node in li.contents).strip()
        cards.append(
            '<div style="margin:0 0 12px;padding:16px 16px 15px;background:#ffffff;'
            'border:1px solid #e5e7eb;border-radius:14px;box-shadow:0 3px 12px rgba(15,23,42,.05);">'
            f'<div style="margin-bottom:9px;">{_category_badge(category)}</div>'
            f'<div style="margin-bottom:8px;color:#0f172a;font-size:17px;font-weight:750;'
            f'line-height:1.5;">{html.escape(news_title)}</div>'
            f'<div style="color:#475569;font-size:14px;line-height:1.8;word-break:break-word;">'
            f'{description}</div></div>'
        )

    if not cards:
        _style_links(soup)
        fallback = str(soup)
        cards.append(
            '<div style="padding:17px;background:#ffffff;border:1px solid #e5e7eb;'
            f'border-radius:14px;color:#475569;font-size:14px;line-height:1.85;">{fallback}</div>'
        )

    summary_card = (
        '<div style="margin:14px 0 18px;padding:16px 17px;background:#eef2ff;'
        'border:1px solid #c7d2fe;border-left:5px solid #6366f1;border-radius:12px;">'
        '<div style="margin-bottom:7px;color:#4338ca;font-size:12px;font-weight:800;'
        'letter-spacing:1px;">本期重点</div>'
        f'<div style="color:#273253;font-size:15px;line-height:1.8;">'
        f'{html.escape(summary_text)}</div></div>'
    )
    section_header = (
        '<div style="margin:2px 2px 12px;color:#0f172a;font-size:18px;font-weight:800;">'
        f'本期速览 <span style="color:#94a3b8;font-size:13px;font-weight:600;">'
        f'· {len(cards)} 条</span></div>'
    )
    return f"{summary_card}{section_header}{''.join(cards)}", len(cards)


def build_message(item: FeedItem, *, content_mode: str = "full") -> PushMessage:
    content_mode = content_mode.strip().lower()
    if content_mode not in {"full", "summary"}:
        raise ValueError("CONTENT_MODE 只能是 full 或 summary")

    link = html.escape(item.link, quote=True)
    meta = html.escape(_issue_meta(item))
    header = (
        f'<div style="font-family:{FONT_STACK};width:100%;max-width:680px;box-sizing:border-box;'
        'margin:0 auto;padding:14px;'
        'background:#f4f7fb;color:#172033;">'
        '<div style="padding:23px 21px 21px;border-radius:18px;'
        'background:linear-gradient(135deg,#111827 0%,#312e81 52%,#2563eb 100%);'
        'box-shadow:0 10px 24px rgba(49,46,129,.2);color:#ffffff;">'
        '<div style="margin-bottom:16px;">'
        '<span style="display:inline-block;padding:5px 10px;border:1px solid rgba(255,255,255,.3);'
        'border-radius:999px;background:rgba(255,255,255,.12);font-size:11px;font-weight:800;'
        'letter-spacing:1.2px;">⚡ AI NEWS · 4H UPDATE</span></div>'
        '<div style="font-size:27px;font-weight:850;line-height:1.25;letter-spacing:.5px;">'
        '大黑AI速报</div>'
        f'<div style="margin-top:8px;color:#dbeafe;font-size:13px;line-height:1.5;">{meta}</div>'
        '</div>'
    )
    footer = (
        '<div style="margin-top:18px;padding:18px 16px;border-radius:14px;background:#ffffff;'
        'border:1px solid #e5e7eb;text-align:center;">'
        f'<a href="{link}" style="display:block;padding:13px 18px;border-radius:10px;'
        'background:#4f46e5;color:#ffffff;text-decoration:none;font-size:15px;font-weight:800;">'
        '打开网站查看完整速报 →</a>'
        '<div style="margin-top:12px;color:#94a3b8;font-size:11px;line-height:1.6;">'
        '内容来源：大黑AI速报 · 每4小时自动更新</div></div></div>'
    )

    if content_mode == "summary":
        body = (
            '<div style="margin:14px 0;padding:17px;background:#ffffff;border:1px solid #e5e7eb;'
            'border-left:5px solid #6366f1;border-radius:12px;">'
            '<div style="margin-bottom:7px;color:#4338ca;font-size:12px;font-weight:800;">本期重点</div>'
            f'<div style="color:#334155;font-size:15px;line-height:1.8;">'
            f'{html.escape(item.summary)}</div></div>'
        )
    else:
        body, _ = _styled_feed_body(item)

    full_content = f"{header}{body}{footer}"
    if len(full_content) > FULL_CONTENT_SOFT_LIMIT:
        safe_summary = item.summary or "本期内容较长，请点击下方链接查看完整速报。"
        full_content = f"{header}<p>{html.escape(safe_summary)}</p>{footer}"

    if len(full_content) > MAX_WXPUSHER_CONTENT_LENGTH:
        raise PushError("生成的推送内容超过 WxPusher 40000 字符限制")

    return PushMessage(
        summary=f"⚡ 大黑AI速报｜{item.title}"[:100],
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
