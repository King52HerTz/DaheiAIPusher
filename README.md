# 大黑 AI 速报推送

定时读取[大黑 AI 速报 RSS](https://news.daheiai.com/rss.php)，通过 WxPusher 将新一期内容推送到手机。

同一套代码支持两种使用方式：

- **开源自部署**：每位开发者创建自己的 WxPusher 应用，通过 UID 推送给自己。
- **统一订阅服务**：运营者创建 WxPusher Topic，用户扫码订阅后，由 Topic 统一群发。

## 功能

- 直接读取 RSS，不抓取网页 HTML
- 使用 RSS `guid` 防止重复推送
- 支持中断后的多期补发，默认最多补发 6 期
- 首次运行只建立最新一期基线，不推送全部历史内容
- 支持 UID 单发、多个 UID 批量发送和 Topic 群发
- UID 与 Topic 可以同时配置
- 支持完整内容和摘要两种推送模式
- 完整模式会将 RSS 内容重新排版为适合手机阅读的摘要区、分类徽标和新闻卡片
- GitHub Actions 定时执行和手动测试
- 推送成功后持久化状态；失败内容会在下次运行时重试

## 方式一：开源工具，各自部署

适合只想给自己推送的开发者。

1. Fork 或复制本项目。
2. 在 [WxPusher 后台](https://wxpusher.zjiecode.com/admin/)创建自己的应用。
3. 扫描应用二维码关注应用，获取自己的 UID。
4. 在自己的 GitHub 仓库配置以下 Actions Secrets：

| Secret | 内容 |
| --- | --- |
| `WXPUSHER_APP_TOKEN` | 自己应用的 `AT_...` |
| `WXPUSHER_UID` | 自己的 `UID_...`；多个 UID 用英文逗号分隔 |

Fork 不会继承上游仓库的 Secrets。每位开发者都应使用自己的 AppToken，不得使用或索要运营者的 AppToken。

## 方式二：运营统一推送服务

适合由一个运营者向所有订阅者发送相同的 AI 速报。推荐使用 **Topic 群发**，无需保存用户 UID，也不需要部署关注回调服务器。

### 创建 Topic

1. 在 WxPusher 后台进入你的应用。
2. 创建一个主题，例如“AI速报”。
3. 取得该主题的数字 `topicId`。
4. 分享主题的订阅链接或主题二维码。
5. 用户订阅 Topic 后，程序每期只提交一次群发任务，由 WxPusher 分发给全部订阅者。

注意：应用二维码和主题二维码用途不同。应用二维码用于关注应用并取得 UID；统一群发应分享 **主题订阅码**。WxPusher 的动态二维码图片会变化，优先分享后台提供的订阅链接；如需长期展示或打印，应使用静态二维码。

统一服务配置以下 Secrets：

| Secret | 内容 |
| --- | --- |
| `WXPUSHER_APP_TOKEN` | 运营应用的 `AT_...` |
| `WXPUSHER_TOPIC_IDS` | Topic 数字 ID；多个 Topic 用英文逗号分隔 |

统一服务不需要设置 `WXPUSHER_UID`；你也可以额外配置自己的 UID，同时接收一份管理员测试通知。

如果定时任务需要使用摘要模式，在 GitHub 仓库的
`Settings → Secrets and variables → Actions → Variables` 中添加：

```text
CONTENT_MODE = summary
```

### 运营注意事项

- AppToken 只能保存在 GitHub Actions Secrets 或服务器环境变量中，不能公开。
- Topic ID 不是发送授权凭证，但建议仍放在 Secrets 中统一管理。
- 应用名称、说明和关注提示应明确运营者身份、内容来源、推送频率和退订方式。
- 推送正文保留“大黑AI速报”署名和原文链接。
- 本项目运营者的公开推送服务已获得原作者授权；其他 Fork 使用者应自行确认其使用方式获得相应授权。
- 保存原作者授权记录，内容范围或商业模式发生变化时重新确认。

建议的应用说明：

> 每4小时推送大黑AI速报，内容来源于 news.daheiai.com。订阅者可随时在 WxPusher 中取消主题订阅。

## GitHub Actions Secrets

进入 GitHub 仓库：

`Settings → Secrets and variables → Actions`

至少配置：

```text
WXPUSHER_APP_TOKEN
```

并根据部署方式至少配置以下一个：

```text
WXPUSHER_UID
WXPUSHER_TOPIC_IDS
```

程序支持同时配置二者，但不能同时留空。

## 第一次运行

在 GitHub 中打开：

`Actions → Dahei AI News Push → Run workflow`

可选项：

- 默认运行：只建立当前最新一期基线，不发送历史内容。
- `push_on_first_run`：状态为空时立即推送最新一期。
- `dry_run`：只检查新内容，不发送，也不更新状态。
- `content_mode`：本次手动运行使用完整内容或摘要。

定时任务会在北京时间每天 `00、04、08、12、16、20` 点后的第 12 和 42 分钟检查更新。

## 推送内容模式

通过 `CONTENT_MODE` 控制：

- `full`：发送 RSS 提供的完整 HTML 内容，当前默认值。
- `summary`：只发送标题、摘要、署名和原文链接。

公开运营者应确保全文推送已取得内容方授权；未取得授权时建议使用 `summary`。

## 本地运行

推荐使用 Python 3.12 或更高版本。

### UID 自用模式

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:WXPUSHER_APP_TOKEN = "AT_xxx"
$env:WXPUSHER_UID = "UID_xxx"
python -m src.main
```

### Topic 运营模式

```powershell
$env:WXPUSHER_APP_TOKEN = "AT_xxx"
$env:WXPUSHER_TOPIC_IDS = "123"
$env:CONTENT_MODE = "full"
python -m src.main
```

### 只读检查

```powershell
$env:DRY_RUN = "true"
python -m src.main
```

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WXPUSHER_APP_TOKEN` | 无 | WxPusher AppToken，实际推送时必填 |
| `WXPUSHER_UID` | 无 | UID，多个值使用英文逗号分隔 |
| `WXPUSHER_TOPIC_IDS` | 无 | Topic 数字 ID，多个值使用英文逗号分隔 |
| `CONTENT_MODE` | `full` | `full` 完整内容，`summary` 摘要模式 |
| `RSS_URL` | 大黑 AI RSS | RSS 地址 |
| `STATE_FILE` | `data/state.json` | 去重状态文件 |
| `DRY_RUN` | `false` | 只检查，不发送、不更新状态 |
| `PUSH_ON_FIRST_RUN` | `false` | 首次运行是否推送最新一期 |
| `MAX_CATCHUP_ITEMS` | `6` | 旧 GUID 已离开 RSS 时最多补发数量 |
| `HTTP_CONNECT_TIMEOUT` | `10` | 连接超时秒数 |
| `HTTP_READ_TIMEOUT` | `20` | 读取超时秒数 |

## 状态提交

GitHub Actions 会在成功推送后提交 `data/state.json`。仓库需要启用：

`Settings → Actions → General → Workflow permissions → Read and write permissions`

如果默认分支禁止机器人直接推送，需要允许 GitHub Actions 写入该文件，或改用服务器保存状态。

## 测试

```powershell
python -m unittest discover -s tests -v
```

本地预览最新一期的消息样式：

```powershell
python -m scripts.preview
```

运行后用浏览器打开项目根目录下的 `preview.html`。
