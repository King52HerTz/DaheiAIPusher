from __future__ import annotations

import os
import sys
from pathlib import Path

from .feed import DEFAULT_RSS_URL, FeedError, fetch_feed, unseen_items
from .state import PushState, load_state, save_state
from .wxpusher import PushError, WxPusherClient, build_message


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1.0, float(raw))
    except ValueError as exc:
        raise ValueError(f"{name} 必须是数字") from exc


def env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc


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


def run() -> int:
    rss_url = (os.getenv("RSS_URL") or DEFAULT_RSS_URL).strip()
    state_file = Path(os.getenv("STATE_FILE") or "data/state.json")
    dry_run = env_bool("DRY_RUN")
    push_on_first_run = env_bool("PUSH_ON_FIRST_RUN")
    content_mode = (os.getenv("CONTENT_MODE") or "full").strip().lower()
    if content_mode not in {"full", "summary"}:
        raise ValueError("CONTENT_MODE 只能是 full 或 summary")
    max_catchup_items = env_int("MAX_CATCHUP_ITEMS", 6)
    connect_timeout = env_float("HTTP_CONNECT_TIMEOUT", 10)
    read_timeout = env_float("HTTP_READ_TIMEOUT", 20)

    print(f"读取 RSS: {rss_url}")
    items = fetch_feed(
        rss_url,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
    )
    print(f"RSS 中读取到 {len(items)} 期，最新一期：{items[0].title}")

    state = load_state(state_file)
    if not state.last_guid:
        if not push_on_first_run:
            if dry_run:
                print(f"[DRY RUN] 首次运行将建立基线：{items[0].guid}")
            else:
                save_state(state_file, PushState(last_guid=items[0].guid))
                print(f"首次运行已建立基线，不推送历史内容：{items[0].guid}")
            return 0
        pending = [items[0]]
        found_previous = False
    else:
        pending, found_previous = unseen_items(
            items,
            state.last_guid,
            max_catchup_items=max_catchup_items,
        )

    if state.last_guid and not found_previous:
        print(
            "警告：上次 GUID 已不在当前 RSS 中，"
            f"最多补发最新 {max_catchup_items} 期。"
        )

    if not pending:
        print("没有发现新一期，无需推送。")
        return 0

    print(f"发现 {len(pending)} 期待推送内容。")
    if dry_run:
        for item in pending:
            print(f"[DRY RUN] {item.title} | {item.guid} | {item.link}")
        return 0

    app_token = (os.getenv("WXPUSHER_APP_TOKEN") or "").strip()
    uids = [part for part in (os.getenv("WXPUSHER_UID") or "").split(",") if part.strip()]
    topic_ids = env_topic_ids("WXPUSHER_TOPIC_IDS")
    client = WxPusherClient(
        app_token,
        uids,
        topic_ids,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
    )

    for item in pending:
        print(f"正在推送：{item.title} ({item.guid})")
        client.send(build_message(item, content_mode=content_mode))
        save_state(state_file, PushState(last_guid=item.guid))
        print(f"推送成功并更新状态：{item.guid}")
    return 0


def main() -> None:
    try:
        raise SystemExit(run())
    except (FeedError, PushError, RuntimeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
