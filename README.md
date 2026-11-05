# feishu_codex_bot

飞书群里 @机器人 → 机器人调用本机 Codex CLI 执行任务 → 结果自动回复到群里。

## 功能

- 在飞书群聊中 @机器人 提问或下达编码任务，机器人自动执行并回复
- 每个群绑定独立的工作目录（`group_workspace/`），Codex 在该目录内读写文件、执行命令
- 消息幂等去重（Redis，5 分钟窗口），防止飞书重试导致重复执行
- Celery 异步执行，长连接不阻塞；支持超时控制（默认 300s）

## 架构

```
飞书群 @机器人
      │  (WebSocket 长连接)
      ▼
main.py ── 收消息、去重、提取问题（去掉 @ 前缀）
      │  celery .delay()
      ▼
Redis (broker / backend, db1, Docker 容器)
      │
      ▼
tasks.py (Celery worker, --pool=solo)
      │  subprocess 调用 codex exec
      ▼
Codex CLI ── 在群绑定的工作目录内执行
      │  --output-last-message 提取最终回答
      ▼
main.py 后台线程等待结果 ── 调飞书 API 回复群聊
```

## 前置条件

| 依赖 | 说明 |
|---|---|
| Python 3.x + 项目 `.venv` | `lark-oapi`、`celery`、`redis`、`python-dotenv` |
| Redis | 跑在 Docker Desktop 里，映射到 `127.0.0.1:6379` |
| Codex CLI (`@openai/codex`) | npm 全局安装，配置见下方 |

## 配置

### `.env`（项目根目录，勿提交）

```ini
# 飞书应用凭证（需开通接收消息 + 发消息权限）
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx

# Redis
REDIS_URL=redis://127.0.0.1:6379/1

# Codex 可执行文件全路径 + 超时（秒）
CODEX_EXEC_PATH=C:\Users\Administrator\AppData\Roaming\npm\...\codex.exe
CODEX_TIMEOUT=300

# 模型 Provider 的 API Key（按 config.toml 中 env_key 对应）
DEEPSEEK_API_KEY=sk-xxx
SUBLINKS_API_KEY=sk-xxx

OPENAI_API_KEY=sk-xxx
```

### Codex CLI（`C:\Users\<user>\.codex\config.toml`）

> ⚠️ codex 0.166+ 已废弃顶层 `base_url` / `experimental_bearer_token` 写法，必须使用 `[model_providers.*]` + `env_key`：

```toml
model = "deepseek-flash"
model_provider = "deepseek"

[model_providers.deepseek]
name = "deepseek"
base_url = "https://api.deepseek.com"
wire_api = "responses"
env_key = "DEEPSEEK_API_KEY"
requires_openai_auth = false
```

当前使用 DeepSeek（国内直连稳定）；`config.toml` 中同时保留了 `sublinks` 中转站配置，恢复可用时把 `model_provider` 改回 `"sublinks"` 即可。

> 注意：如果本机有 `~/.codex/auth.json`（ChatGPT 登录态），codex 启动时会尝试连接 chatgpt.com 导致长时间重试，服务器场景建议移走（本项目已备份为 `auth.json.bak-20261105`）。

### 群 → 工作目录映射（`redis_store.py`）

```python
CHAT_DIR_MAP = {
    "oc_xxxxxxxx": "group_workspace/demo1",  # 群 chat_id -> 相对目录
}
```

新群默认使用 `group_workspace/default`，按需在此添加映射。

## 启动 / 停止

```
1. 启动 Docker Desktop（Redis 在其中）
2. 双击 start_bot.bat   → 自动检查 Redis 并启动 celery + 机器人
3. 在群里 @机器人 提问即可
停止：双击 stop_bot.bat
```

手动启动（等价）：

```bash
# 终端 1
.venv/Scripts/celery.exe -A tasks worker --pool=solo --loglevel=info
# 终端 2
.venv/Scripts/python.exe main.py
```

## 使用

在飞书群里 @机器人 + 问题，例如：

> @机器人 帮我写一个 fastapi 的 hello world

机器人约 20~60 秒后回复 Codex 的执行结果。日志查看项目根目录 `bot.log`（飞书侧）与 `celery.log`（任务侧）。

## 文件说明

| 文件 | 作用 |
|---|---|
| `main.py` | 飞书长连接客户端，收 @消息、去重、清洗问题、投递任务、回发结果 |
| `tasks.py` | Celery 任务：调用 codex exec，提取最终回答 |
| `redis_store.py` | Redis 连接、消息幂等去重、群→工作目录映射 |
| `start_bot.bat` / `stop_bot.bat` | 一键启停 |
| `test_codex.py` | 本地调试脚本：加载 .env 直接测 codex exec（不在命令行暴露密钥） |
| `group_workspace/` | 各群独立工作目录 |

## 常见问题

- **机器人不回复**：确认 Docker Desktop 和 `start_bot.bat` 都已启动；查看 `bot.log` 是否收到事件、`celery.log` 是否执行任务。
- **回复"Codex 执行失败"**：看 `celery.log` 中的 stderr 关键行；多半是 API Key 失效或模型通道故障。
- **中转站 502**：sublinks 的 `/v1/responses` 上游故障时切换到 deepseek provider（见上文配置）。
- **重复回复**：幂等窗口只有 5 分钟，若 5 分钟后飞书重试同一条消息会再次执行。
