#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/opt/dahei-ai-pusher"
SERVICE_NAME="dahei-ai-pusher"
LOCK_FILE="/run/lock/${SERVICE_NAME}.lock"

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 root 运行：sudo bash scripts/update_server.sh"
  exit 1
fi

if [[ ! -d "${APP_DIR}/.git" ]]; then
  echo "没有找到 ${APP_DIR}，请先运行服务器安装脚本。"
  exit 1
fi

exec 9>"${LOCK_FILE}"
if ! flock -w 60 9; then
  echo "推送任务仍在运行，本次更新已取消，请稍后重试。"
  exit 1
fi

echo "正在拉取最新代码……"
git -C "${APP_DIR}" fetch origin main
git -C "${APP_DIR}" checkout main
git -C "${APP_DIR}" pull --ff-only origin main

echo "正在同步 Python 依赖……"
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.timer"

echo "✅ 更新完成，私密配置和推送状态均未修改。"
echo "查看日志：journalctl -u ${SERVICE_NAME}.service -n 100 --no-pager"
