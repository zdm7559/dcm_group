# AutoFix Agent Demo


这个服务的目标不是做复杂业务，而是提供一个稳定、可观测、可测试的 Web 服务，让 AutoFix Agent 能够完成：

```text
触发 bug -> 生成 traceback 日志 -> Agent 读取日志 -> 读取源码 -> 调用大模型 -> 修改代码 -> 运行测试 -> 记录修复过程
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
  services/                 # 业务逻辑层，初始靶场状态下包含待修复 bug
tests/
  test_service.py           # 修复验收测试
scripts/
  trigger_bug.py            # 演示用脚本，用于稳定触发 bug
agent/
  main.py                   # Agent 命令行入口
  workflow.py               # AutoFix 主流程编排
  llm_client.py             # OpenAI-compatible 大模型客户端
  prompts.py                # 诊断和补丁生成 Prompt
  fix_records.py            # 保存每次修复过程记录
  tools/
    git_ops.py              # Git 分支、diff、commit、PR 工具
    feishu_notify.py        # 飞书卡片通知工具
    read_log.py             # 读取并结构化解析错误日志
    read_file.py            # 读取错误相关源码上下文
    run_tests.py            # 运行测试并返回结构化结果
    write_file.py           # 安全写入和批量替换源码
fix_records/                # Agent 自动生成的修复记录
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

OPENAI_API_KEY="你的 OpenAI-compatible API Key"
OPENAI_BASE_URL="https://api.openai.com/v1"
MODEL_NAME="gpt-4o-mini"
LLM_TEMPERATURE=""

GIT_AUTHOR_NAME="AutoFix Agent"
GIT_AUTHOR_EMAIL="autofix-agent@example.com"
GIT_COMMITTER_NAME="AutoFix Agent"
GIT_COMMITTER_EMAIL="autofix-agent@example.com"
```

说明：

```text
FEISHU_WEBHOOK_URL  用于发送飞书 Review 卡片
GITHUB_TOKEN        用于通过 GitHub API 创建 Pull Request
OPENAI_API_KEY      用于调用大模型生成诊断和修复操作
OPENAI_BASE_URL     OpenAI-compatible 接口地址
MODEL_NAME          大模型名称
LLM_TEMPERATURE     可选；留空则不传 temperature，适合 Kimi 等限制 temperature 的模型
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

在初始靶场状态下，这两个接口会故意返回 `500`，用于模拟服务运行时异常：

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

初始靶场状态下，测试预期是：

```text
/health 正常通过
/divide?a=10&b=2 正常通过
/users/1 正常通过
/divide?a=10&b=0 测试失败，期望 Agent 修成 400
/users/999 测试失败，期望 Agent 修成 404
```

也就是说，初始测试失败是正常现象。这个失败结果就是 AutoFix Agent 的修复目标。

如果 Agent 已经修复过对应 bug，全量测试可能会变为全部通过。

## 当前阶段目标

Stage 1 的目标是先跑通一个最小可用的自动修复闭环：

```text
服务能启动
正常接口能访问
bug 能稳定复现
错误能写入 logs/error.log
测试能定义修复后的验收标准
Agent 能读取日志并定位相关源码
Agent 能调用大模型生成修复操作
Agent 能安全写入代码并运行目标测试
Agent 能保存修复记录
```

当前已经验证通过的自动修复场景：

```text
/divide?a=10&b=0 -> ZeroDivisionError -> 自动修复为 400
/users/999       -> KeyError           -> 自动修复为 404
```

## Agent 主流程

当前已经补充了一个最小可运行的手写 workflow，不依赖 LangChain / LangGraph 调度。

```text
agent/main.py          # 命令行入口
agent/workflow.py      # 串联 read_log -> read_file -> LLM -> write_file -> run_tests -> fix_record
agent/llm_client.py    # OpenAI-compatible Chat Completions 客户端
agent/prompts.py       # 诊断和修复操作生成 prompt
agent/fix_records.py   # 保存本地修复记录
fix_records/           # 保存每次修复过程的 Markdown 记录
```

运行一次 Agent：

```bash
python -m agent.main
```

指定最大修复尝试次数：

```bash
python -m agent.main --max-attempts 3
```

指定项目根目录：

```bash
python -m agent.main --repo-path <project-root> --max-attempts 3
```

默认情况下，命令行会输出适合人阅读的阶段进度，例如“读取日志、选择错误、读取源码、调用大模型、写入代码、语法检查、运行测试、保存记录”。这样可以直接看到 Agent 当前执行到哪一步。

如果需要查看完整结构化 JSON，可以加上：

```bash
python -m agent.main --max-attempts 3 --json
```

如果没有配置 `OPENAI_API_KEY`，流程会停在大模型调用前，并返回明确错误：

```text
OPENAI_API_KEY is not configured
```

当前 workflow 的定位是先跑通确定性主线，大模型只负责两步：

```text
LLM diagnose         # 分析根因和修复策略
LLM generate patch   # 生成 apply_replacements 可执行的替换操作
```

### 当前数据流

运行：

```bash
python -m agent.main --max-attempts 3
```

实际执行的数据流如下：

```text
agent/main.py
  -> 解析 --repo-path 和 --max-attempts
  -> agent/workflow.py::run_once()

