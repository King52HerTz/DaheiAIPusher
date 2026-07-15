from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PushState:
    last_guid: str | None = None


def load_state(path: str | Path) -> PushState:
    state_path = Path(path)
    if not state_path.exists():
        return PushState()

    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"状态文件读取失败 {state_path}: {exc}") from exc

    last_guid = data.get("last_guid")
    if last_guid is not None and not isinstance(last_guid, str):
        raise RuntimeError(f"状态文件格式错误 {state_path}: last_guid 必须是字符串或 null")
    return PushState(last_guid=last_guid)


def save_state(path: str | Path, state: PushState) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    payload = json.dumps(
        {"last_guid": state.last_guid},
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    try:
        temp_path.write_text(payload, encoding="utf-8")
        os.replace(temp_path, state_path)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"状态文件保存失败 {state_path}: {exc}") from exc

