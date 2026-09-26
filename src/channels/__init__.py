"""Push channel registry: every notification destination lives in this package."""

from __future__ import annotations

from typing import Any

from .base import PushChannel, PushError
from .wxpusher import WxPusherChannel


CHANNELS: dict[str, Any] = {
    "wxpusher": WxPusherChannel,
}
CHANNEL_NAMES = tuple(CHANNELS)


def parse_push_channels(raw: str | None) -> list[str]:
    """Parse PUSH_CHANNELS; unset/blank keeps the legacy wxpusher-only behaviour."""
    if raw is None or not raw.strip():
        return ["wxpusher"]
    names: list[str] = []
    for part in raw.split(","):
        part = part.strip().lower()
        if not part:
            continue
        if part not in CHANNELS:
            raise ValueError(f"未知推送通道: {part}（支持: {', '.join(CHANNEL_NAMES)}）")
        if part not in names:
            names.append(part)
    if not names:
        raise ValueError("PUSH_CHANNELS 不能全部为空")
    return names


def create_channel(name: str, *, connect_timeout: float = 8, read_timeout: float = 15) -> PushChannel:
    channel_cls = CHANNELS.get(name)
    if channel_cls is None:
        raise ValueError(f"未知推送通道: {name}（支持: {', '.join(CHANNEL_NAMES)}）")
    return channel_cls.from_env(connect_timeout=connect_timeout, read_timeout=read_timeout)
