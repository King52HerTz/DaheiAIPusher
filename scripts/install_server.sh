#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="https://github.com/King52HerTz/DaheiAIPusher.git"
APP_DIR="/opt/dahei-ai-pusher"
ENV_FILE="/etc/dahei-ai-pusher.env"
STATE_DIR="/var/lib/dahei-ai-pusher"
STATE_FILE="${STATE_DIR}/state.json"
SERVICE_NAME="dahei-ai-pusher"

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 root 运行：sudo bash scripts/install_server.sh"
  exit 1
fi

echo "🐒 大黑 AI 速报服务器安装器"
echo "接下来只需要填写 WxPusher 的 AppToken 和 Topic ID。"
echo

read -r -s -p "WxPusher AppToken（输入时不会显示）: " APP_TOKEN </dev/tty
echo
read -r -p "大黑AI速报 Topic ID（纯数字）: " TOPIC_IDS </dev/tty

if [[ -z "${APP_TOKEN}" ]]; then
  echo "AppToken 不能为空。"
  exit 1
fi

if [[ ! "${TOPIC_IDS}" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
  echo "Topic ID 格式不正确；多个 ID 请使用英文逗号分隔。"
  exit 1
fi

echo
echo "正在安装系统依赖……"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates git python3 python3-pip python3-venv util-linux

echo "正在准备项目代码……"
if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "${APP_DIR}" fetch origin main
  git -C "${APP_DIR}" checkout main
  git -C "${APP_DIR}" pull --ff-only origin main
elif [[ -e "${APP_DIR}" ]]; then
  echo "${APP_DIR} 已存在但不是本项目的 Git 仓库，为避免误删文件，安装已停止。"
  echo "请先检查并处理这个目录，然后重新运行安装器。"
  exit 1
else
  git clone --branch main "${REPO_URL}" "${APP_DIR}"
fi

python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "正在保存私密配置……"
install -d -m 700 "${STATE_DIR}"
if [[ ! -f "${STATE_FILE}" && -f "${APP_DIR}/data/state.json" ]]; then
  install -m 600 "${APP_DIR}/data/state.json" "${STATE_FILE}"
fi

umask 077
cat >"${ENV_FILE}" <<EOF
WXPUSHER_APP_TOKEN='${APP_TOKEN}'
WXPUSHER_UID=''
WXPUSHER_TOPIC_IDS='${TOPIC_IDS}'
CONTENT_MODE='full'
RSS_URL='https://news.daheiai.com/rss.php'
STATE_FILE='${STATE_FILE}'
MAX_CATCHUP_ITEMS='6'
HTTP_CONNECT_TIMEOUT='10'
HTTP_READ_TIMEOUT='20'
EOF
chmod 600 "${ENV_FILE}"
unset APP_TOKEN

echo "正在创建后台任务……"
cat >"/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Dahei AI News WxPusher
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/flock -n /run/lock/${SERVICE_NAME}.lock ${APP_DIR}/.venv/bin/python -m src.main
EOF

cat >"/etc/systemd/system/${SERVICE_NAME}.timer" <<EOF
[Unit]
Description=Check Dahei AI RSS every 15 minutes

[Timer]
OnCalendar=*:0/15
Persistent=true
AccuracySec=1min
Unit=${SERVICE_NAME}.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload

echo "正在进行只检查、不推送测试……"
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a
(
  cd "${APP_DIR}"
  DRY_RUN=true "${APP_DIR}/.venv/bin/python" -m src.main
)

systemctl enable --now "${SERVICE_NAME}.timer"

echo
echo "✅ 安装完成。服务器会每 15 分钟检查一次，只有出现新一期才会调用 WxPusher。"
echo "查看下次运行：systemctl list-timers ${SERVICE_NAME}.timer"
echo "查看运行日志：journalctl -u ${SERVICE_NAME}.service -n 100 --no-pager"
echo "立即正式检查：systemctl start ${SERVICE_NAME}.service"
echo
echo "请先不要删除 GitHub Actions；确认服务器运行正常后，再关闭本仓库的自动排程。"
