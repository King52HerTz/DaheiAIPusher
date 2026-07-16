# 云服务器部署教程

这套方案适合已经有 Ubuntu / Debian 云服务器，并且希望定时任务比 GitHub Actions 更准的人。

不需要域名、不需要数据库、不需要开放新端口，也不用把 AppToken 写进仓库。服务器只会定时读取大黑 AI 速报的 RSS；发现新一期后，才会调用 WxPusher。

## 需要多少钱

程序、Python、Git 和 systemd 都是免费的。

如果已经有云服务器，一般不需要为本项目额外付费。每 15 分钟读取一次 RSS 所消耗的流量很少，实际是否产生流量费用取决于服务器厂商的带宽计费方式。

## 一键安装

在服务器终端执行：

```bash
curl -fsSL https://raw.githubusercontent.com/King52HerTz/DaheiAIPusher/main/scripts/install_server.sh \
  -o /tmp/install-dahei.sh && sudo bash /tmp/install-dahei.sh
```

如果当前终端已经是 `root`，但系统没有安装 `sudo`：

```bash
bash /tmp/install-dahei.sh
```

安装器只会询问两个内容：

1. WxPusher `AppToken`，输入时不会显示；
2. 接收推送的数字 `Topic ID`。

随后会自动完成：

- 安装 Git、Python 和虚拟环境；
- 把项目安装到 `/opt/dahei-ai-pusher`；
- 把私密配置保存到 `/etc/dahei-ai-pusher.env`；
- 把去重状态保存到 `/var/lib/dahei-ai-pusher/state.json`；
- 创建 systemd 服务和定时器；
- 进行一次只检查、不推送的测试；
- 每 15 分钟自动检查一次新内容。

> [!CAUTION]
> AppToken 不要填写到 README、Issue、聊天截图或 GitHub 代码中。安装器会把配置文件权限设为仅 `root` 可读。

## 为什么是每 15 分钟

云服务器可以准时执行任务，但原网站没有主动通知本程序的接口，因此仍然需要轮询 RSS。

| 检查间隔 | 平均发现延迟 | 最坏发现延迟 |
| --- | ---: | ---: |
| 2 小时 | 约 1 小时 | 约 2 小时 |
| 30 分钟 | 约 15 分钟 | 约 30 分钟 |
| 15 分钟 | 约 7.5 分钟 | 约 15 分钟 |

没有新一期时，程序只读取 RSS 后退出，不会调用 WxPusher，也不会给手机发送消息。GUID 去重会阻止同一期重复推送。

## 检查运行状态

查看下一次执行时间：

```bash
systemctl list-timers dahei-ai-pusher.timer
```

查看最近 100 行日志：

```bash
journalctl -u dahei-ai-pusher.service -n 100 --no-pager
```

立即检查一次：

```bash
systemctl start dahei-ai-pusher.service
```

正常但没有更新时会看到：

```text
没有发现新一期，无需推送。
```

出现新一期并成功推送时会看到：

```text
发现 1 期待推送内容。
正在推送……
推送成功并更新状态。
```

## 与 GitHub Actions 一起保留

不要同时让服务器和当前仓库的 GitHub Actions 长期自动推送，否则两边使用不同的状态文件，可能重复发送。

服务器确认正常后，在仓库中进入：

```text
Settings → Secrets and variables → Actions → Variables
```

添加：

```text
ENABLE_GITHUB_SCHEDULED_PUSH = false
```

这只会关闭当前仓库的 GitHub 自动排程：

- `Run workflow` 手动运行仍然保留；
- 其他开发者 Fork 后不设置此变量，GitHub Actions 仍会自动运行；
- 没有云服务器的人仍然可以完整使用 GitHub 部署方案。

如果重置过 WxPusher AppToken，还要同步更新 GitHub Secret `WXPUSHER_APP_TOKEN`，否则手动运行会使用已经失效的旧 Token。

## 更新服务器代码

服务器安装完成后，执行下面的一条命令即可安全更新：

```bash
curl -fsSL https://raw.githubusercontent.com/King52HerTz/DaheiAIPusher/main/scripts/update_server.sh \
  -o /tmp/update-dahei.sh && sudo bash /tmp/update-dahei.sh
```

更新脚本不会修改：

- `/etc/dahei-ai-pusher.env` 中的 AppToken；
- `/var/lib/dahei-ai-pusher/state.json` 中的去重状态。

## 暂停和重新开启推送

长期暂停服务器的自动检查：

```bash
systemctl disable --now dahei-ai-pusher.timer
```

这条命令会立即停止定时器，并阻止它在服务器重启后自动启动。它不会删除：

- `/opt/dahei-ai-pusher` 中的项目代码；
- `/etc/dahei-ai-pusher.env` 中的 AppToken；
- `/var/lib/dahei-ai-pusher/state.json` 中的最后推送期号。

确认定时器状态：

```bash
systemctl is-enabled dahei-ai-pusher.timer
systemctl is-active dahei-ai-pusher.timer
```

停止后通常会分别显示：

```text
disabled
inactive
```

重新开启自动推送：

```bash
systemctl enable --now dahei-ai-pusher.timer
```

再次查看下一次执行时间：

```bash
systemctl list-timers dahei-ai-pusher.timer
```

如果 GitHub Actions 的 `ENABLE_GITHUB_SCHEDULED_PUSH` 同时为 `false`，暂停服务器定时器后将没有任何自动推送来源，README 中的主题二维码仍然可以扫码关注，但订阅者暂时收不到新一期。重新开启服务器定时器后，程序会根据保存的状态继续检查并补发尚未推送的内容。

## 手动部署文件

不使用一键安装器时，可以参考 [`deploy/server`](../deploy/server/)：

```text
deploy/server/
├── dahei-ai-pusher.env.example  # 配置模板
├── dahei-ai-pusher.service      # systemd 推送服务
└── dahei-ai-pusher.timer        # 每 15 分钟运行的定时器
```

对应的服务器路径：

| 仓库文件 | 服务器位置 |
| --- | --- |
| `dahei-ai-pusher.env.example` | `/etc/dahei-ai-pusher.env` |
| `dahei-ai-pusher.service` | `/etc/systemd/system/dahei-ai-pusher.service` |
| `dahei-ai-pusher.timer` | `/etc/systemd/system/dahei-ai-pusher.timer` |

复制完成后执行：

```bash
chmod 600 /etc/dahei-ai-pusher.env
systemctl daemon-reload
systemctl enable --now dahei-ai-pusher.timer
```

## 常见问题

### `No module named 'src'`

需要从项目目录运行：

```bash
cd /opt/dahei-ai-pusher
./.venv/bin/python -m src.main
```

systemd 服务已经配置 `WorkingDirectory`，正常的定时运行不会出现这个问题。

### 定时器运行了，但没有手机消息

先查看日志：

```bash
journalctl -u dahei-ai-pusher.service -n 100 --no-pager
```

如果日志显示“没有发现新一期”，说明 RSS 没有更新，属于正常情况。如果显示 WxPusher 鉴权失败，检查 AppToken 是否被重置，以及 `/etc/dahei-ai-pusher.env` 是否填写正确。

### 出现重复推送

重点检查：

- GitHub Actions 自动排程是否已经关闭；
- `STATE_FILE` 是否仍为 `/var/lib/dahei-ai-pusher/state.json`；
- 状态文件是否被清空或删除；
- 是否在多台服务器上同时运行了相同应用。
