# 大黑 AI 速报推送 ⚡

> 一个把大黑 AI 速报自动送到手机的轻量工具。GitHub Actions 和云服务器都能负责定时运行，我们只管看消息。

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-自动推送-2088FF?logo=githubactions&logoColor=white)](https://github.com/King52HerTz/DaheiAIPusher/actions)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

事情是这样的：

[大黑 AI 速报](https://news.daheiai.com/)每 4 小时更新一次，但我不可能每 4 小时打开网页刷新——毕竟课还是要上的，觉也是要睡的。

整个流程由三个部分完成：

- RSS：负责告诉我“有新一期了”；
- GitHub Actions / 云服务器：负责定时起床干活；
- WxPusher：负责把消息送到手机。

最终效果就是：网站一更新，手机就能收到排版好的 AI 新闻卡片。

## 实际推送效果

不是概念图，也不是“最终效果仅供参考”——下面就是 WxPusher 实际收到的完整长截图。栏目和摘要一目了然，橙色的“查看信源”可以直接点击。

<p align="center">
  <a href="docs/images/wxpusher-long-preview.jpg">
    <img src="docs/images/wxpusher-long-preview.jpg" width="300" alt="大黑AI速报在 WxPusher 中的实际推送长截图">
  </a>
</p>

<p align="center"><sub>图片有亿点长，点击可以查看原图。</sub></p>

## 我只想看，不想配置

完全合理。配置环境的时间够看好几期速报了。

使用 WxPusher 扫描下面的二维码，就能关注我创建的主题 **「大黑AI速报」**：

还没有安装 WxPusher？安卓手机可以在手机自带的应用商店中搜索 **WxPusher**，iPhone 或 iPad 可以在 **App Store** 中搜索 **WxPusher** 安装。安装完成后，再使用 WxPusher 扫描下面的二维码即可订阅。

<p align="center">
  <img src="https://wxpusher.zjiecode.com/api/qrcode/m5pkKxplAx3CdxLyuhsVtysKe953eGVu1UiicQjPfhwdIE3SIew36Qr7dDL0K4yZ.jpg" width="280" alt="大黑AI速报 Topic 订阅二维码">
</p>

<p align="center"><strong>扫码订阅，剩下的交给赛博牛马</strong></p>

二维码没有显示？[点这里单独打开](https://wxpusher.zjiecode.com/api/qrcode/m5pkKxplAx3CdxLyuhsVtysKe953eGVu1UiicQjPfhwdIE3SIew36Qr7dDL0K4yZ.jpg)。

订阅后不需要下载代码、不需要 GitHub 账号，也不需要创建自己的应用。新的速报会自动推送到设备上，想取消时直接在 WxPusher 的订阅管理中取消即可。

## 这个项目做了什么

```text
大黑AI速报 RSS
      ↓
GitHub Actions / 云服务器定时检查
      ↓
GUID 判断是不是新一期
      ↓
重新排版成手机新闻卡片
      ↓
WxPusher UID / Topic
      ↓
你的手机
```

主要功能：

- 读取官方 RSS，不拿爬虫在网页上硬刮；
- 使用每期 GUID 去重，拒绝把同一条新闻反复塞进通知栏；
- 断更后可以补发，默认最多补 6 期，防止手机突然开始“渡劫”；
- 支持完整内容和摘要模式；
- 自动把原始 RSS 排版成摘要区、分类徽标和新闻卡片；
- 支持 UID 单发、多个 UID 批量发送和 Topic 群发；
- 首次运行默认只建立基线，不会把历史消息一股脑倒进手机；
- 推送失败不会更新状态，下次运行还能继续重试。

## 我也想自己部署

欢迎进入“明明扫码就能用，但我偏要自己配”的开发者路线。

### 1. Fork 仓库

点击 GitHub 页面右上角的 `Fork`，把项目复制到自己的账号。

### 2. 创建 WxPusher 应用

打开 [WxPusher 后台](https://wxpusher.zjiecode.com/admin/)，创建一个应用并取得：

- `appToken`：应用的发送密钥；
- `UID`：接收消息的用户标识。

如果准备给很多人提供统一订阅，可以再创建一个 Topic，使用数字 `topicId` 群发。

### 3. 添加 GitHub Secrets

进入自己的仓库：

```text
Settings → Secrets and variables → Actions
```

至少添加：

| Secret | 填什么 |
| --- | --- |
| `WXPUSHER_APP_TOKEN` | 你的 `AT_...` |

再根据使用方式添加至少一个接收目标：

| Secret | 适用场景 |
| --- | --- |
| `WXPUSHER_UID` | 给自己或指定用户发送，多个 UID 用英文逗号分隔 |
| `WXPUSHER_TOPIC_IDS` | Topic 群发，多个数字 ID 用英文逗号分隔 |

两者可以同时配置，但不能同时留空。

> [!CAUTION]
> AppToken 不能发给别人，不能提交到代码，也不要截图发到 Issue。泄漏后别人可以顶着你的应用名义发消息，场面可能比实验课忘记保存代码更难收拾。

### 4. 开启 Actions 写入权限

进入：

```text
Settings → Actions → General → Workflow permissions
```

选择：

```text
Read and write permissions
```

程序需要更新 `data/state.json`，用它记住最后推送到了哪一期。

### 5. 第一次运行

打开：

```text
Actions → Dahei AI News Push → Run workflow
```

选项说明：

- `dry_run`：只检查，不发送，也不修改状态；
- `push_on_first_run`：第一次就发送当前最新一期；
- `force_push_latest`：无论是否推送过，都重新发送最新一期；适合测试排版，但 Topic 订阅者也会收到；
- `content_mode`：选择完整内容 `full` 或摘要 `summary`。

第一次测试建议：

```text
dry_run: false
push_on_first_run: true
content_mode: full
```

看到绿色对勾先别急着开香槟：它代表脚本执行成功。手机是否弹通知，还要确认自己确实订阅了对应 Topic，并开启了系统通知权限。

## 什么时候推送

工作流按北京时间全天检查，每小时运行三次：

```text
每小时的 07、27、47 分
```

网站通常在北京时间 00、04、08、12、16、20 点更新。工作流不再只押注这些时间附近的两次任务，而是全天每 20 分钟检查一次；即使 GitHub 漏掉一次，后面还有连续补偿检查。发现 GUID 没变就会安静退出，不会重复轰炸。

GitHub Actions 不是高铁时刻表，官方也说明定时任务在高负载时可能延迟甚至被丢弃。所以这里选择“多检查几次但不重复推送”，而不是指望一次 cron 永不迟到。

## 我有云服务器，但我有点懒

巧了，电脑最适合接手这种重复劳动。

Ubuntu / Debian 服务器可以使用一键安装脚本。它会自动安装 Python 环境、保存配置、迁移去重状态，并创建每 15 分钟运行一次的 systemd 定时器：

```bash
curl -fsSL https://raw.githubusercontent.com/King52HerTz/DaheiAIPusher/main/scripts/install_server.sh \
  -o /tmp/install-dahei.sh && sudo bash /tmp/install-dahei.sh
```

运行后只需要输入两个东西：

- WxPusher `AppToken`，输入时屏幕不会显示；
- 「大黑AI速报」的数字 `Topic ID`。

服务器仍然需要定时询问 RSS“更新了吗”。每 15 分钟检查一次意味着最坏约 15 分钟发现更新；没有新一期时不会调用 WxPusher，更不会给手机发送空气。

常用命令：

```bash
# 查看定时器
systemctl list-timers dahei-ai-pusher.timer

# 查看最近日志
journalctl -u dahei-ai-pusher.service -n 100 --no-pager

# 立即检查一次
systemctl start dahei-ai-pusher.service
```

确认服务器连续运行正常后，在自己的 GitHub 仓库添加 Actions Variable：

```text
ENABLE_GITHUB_SCHEDULED_PUSH = false
```

这样只会关闭当前仓库的 GitHub 自动排程，`Run workflow` 手动测试仍然保留。其他开发者 Fork 本仓库后，如果不设置这个变量，GitHub Actions 仍会照常定时运行。

## 完整模式和摘要模式

默认使用：

```text
CONTENT_MODE = full
```

- `full`：发送完整内容，并重新排版成适合手机阅读的卡片；
- `summary`：只发送标题、摘要和原文链接。

如果希望定时任务长期使用摘要模式，在仓库的 Actions Variables 中添加：

```text
CONTENT_MODE = summary
```

## 本地运行

推荐 Python 3.12 或更高版本。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:WXPUSHER_APP_TOKEN = "AT_xxx"
$env:WXPUSHER_UID = "UID_xxx"

python -m src.main
```

Topic 群发：

```powershell
$env:WXPUSHER_APP_TOKEN = "AT_xxx"
$env:WXPUSHER_TOPIC_IDS = "123456"
python -m src.main
```

只检查、不发送：

```powershell
$env:DRY_RUN = "true"
python -m src.main
```

## 本地预览消息样式

不想每改一次 CSS 就给手机发一条测试消息，可以先生成浏览器预览：

```powershell
python -m scripts.preview
```

然后打开项目根目录下的 `preview.html`。前端调样式最重要的经验之一：能在本地解决的，不要拿生产环境许愿。

## 环境变量

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `WXPUSHER_APP_TOKEN` | 无 | WxPusher AppToken，实际推送时必填 |
| `WXPUSHER_UID` | 无 | UID，多个值用英文逗号分隔 |
| `WXPUSHER_TOPIC_IDS` | 无 | Topic ID，多个值用英文逗号分隔 |
| `CONTENT_MODE` | `full` | `full` 完整内容，`summary` 摘要模式 |
| `RSS_URL` | 大黑 AI RSS | RSS 地址 |
| `STATE_FILE` | `data/state.json` | 去重状态文件 |
| `DRY_RUN` | `false` | 只检查，不发送、不更新状态 |
| `PUSH_ON_FIRST_RUN` | `false` | 状态为空时是否推送最新一期 |
| `FORCE_PUSH_LATEST` | `false` | 强制重发最新一期且不修改去重状态，用于手动测试 |
| `MAX_CATCHUP_ITEMS` | `6` | 状态落后太多时最多补发几期 |
| `HTTP_CONNECT_TIMEOUT` | `10` | 连接超时秒数 |
| `HTTP_READ_TIMEOUT` | `20` | 读取超时秒数 |

## 项目结构

```text
DaheiAIPusher/
├── .github/workflows/push.yml   # 定时打工人
├── data/state.json              # 记住上次推到哪了
├── scripts/preview.py           # 本地预览消息样式
├── src/
│   ├── feed.py                  # 读取和解析 RSS
│   ├── main.py                  # 主流程
│   ├── state.py                 # 状态读写
│   └── wxpusher.py              # 消息排版与推送
└── tests/                       # 防止“改一行，坏一片”
```

## 测试

```powershell
python -m unittest discover -s tests -v
```

## 感谢

首先感谢 **[人工大黑](https://www.daheiai.com/)** 制作并持续更新[大黑 AI 速报](https://news.daheiai.com/)，还专门提供了 RSS，让这种自动化订阅成为可能。

感谢人工大黑对本项目的授权与支持。推送内容会保留“大黑AI速报”署名、原文入口和原始信源链接。

也感谢：

- [WxPusher](https://wxpusher.zjiecode.com/) 提供消息推送能力；
- [GitHub Actions](https://github.com/features/actions) 提供免费的云端打工人；
- 每一位愿意扫码、Star、提 Issue，甚至帮忙抓 Bug 的同学。

没有这些项目，这个仓库大概只会剩下一句：`print("记得看 AI 新闻")`。

## 开源协议与内容版权
项目代码采用 [MIT License](LICENSE) 开源，你可以使用、修改、分发，也可以在保留版权和许可声明的前提下用于自己的项目。

需要特别说明：

- MIT 协议只覆盖本仓库的程序代码；
- “大黑AI速报”的文章、摘要和视觉素材不因此变成 MIT 内容；
- 速报内容版权属于原作者，引用的新闻与素材权利属于对应的原始信源；
- Fork 后如果要公开运营、商业化或改变内容用途，请自行取得相应授权。

简单说就是：代码可以拿去折腾，别顺手把别人的内容版权也 `git clone` 走了。

## 最后

如果这个项目对你有用，可以点个 Star；如果它突然不推了，欢迎提 Issue；如果你有更好的排版或功能建议，也欢迎一起改进。

请不要在 Issue、截图或日志里公开 AppToken。保护密钥，从不把 `config.py` 上传到 GitHub 做起。
