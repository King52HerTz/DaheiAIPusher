from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import feedparser
import requests


DEFAULT_RSS_URL = "https://news.daheiai.com/rss.php"


class FeedError(RuntimeError):
    """Raised when the RSS feed cannot be downloaded or parsed."""


@dataclass(frozen=True)
class FeedItem:
    guid: str
    title: str
    link: str
    summary: str
    content_html: str
    published: str


def parse_feed(raw_feed: bytes | str) -> list[FeedItem]:
    parsed = feedparser.parse(raw_feed)
    if parsed.bozo and not parsed.entries:
        raise FeedError(f"RSS 解析失败: {parsed.bozo_exception}")

    items: list[FeedItem] = []
    for entry in parsed.entries:
        guid = str(entry.get("id") or entry.get("guid") or entry.get("link") or "").strip()
        link = str(entry.get("link") or "").strip()
        if not guid or not link:
            continue

        content_html = ""
        contents = entry.get("content") or []
        if contents:
            content_html = str(contents[0].get("value") or "").strip()

        summary = str(entry.get("summary") or entry.get("description") or "").strip()
        if not content_html:
            content_html = summary

        items.append(
            FeedItem(
                guid=guid,
                title=str(entry.get("title") or "大黑AI速报").strip(),
                link=link,
                summary=summary,
                content_html=content_html,
                published=str(entry.get("published") or "").strip(),
            )
        )

    if not items:
        raise FeedError("RSS 中没有可用的期刊条目")
    return items


def fetch_feed(
    url: str = DEFAULT_RSS_URL,
    *,
    connect_timeout: float = 10,
    read_timeout: float = 20,
) -> list[FeedItem]:
    headers = {
        "User-Agent": "DaheiPusher/1.0 (+https://news.daheiai.com/)",
        "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    }
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=(connect_timeout, read_timeout),
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FeedError(f"RSS 下载失败: {exc}") from exc
    return parse_feed(response.content)


def unseen_items(
    items: Iterable[FeedItem],
    last_guid: str | None,
    *,
    max_catchup_items: int = 6,
) -> tuple[list[FeedItem], bool]:
    """Return unseen items oldest-first and whether the prior GUID was found.

    RSS feeds are expected to be ordered newest-first. If a non-empty prior GUID
    has fallen out of the feed, only the newest ``max_catchup_items`` are used to
    prevent an accidental notification flood.
    """
    feed_items = list(items)
    if not feed_items or not last_guid:
        return [], False

    for index, item in enumerate(feed_items):
        if item.guid == last_guid:
            return list(reversed(feed_items[:index])), True

    limit = max(1, max_catchup_items)
    return list(reversed(feed_items[:limit])), False

