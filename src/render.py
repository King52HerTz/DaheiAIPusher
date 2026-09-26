"""Channel-agnostic message rendering shared by every push channel."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .feed import FeedItem


FULL_CONTENT_SOFT_LIMIT = 38_000

FONT_STACK = "-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif"
SERIF_STACK = "'Noto Serif SC','Songti SC','STSong',serif"

CATEGORY_ORDER = ("模型动态", "产品工具", "技巧教程", "硬件动态", "行业资讯", "AI 快讯")


@dataclass(frozen=True)
class PushMessage:
    summary: str
    content: str
    url: str


def issue_meta(item: FeedItem) -> str:
    match = re.search(r"第\s*(\d+)\s*期\s*[-·]?\s*(.*)", item.title)
    if match:
        issue, timestamp = match.groups()
        parts = [f"第 {issue} 期"]
        if timestamp.strip():
            parts.append(timestamp.strip())
        return " · ".join(parts)
    return item.title


def _style_inline_content(fragment: BeautifulSoup) -> None:
    for link in fragment.find_all("a"):
        link["style"] = (
            "color:#e85d04;text-decoration:none;font-weight:700;"
            "word-break:break-all;"
        )
    for strong in fragment.find_all("strong"):
        strong["style"] = "color:#e85d04;font-weight:700;"


def _format_summary(value: str) -> str:
    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    escaped = html.escape(text)
    return re.sub(
        r"\[([^][\n]{1,80})]",
        r'<strong style="color:#e85d04;font-weight:750;">\1</strong>',
        escaped,
    )


@dataclass(frozen=True)
class NewsEntry:
    index: int
    category: str
    title: str
    description: str
    source_name: str
    source_url: str
    source_kind: str


def parse_news(item: FeedItem) -> tuple[str, list[NewsEntry]]:
    """Parse the RSS HTML into (summary text, structured news entries).

    Shared by the HTML renderer and any channel that needs a compact
    representation of the issue (e.g. Feishu cards).
    """
    soup = BeautifulSoup(item.content_html, "html.parser")
    list_items = soup.find_all("li")
    summary_text = item.summary
    first_heading = soup.find(["h2", "h3"])
    if first_heading:
        summary_node = first_heading.find_next_sibling("p")
        if summary_node:
            summary_text = summary_node.get_text(" ", strip=True) or summary_text

    entries: list[NewsEntry] = []
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

        source = li.find("small")
        source_link = source.find("a") if source else None
        source_name = source_link.get_text(" ", strip=True) if source_link else ""
        source_url = str(source_link.get("href") or "") if source_link else ""
        source_text = source.get_text(" ", strip=True) if source else ""
        source_kind_match = re.search(r"\[([^]]+)]\s*$", source_text)
        source_kind = source_kind_match.group(1) if source_kind_match else ""
        if source:
            source.extract()

        while li.contents and getattr(li.contents[0], "name", None) == "br":
            li.contents[0].extract()
        while li.contents and getattr(li.contents[-1], "name", None) == "br":
            li.contents[-1].extract()

        _style_inline_content(fragment)
        description = "".join(str(node) for node in li.contents).strip()
        entries.append(
            NewsEntry(
                index=index,
                category=category,
                title=news_title,
                description=description,
                source_name=source_name,
                source_url=source_url,
                source_kind=source_kind,
            )
        )
    return summary_text, entries


def _source_line(entry: NewsEntry) -> str:
    if not entry.source_url:
        return ""
    source_url = html.escape(entry.source_url, quote=True)
    source_name = html.escape(entry.source_name or "查看原始信源")
    source_kind = (
        f'<span style="margin-left:7px;color:#9a948b;font-size:10px;">'
        f'{html.escape(entry.source_kind)}</span>'
        if entry.source_kind
        else ""
    )
    return (
        '<div style="margin-top:13px;color:#8a847b;font-size:11px;line-height:1.6;">'
        '来源 · '
        f'<a href="{source_url}" style="color:#e85d04;text-decoration:none;font-weight:750;'
        'word-break:break-word;overflow-wrap:anywhere;">'
        f'{source_name} &nbsp;↗</a>{source_kind}</div>'
    )


def _render_entry(entry: NewsEntry) -> str:
    reference = f'#{entry.index:02d}'
    if entry.source_url:
        reference = (
            f'<a href="{html.escape(entry.source_url, quote=True)}" style="color:#e85d04;'
            f'text-decoration:none;">[{entry.index}] &nbsp;查看信源 ↗</a>'
        )
    return (
        '<div style="padding:21px 0 20px;border-bottom:1px solid #e8e3db;">'
        f'<div style="margin-bottom:8px;color:#e85d04;font-family:monospace;font-size:11px;'
        f'font-weight:800;letter-spacing:1px;">{reference}</div>'
        f'<div style="margin-bottom:10px;color:#171717;font-family:{SERIF_STACK};font-size:19px;'
        f'font-weight:900;line-height:1.42;letter-spacing:.1px;word-break:break-word;'
        f'overflow-wrap:anywhere;">{html.escape(entry.title)}</div>'
        '<div style="color:#3f3d39;font-size:14px;line-height:1.8;word-break:break-word;'
        f'overflow-wrap:anywhere;">{entry.description}</div>{_source_line(entry)}</div>'
    )


def _styled_feed_body(item: FeedItem) -> tuple[str, int]:
    """Convert the RSS list into a compact, link-preserving mobile newspaper."""
    summary_text, entries = parse_news(item)

    if not entries:
        soup = BeautifulSoup(item.content_html, "html.parser")
        _style_inline_content(soup)
        fallback = str(soup)
        content = (
            '<div style="padding:25px 20px;color:#3f3d39;font-size:14px;line-height:1.85;">'
            f'{fallback}</div>'
        )
        return f'{_summary_section(summary_text)}{content}', 1

    groups: dict[str, list[NewsEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.category, []).append(entry)
    category_rank = {name: index for index, name in enumerate(CATEGORY_ORDER)}
    categories = sorted(groups, key=lambda name: category_rank.get(name, len(CATEGORY_ORDER)))

    sections: list[str] = []
    for category in categories:
        category_entries = groups[category]
        sections.append(
            '<div style="padding:27px 20px 5px;border-bottom:1px solid #e8e3db;">'
            '<div style="padding-left:11px;border-left:4px solid #171717;color:#171717;'
            f'font-family:{SERIF_STACK};font-size:22px;font-weight:900;line-height:1.25;">'
            f'{html.escape(category)} <span style="color:#aaa39a;font-family:{FONT_STACK};'
            f'font-size:11px;font-weight:600;">{len(category_entries)} 条</span></div>'
            f'{"".join(_render_entry(entry) for entry in category_entries)}</div>'
        )
    return f'{_summary_section(summary_text)}{"".join(sections)}', len(entries)


def _summary_section(summary: str) -> str:
    return (
        '<div style="padding:25px 20px 26px;border-bottom:1px solid #e8e3db;">'
        '<div style="margin-bottom:11px;color:#e85d04;font-size:11px;font-weight:850;'
        'letter-spacing:2px;">◆ AI 总结</div>'
        '<div style="color:#242321;font-size:16px;font-weight:650;line-height:1.78;'
        'word-break:break-word;overflow-wrap:anywhere;">'
        f'{_format_summary(summary)}</div></div>'
    )


def build_message(item: FeedItem, *, content_mode: str = "full") -> PushMessage:
    content_mode = content_mode.strip().lower()
    if content_mode not in {"full", "summary"}:
        raise ValueError("CONTENT_MODE 只能是 full 或 summary")

    link = html.escape(item.link, quote=True)
    meta = html.escape(issue_meta(item))
    header = (
        f'<div style="font-family:{FONT_STACK};width:100%;max-width:680px;box-sizing:border-box;'
        'margin:0 auto;background:#faf9f6;color:#1a1a1a;overflow:hidden;">'
        '<div style="height:5px;background:#ff6b00;font-size:0;line-height:0;">&nbsp;</div>'
        '<div style="padding:23px 20px 22px;border-bottom:2px solid #1a1a1a;">'
        '<div style="margin-bottom:16px;color:#77716a;font-family:monospace;font-size:10px;'
        'font-weight:700;letter-spacing:1.6px;">DAHEI AI BRIEF <span style="color:#ff6b00;">●</span> 4H</div>'
        f'<div style="font-family:{SERIF_STACK};font-size:30px;font-weight:900;line-height:1.2;'
        'letter-spacing:1px;">大黑 AI 速报</div>'
        f'<div style="margin-top:9px;color:#716c65;font-family:monospace;font-size:11px;'
        f'line-height:1.5;">{meta}</div></div>'
    )
    footer = (
        '<div style="padding:27px 20px 30px;text-align:center;">'
        f'<a href="{link}" style="display:block;padding:14px 18px;background:#1a1a1a;color:#ffffff;'
        'text-decoration:none;font-size:14px;font-weight:800;letter-spacing:.3px;">'
        '去原网页看完整速报 &nbsp;→</a>'
        '<div style="margin-top:15px;color:#aaa39a;font-size:10px;line-height:1.7;">'
        '由人工大黑制作<br/>DaheiAIPusher 自动转发 · 每 4 小时更新</div></div></div>'
    )

    if content_mode == "summary":
        body = _summary_section(item.summary)
    else:
        body, _ = _styled_feed_body(item)

    full_content = f"{header}{body}{footer}"
    if len(full_content) > FULL_CONTENT_SOFT_LIMIT:
        safe_summary = item.summary or "本期内容较长，请点击下方链接查看完整速报。"
        full_content = f"{header}<p>{html.escape(safe_summary)}</p>{footer}"

    return PushMessage(
        summary=f"⚡ 大黑AI速报｜{item.title}"[:100],
        content=full_content,
        url=item.link,
    )