run_once()
  -> read_error_logs(mode="grouped")
  -> _select_error()
  -> read_files_for_error()
  -> LLM diagnose
  -> LLM generate patch
  -> apply_replacements()
  -> py_compile changed python files
  -> run targeted pytest
  -> save_fix_record()
  -> 打印最终 JSON
```

关键说明：

```text
read_error_logs(mode="grouped")
  读取 logs/error.log 中所有 AUTO_FIX_BUG 日志块，并按 fingerprint 聚合同类错误。

_select_error()
  当前选择 grouped 结果中的第一组 latest 错误。
  grouped 排序优先考虑 occurrences，出现次数相同时再考虑 latest_seen。

read_files_for_error()
  根据 traceback 中的 project_frames 读取相关源码。
  优先读取目标行所在的完整函数，额外读取 tests/test_service.py 让模型理解验收标准。

LLM diagnose
  只生成根因、修复策略、建议修改文件和风险等级。

LLM generate patch
  只生成 apply_replacements 可执行的 operations。

apply_replacements()
  先验证所有 old_text 是否唯一匹配，再统一写入文件。
  写入结果会包含 before_contents，供失败回滚使用。

py_compile
  对本轮被修改的 .py 文件做语法检查。
  如果大模型生成缩进错误或非法 Python，会立即回滚。

run targeted pytest
  对 /divide 错误只运行 test_divide_by_zero_should_return_400。
  对 /users/{user_id} 错误只运行 test_user_not_found_should_return_404。
  其他未知错误才退回运行 python -m pytest tests/。

