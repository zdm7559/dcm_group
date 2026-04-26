# AutoFix Agent Demo


这个服务的目标不是做复杂业务，而是提供一个稳定、可观测、可测试的 Web 服务，让后续 AutoFix Agent 能够完成：

```text
触发 bug -> 生成 traceback 日志 -> Agent 读取日志 -> 修改代码 -> 运行测试 -> 通知开发者
```

## 目录结构

```text
web_service/
  app.py                    # FastAPI 应用入口，负责组装路由和异常处理器
  api/
    router.py               # 汇总所有 API 路由
    routes/                 # HTTP 接口层，只负责接收请求和返回响应
  core/
    config.py               # 项目路径、日志路径、服务名等配置
    error_handlers.py       # 全局异常处理，将 traceback 写入结构化日志
    logging.py              # 错误日志 logger 配置
  repositories/             # 数据访问层，当前使用内存数据模拟
  services/                 # 业务逻辑层，当前故意保留两个待修复 bug
tests/
  test_service.py           # 修复验收测试
scripts/
  trigger_bug.py            # 演示用脚本，用于稳定触发 bug
agent/
  tools/
    git_ops.py              # Git 分支、diff、commit、PR 工具
    feishu_notify.py        # 飞书卡片通知工具
```

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

如果环境中已经安装过依赖，可以跳过这一步。

## 环境变量

复制示例配置：

```bash
cp .env.example .env
```

然后在 `.env` 中填入真实配置：

```bash
FEISHU_WEBHOOK_URL="你的飞书自定义机器人 Webhook"
GITHUB_TOKEN="你的 GitHub Personal Access Token"

GIT_AUTHOR_NAME="AutoFix Agent"
GIT_AUTHOR_EMAIL="autofix-agent@example.com"
GIT_COMMITTER_NAME="AutoFix Agent"
GIT_COMMITTER_EMAIL="autofix-agent@example.com"
```

说明：

```text
FEISHU_WEBHOOK_URL  用于发送飞书 Review 卡片
GITHUB_TOKEN        用于通过 GitHub API 创建 Pull Request
GIT_AUTHOR_*        用于让 Agent 生成的 commit 显示为 AutoFix Agent
GIT_COMMITTER_*     用于设置 Agent commit 的提交者信息
```

`.env` 只保存在本地，不要提交到 Git。

## 启动服务

```bash
python -m uvicorn web_service.app:app --reload
```

服务启动后访问：

```text
http://127.0.0.1:8000/docs
```

可以打开 FastAPI 自带的交互式接口文档。

## 正常接口

健康检查：

```bash
curl 'http://127.0.0.1:8000/health'
```

正常除法：

```bash
curl 'http://127.0.0.1:8000/divide?a=10&b=2'
```

查询存在的用户：

```bash
curl 'http://127.0.0.1:8000/users/1'
```

## 触发 bug

```bash
curl 'http://127.0.0.1:8000/divide?a=10&b=0'
curl 'http://127.0.0.1:8000/users/999'
```

也可以使用脚本触发：

```bash
python scripts/trigger_bug.py divide
python scripts/trigger_bug.py user
```

当前这两个接口会故意返回 `500`，用于模拟服务运行时异常：

```text
/divide?a=10&b=0 -> ZeroDivisionError
/users/999       -> KeyError
```

异常会被全局异常处理器捕获，并写入：

```text
logs/error.log
```

日志格式类似：

```text
=== AUTO_FIX_BUG_START ===
{
  "service": "demo-web-service",
  "method": "GET",
  "path": "/divide",
  "path_params": {},
  "query": {
    "a": "10",
    "b": "0"
  },
  "status_code": 500,
  "exception_type": "ZeroDivisionError",
  "exception_message": "float division by zero",
  "traceback": "..."
}
=== AUTO_FIX_BUG_END ===
```

这个 `logs/error.log` 是后续 Agent 的主要输入。

## 运行测试

```bash
python -m pytest tests/
```

当前初始状态下，测试预期是：

