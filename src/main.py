from __future__ import annotations

import os
import sys
from pathlib import Path

from .channels import PushChannel, PushError, create_channel, parse_push_channels
from .feed import DEFAULT_RSS_URL, FeedError, fetch_feed, unseen_items
from .state import PushState, load_state, save_state


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


def run() -> int:
    rss_url = (os.getenv("RSS_URL") or DEFAULT_RSS_URL).strip()
    state_file = Path(os.getenv("STATE_FILE") or "data/state.json")
    dry_run = env_bool("DRY_RUN")
    push_on_first_run = env_bool("PUSH_ON_FIRST_RUN")
    force_push_latest = env_bool("FORCE_PUSH_LATEST")
    content_mode = (os.getenv("CONTENT_MODE") or "full").strip().lower()
    if content_mode not in {"full", "summary"}:
        raise ValueError("CONTENT_MODE 只能是 full 或 summary")
    max_catchup_items = env_int("MAX_CATCHUP_ITEMS", 6)
    connect_timeout = env_float("HTTP_CONNECT_TIMEOUT", 10)
    read_timeout = env_float("HTTP_READ_TIMEOUT", 20)

    channel_names = parse_push_channels(os.getenv("PUSH_CHANNELS"))
    print(f"启用推送通道: {', '.join(channel_names)}")

    print(f"读取 RSS: {rss_url}")
    items = fetch_feed(
        rss_url,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
    )
    print(f"RSS 中读取到 {len(items)} 期，最新一期：{items[0].title}")

    state = load_state(state_file)
    # 回退游标在循环前快照：否则先推送的通道会推进全局 last_guid，
    # 让依赖全局游标的新通道误判"没有新内容"。
    fallback_state = PushState(last_guid=state.last_guid, channels=dict(state.channels))
    channels: dict[str, PushChannel] = {}

    def get_channel(name: str) -> PushChannel:
        # 懒加载：只在真的要发送时才读取并校验该通道的配置，
        # 保证 DRY_RUN / 首次基线在没有任何密钥时也能运行。
        if name not in channels:
            channels[name] = create_channel(
                name,
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
            )
        return channels[name]

    errors: list[str] = []

    if force_push_latest:
        print("手动测试模式：强制重发最新一期，推送后不修改去重状态。")
        if dry_run:
            print(f"[DRY RUN] {items[0].title} | {items[0].guid} | {items[0].link}")
            return 0
        for name in channel_names:
            try:
                print(f"[{name}] 正在推送：{items[0].title} ({items[0].guid})")
                get_channel(name).send(items[0], content_mode=content_mode)
                print(f"[{name}] 测试推送成功，去重状态保持不变")
            except (PushError, ValueError) as exc:
                errors.append(f"{name}: {exc}")
                print(f"[{name}] 推送失败：{exc}", file=sys.stderr)
        if errors:
            raise RuntimeError("；".join(errors))
        return 0

    any_pending = False
    for name in channel_names:
        cursor = fallback_state.cursor_for(name)
        if cursor is None:
            if not push_on_first_run:
                if dry_run:
                    print(f"[DRY RUN] 通道 {name} 首次运行将建立基线：{items[0].guid}")
                else:
                    state.channels[name] = items[0].guid
                    save_state(state_file, state)
                    print(f"通道 {name} 首次运行已建立基线，不推送历史内容：{items[0].guid}")
                continue
            pending, found_previous = [items[0]], False
        else:
            pending, found_previous = unseen_items(
                items,
                cursor,
                max_catchup_items=max_catchup_items,
            )
            if not found_previous:
                print(
                    f"警告[{name}]：上次推送的期号已不在当前 RSS 中，"
                    f"最多补发最新 {max_catchup_items} 期。"
                )

        if not pending:
            print(f"通道 {name}：没有发现新一期。")
            continue

        any_pending = True
        if dry_run:
            for item in pending:
                print(f"[DRY RUN][{name}] {item.title} | {item.guid} | {item.link}")
            continue

        try:
            for item in pending:
                print(f"[{name}] 正在推送：{item.title} ({item.guid})")
                get_channel(name).send(item, content_mode=content_mode)
                state.channels[name] = item.guid
                state.last_guid = item.guid
                save_state(state_file, state)
                print(f"[{name}] 推送成功并更新状态：{item.guid}")
        except (PushError, ValueError) as exc:
            errors.append(f"{name}: {exc}")
            print(f"[{name}] 推送失败：{exc}", file=sys.stderr)

    if errors:
        raise RuntimeError("；".join(errors))
    if not any_pending:
        print("没有发现新一期，无需推送。")
    return 0


def main() -> None:
    try:
        raise SystemExit(run())
    except (FeedError, PushError, RuntimeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