save_fix_record()
  将错误、诊断、写入结果、测试结果保存到 fix_records/*.md。
```

### 成功返回示例

```json
{
  "ok": true,
  "data": {
    "error": {
      "path": "/divide",
      "exception_type": "ZeroDivisionError",
      "fingerprint": "379050a2308c3096"
    },
    "diagnosis": {
      "root_cause": "...",
      "fix_strategy": "...",
      "files_to_modify": [
        "web_service/services/calculator.py",
        "web_service/api/routes/calculator.py"
      ],
      "risk_level": "low"
    },
    "write_result": {
      "ok": true,
      "data": {
        "changed": true,
        "changed_files": [
          "web_service/services/calculator.py",
          "web_service/api/routes/calculator.py"
        ]
      }
    },
    "test_result": {
      "ok": true,
      "data": {
        "passed": true,
        "command": [
          "python",
          "-m",
          "pytest",
          "tests/test_service.py::test_divide_by_zero_should_return_400"
        ]
      }
    },
    "record": {
      "ok": true,
      "data": {
        "path": "fix_records/20260427-193025-zerodivisionerror-379050a2308c3096.md"
      }
    }
  },
  "error": null
}
```

### 失败和重试机制

`--max-attempts 3` 表示最多让大模型生成 3 轮修复操作。

每一轮失败后，workflow 会把失败信息放入 `previous_failure`，下一轮会带给大模型：

```text
stage = write    # old_text 找不到、old_text 不唯一、路径非法等
stage = syntax   # 写入后 py_compile 失败
stage = test     # 语法正确，但目标测试失败
```

如果已经写入文件但后续失败，会调用 `restore_files()` 回滚到本轮修改前的内容，避免错误补丁污染代码。

## Agent 工具

当前已实现六个工具模块：

```text
agent/tools/git_ops.py
agent/tools/feishu_notify.py
agent/tools/read_log.py
agent/tools/read_file.py
agent/tools/run_tests.py
agent/tools/write_file.py
```

更详细的工具层变更说明见：

```text
CHANGELOG_AGENT_TOOLS.md
```

### 日志读取工具

`read_log.py` 负责把 `logs/error.log` 转换成 Agent 可处理的结构化错误事件。

核心函数：

```text
read_error_logs()
read_latest_error_log()
```

主要能力：

```text
读取多个 AUTO_FIX_BUG_START / AUTO_FIX_BUG_END 日志块
支持 all / latest / grouped 三种读取模式
按 fingerprint 聚合同类错误
保留完整 traceback
提取项目内 project_frames
生成 suspect_frame 和 context_hints，提示 Agent 优先读取哪些源码文件
```

示例：

```bash
python - <<'PY'
from agent.tools import read_error_logs

result = read_error_logs(mode="grouped")
print(result)
PY
```

### 源码读取工具

`read_file.py` 负责根据 `read_log` 输出的错误事件读取相关源码上下文。

核心函数：

```text
read_file()
read_files()
read_files_for_error()
```

主要能力：

```text
优先读取目标行所在的完整函数或异步函数
找不到函数时退回到目标行附近窗口
支持一次读取多个文件
可以直接消费 read_log 返回的 error_event
默认额外读取 tests/test_service.py，帮助 Agent 理解测试期望
```

示例：

```bash
python - <<'PY'
from agent.tools import read_error_logs, read_files_for_error

log_result = read_error_logs(mode="latest")
error_event = log_result["data"]["error"]
result = read_files_for_error(error_event)
print(result)
PY
```

### 测试运行工具

`run_tests.py` 负责在 Agent 修改代码后运行测试，判断修复是否成功。

核心函数：

```text
run_tests()
```

默认执行：

```text
python -m pytest tests/
```

返回内容包括：

```text
passed
exit_code
command
stdout
stderr
summary
```

示例：

```bash
python - <<'PY'
from agent.tools import run_tests

result = run_tests(cwd=".")
print(result["ok"])
print(result["data"]["summary"])
PY
```

在初始靶场状态下，此工具预期返回测试失败：

```text
3 passed, 2 failed
```

如果两个示例 bug 都已经被 Agent 修复，全量测试应变为：

```text
5 passed
```

### 源码写入工具

`write_file.py` 负责把 Agent 生成的修复安全写入项目文件。

核心函数：

```text
replace_in_file()
apply_replacements()
write_file()
restore_files()
```

主要能力：

```text
replace_in_file 用于单点精确替换
apply_replacements 用于多文件、多位置批量替换
write_file 用于受保护的整文件写入
restore_files 用于根据 before_contents 回滚本轮写入
批量替换会先验证全部操作，再统一写回，避免半成功状态
默认拒绝写入 .git、.env、logs/error.log、缓存目录等路径
返回变更文件、写入前后的 sha256 摘要和 before_contents
```

示例：

```python
from agent.tools import apply_replacements

result = apply_replacements([
    {
        "path": "web_service/services/calculator.py",
        "old_text": "return a / b",
        "new_text": "return a / b",
    }
])
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

### 当前 Agent 调用顺序

当前 `agent/workflow.py` 已经按这个顺序编排：

```text
read_error_logs(mode="grouped")
  -> 选择一个错误事件
  -> read_files_for_error()
  -> LLM 诊断根因
  -> LLM 生成修复操作
  -> apply_replacements()
  -> py_compile 检查语法
  -> run_tests(command=targeted_test)
  -> save_fix_record()
```

GitHub PR 和飞书通知目前已经有工具实现，但还没有接入 `agent/workflow.py` 主链路：

```text
  -> git_diff()
  -> git_commit()
  -> create_pr()
  -> build_review_card()
  -> send_feishu_card()
```

## 发布 v0.1.0

`v0.1.0` 是当前项目的第一个完整可运行版本，版本边界如下：

```text
已完成：
  Web 服务靶场
  结构化错误日志
  read_log / read_file / write_file / run_tests 工具
  OpenAI-compatible 大模型调用
  手写 AutoFix workflow
  语法检查和失败回滚
  目标测试验证
  本地修复记录

暂未接入主链路：
  自动创建 GitHub PR
  自动发送飞书通知
  MCP Server 封装
  LangChain / LangGraph 等通用 Agent 框架
```

建议打 tag 前执行：

```bash
python -m py_compile agent/main.py agent/workflow.py agent/llm_client.py agent/prompts.py agent/fix_records.py
python -m py_compile agent/tools/read_log.py agent/tools/read_file.py agent/tools/run_tests.py agent/tools/write_file.py agent/tools/__init__.py
python -m pytest tests/
```

当前代码如果两个示例 bug 都已被修复，预期测试结果是：

```text
5 passed
```

### 建议上传到 GitHub 的内容

应该上传：

```text
README.md
CHANGELOG_AGENT_TOOLS.md
requirements.txt
pytest.ini
.env.example
.gitignore
VERSION
web_service/
agent/
scripts/
tests/
logs/.gitkeep
fix_records/.gitkeep
```

不应该上传：

```text
.env
.env.*
logs/error.log
fix_records/*.md
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
build/
dist/
*.egg-info/
external_repos/
CLAUDE.md
```

说明：

```text
.env                    包含真实 API Key、Webhook、Token，只保留 .env.example。
logs/error.log           是本地运行产生的错误日志，可能包含路径、请求参数和 traceback。
fix_records/*.md         是本地自动修复记录，可能包含模型输出、旧代码快照和本机路径。
__pycache__/.pytest_cache 是 Python 和 pytest 运行缓存。
external_repos/          是本地联调用外部仓库，不属于当前项目源码。
CLAUDE.md                是本地开发/协作配置，不作为项目发布内容。
```

### 打 tag 示例

确认工作区只包含要发布的改动后：

```bash
git status --short
git add .
git commit -m "chore: release v0.1.0"
git tag v0.1.0
git push origin HEAD
git push origin v0.1.0
```

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