```text
/health 正常通过
/divide?a=10&b=2 正常通过
/users/1 正常通过
/divide?a=10&b=0 测试失败，期望 Agent 修成 400
/users/999 测试失败，期望 Agent 修成 404
```

也就是说，初始测试失败是正常现象。这个失败结果就是后续 AutoFix Agent 的修复目标。

## 当前阶段目标

Stage 1 的目标是先跑通 Web 靶场部分：

```text
服务能启动
正常接口能访问
bug 能稳定复现
错误能写入 logs/error.log
测试能定义修复后的验收标准
```

后续 Agent 会读取 `logs/error.log`，定位代码问题，修改 `services/` 或 `repositories/` 中的业务代码，并运行 `pytest tests/` 验证修复是否成功。

## Agent 工具

当前已实现两个工具模块：

```text
agent/tools/git_ops.py
agent/tools/feishu_notify.py
```

### Git 工具

`git_ops.py` 覆盖 Agent 自动修复后的 Git / GitHub 流程：

```text
sync_base_branch()
  -> git switch main
  -> git pull origin main

create_branch()
  -> git switch -c agent/fix-{error-slug}-{timestamp}

git_diff()
  -> git diff

git_commit()
  -> git add .
  -> git commit -m "fix: ..."

create_pr()
  -> git push origin 当前分支
  -> 调用 GitHub API 创建 PR
```

分支命名建议：

```text
agent/fix-{error-slug}-{timestamp}
```

示例：

```text
agent/fix-zero-division-error-20260426112830
agent/fix-key-error-20260426113012
```

### 飞书通知工具

`feishu_notify.py` 负责构造并发送飞书消息卡片：

```text
build_review_card()   # 构造 Card JSON 2.0 卡片
send_feishu_card()    # 发送到飞书自定义机器人 Webhook
```

飞书卡片使用 Card JSON 2.0：

```text
https://open.feishu.cn/document/feishu-cards/card-json-v2-structure
```

自定义机器人发送卡片参考：

```text
https://open.feishu.cn/document/feishu-cards/quick-start/send-message-cards-with-custom-bot
```

### 工具返回格式

所有工具统一返回：

```python
{"ok": True, "data": ..., "error": None}
{"ok": False, "data": ..., "error": "..."}
```

Agent 只需要根据 `ok` 判断是否继续下一步。

## Git / 飞书联调测试

如果要在测试仓库中验证 GitHub PR + 飞书通知，可以把测试仓库放在：

```text
external_repos/
```

示例：

```bash
mkdir -p external_repos
git clone git@github.com:ChailynCui/auto-fix-agent-test.git external_repos/auto-fix-agent-test
```

然后运行：

```bash
python - <<'PY'
from datetime import datetime
from pathlib import Path

from agent.tools.git_ops import (
    create_branch,
    create_pr,
    git_commit,
    git_diff,
    sync_base_branch,
)
from agent.tools.feishu_notify import build_review_card, send_feishu_card

repo_path = "external_repos/auto-fix-agent-test"
branch = "agent/fix-zero-division-error-" + datetime.now().strftime("%Y%m%d%H%M%S")

print(sync_base_branch("main", repo_path=repo_path))
print(create_branch(branch, repo_path=repo_path))

test_file = Path(repo_path) / "agent_git_tool_test.txt"
test_file.write_text(f"AutoFix Agent test branch: {branch}\n", encoding="utf-8")

print(git_diff(repo_path=repo_path))
print(git_commit("test: verify agent git tools", repo_path=repo_path))

pr_result = create_pr(
    title="test: verify agent git tools",
    body="Testing AutoFix Agent git_ops flow.",
    repo_path=repo_path,
    base="main",
)
print(pr_result)

if pr_result["ok"]:
    payload = build_review_card(
        title="Agent 已自动修复 Bug，请 Review",
        bug_type="ZeroDivisionError",
        endpoint="GET /divide?a=10&b=0",
        branch=pr_result["data"]["head"],
        pr_url=pr_result["data"]["url"],
        test_result="passed",
        risk_level="low",
    )
    print(send_feishu_card(payload))
PY
```
