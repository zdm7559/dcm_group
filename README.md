# AutoFix Agent Demo

这是一个用于演示 AutoFix 流程的最小项目。

项目目标不是实现复杂业务，而是稳定复现一组常见后端 bug，并把下面这条链路跑通：

```text
触发 bug -> 记录结构化错误日志 -> Agent 读取日志 -> 读取相关源码 -> 调用 LLM -> 生成修复操作 -> 修改代码 -> 运行定向测试 -> 保存修复记录
```

## 项目结构

```text
web_service/
  app.py                    FastAPI 应用入口
  api/
    router.py               路由汇总
    routes/                 各个 HTTP 接口
  core/
    config.py               项目路径、日志路径等配置
    error_handlers.py       全局异常处理与错误日志写入
    logging.py              错误日志 logger
  repositories/             简单数据访问层
  services/                 业务逻辑层，包含待修复 bug

agent/
  main.py                   命令行入口
  workflow.py               AutoFix 主流程
  llm_client.py             OpenAI-compatible LLM 客户端
  prompts.py                诊断与修复 prompt
  fix_records.py            修复记录落盘
  tools/
    read_log.py             读取并解析 logs/error.log
    read_file.py            读取错误相关源码上下文
    write_file.py           批量精确替换与回滚
    run_tests.py            执行 pytest 并返回结构化结果

tests/
  test_service.py           所有接口验收测试

scripts/
  trigger_bug.py            单条 bug 触发脚本

logs/
  error.log                 结构化错误日志

fix_records/
  *.md                      每次 agent 修复过程记录
```

## 环境准备

推荐直接使用仓库内虚拟环境。

安装依赖：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

复制环境变量模板：

```bash
cp .env.example .env
```

至少需要配置：

```bash
OPENAI_API_KEY="你的 API Key"
OPENAI_BASE_URL="https://api.openai.com/v1"
MODEL_NAME="gpt-4o-mini"
LLM_TEMPERATURE=""
```

其他可选变量：

```bash
FEISHU_WEBHOOK_URL="可选"
GITHUB_TOKEN="可选"
GIT_AUTHOR_NAME="AutoFix Agent"
GIT_AUTHOR_EMAIL="autofix-agent@example.com"
GIT_COMMITTER_NAME="AutoFix Agent"
GIT_COMMITTER_EMAIL="autofix-agent@example.com"
```

说明：

- `OPENAI_API_KEY`：LLM 调用必填
- `OPENAI_BASE_URL`：兼容 OpenAI Chat Completions 的服务地址
- `MODEL_NAME`：使用的模型名
- `LLM_TEMPERATURE`：可留空，留空时不传 temperature
- `FEISHU_WEBHOOK_URL`、`GITHUB_TOKEN`：当前主流程不是必须

## 启动服务

```bash
.venv/bin/python -m uvicorn web_service.app:app --reload
```

默认地址：

```text
http://127.0.0.1:8000
```

文档地址：

```text
http://127.0.0.1:8000/docs
```

## 正常接口

```bash
curl 'http://127.0.0.1:8000/health'
curl 'http://127.0.0.1:8000/divide?a=10&b=2'
curl 'http://127.0.0.1:8000/users/1'
```

## Bug Case 列表

项目目前维护了 22 个可稳定触发的 bug case，全部都在 [tests/test_service.py](tests/test_service.py) 里有对应测试。

| case | 请求路径 | 典型异常 | 对应测试 |
|---|---|---|---|
| `divide` | `/divide?a=10&b=0` | `ZeroDivisionError` | `test_divide_by_zero_should_return_400` |
| `user` | `/users/999` | `KeyError` | `test_user_not_found_should_return_404` |
| `invalid-json` | `/request/invalid-json` | `JSONDecodeError` | `test_invalid_json_should_return_400` |
| `missing-config` | `/files/missing-config` | `FileNotFoundError` | `test_missing_config_should_not_return_500` |
| `missing-log-dir` | `/files/missing-log-dir` | `FileNotFoundError` | `test_missing_log_dir_should_create_directory` |
| `missing-api-key` | `/config/missing-api-key` | `KeyError` | `test_missing_api_key_should_return_client_or_service_error` |
| `invalid-timeout` | `/config/invalid-timeout` | `ValueError` | `test_invalid_timeout_should_return_400` |
| `missing-yaml` | `/dependencies/missing-yaml` | `ModuleNotFoundError` | `test_missing_yaml_should_not_return_500` |
| `bad-import` | `/dependencies/bad-import` | `ModuleNotFoundError` | `test_bad_import_should_not_return_500` |
| `unknown-function` | `/naming/unknown-function` | `NameError` | `test_unknown_function_should_return_200` |
| `missing-profile` | `/data/missing-profile` | `AttributeError` | `test_missing_profile_should_return_404` |
| `not-found-as-500` | `/resources/not-found-as-500` | `ValueError` | `test_not_found_resource_should_return_404` |
| `missing-required` | `/validation/missing-required?name=Alice` | `KeyError` | `test_missing_required_param_should_return_400` |
| `bad-age` | `/validation/bad-age?age=abc` | `ValueError` | `test_bad_age_param_should_return_400` |
| `bad-range` | `/validation/bad-range?page=-1&limit=0` | `ZeroDivisionError` | `test_bad_range_param_should_return_400` |
| `empty-username` | `/validation/empty-username?username=` | `IndexError` | `test_empty_username_should_return_400` |
| `missing-user-null` | `/nulls/missing-user` | `TypeError` | `test_missing_user_null_should_return_404` |
| `none-email` | `/nulls/none-email` | `AttributeError` | `test_none_email_should_return_400` |
| `missing-body-age` | `/body/missing-age` | `KeyError` | `test_missing_body_age_should_return_400` |
| `int-string` | `/conversion/int-string?value=abc` | `ValueError` | `test_int_string_should_return_400` |
| `float-string` | `/conversion/float-string?value=hello` | `ValueError` | `test_float_string_should_return_400` |
| `bad-date` | `/conversion/bad-date?date=2026-99-99` | `ValueError` | `test_bad_date_should_return_400` |

## 触发单条 Bug

使用脚本触发最方便：

```bash
.venv/bin/python scripts/trigger_bug.py divide
.venv/bin/python scripts/trigger_bug.py user
.venv/bin/python scripts/trigger_bug.py invalid-json
```

完整可选值：

```text
divide
user
invalid-json
missing-config
missing-log-dir
missing-api-key
invalid-timeout
missing-yaml
bad-import
unknown-function
missing-profile
not-found-as-500
missing-required
bad-age
bad-range
empty-username
missing-user-null
none-email
missing-body-age
int-string
float-string
bad-date
```

如果你只想看某一条 bug 的日志，建议先清空旧日志：

```bash
: > logs/error.log
.venv/bin/python scripts/trigger_bug.py divide
tail -n 80 logs/error.log
```

错误日志格式如下：

```text
=== AUTO_FIX_BUG_START ===
{
  "timestamp": "...",
  "service": "demo-web-service",
  "method": "GET",
  "path": "/divide",
  "status_code": 500,
  "exception_type": "ZeroDivisionError",
  "exception_message": "float division by zero",
  "traceback": "..."
}
=== AUTO_FIX_BUG_END ===
```

`logs/error.log` 是 agent 的核心输入。

## 运行测试

全量测试：

```bash
.venv/bin/python -m pytest tests/
```

单条测试：

```bash
.venv/bin/python -m pytest tests/test_service.py::test_divide_by_zero_should_return_400 -q
.venv/bin/python -m pytest tests/test_service.py::test_user_not_found_should_return_404 -q
```

说明：

- `tests/test_service.py` 同时包含正常路径测试和异常修复验收测试
- 当前仓库设计上允许一部分测试初始失败，因为这些失败就是 AutoFix 的修复目标
- 测试中使用 `ASGITransport` 直连应用，因此跑 pytest 时不需要先启动 uvicorn

## 单条调试流程

最推荐的单条调试流程如下。

1. 启动服务

```bash
.venv/bin/python -m uvicorn web_service.app:app --reload
```

2. 清空旧日志

```bash
: > logs/error.log
```

3. 触发单条 bug

```bash
.venv/bin/python scripts/trigger_bug.py divide
```

4. 查看这条 bug 的日志

```bash
tail -n 80 logs/error.log
```

5. 跑对应单测

```bash
.venv/bin/python -m pytest tests/test_service.py::test_divide_by_zero_should_return_400 -q
```

6. 运行 agent

```bash
.venv/bin/python -m agent.main --repo-path . --max-attempts 3
```

7. 再次验证单测

```bash
.venv/bin/python -m pytest tests/test_service.py::test_divide_by_zero_should_return_400 -q
```

## 批量修复模式

默认情况下，agent 每次只选择 `logs/error.log` 里的一个错误分组进行修复。

如果要顺序修复日志中的所有错误分组，可以使用：

```bash
.venv/bin/python -m agent.main --repo-path . --max-attempts 3 --all
```

默认输出是按阶段展示的进度日志。如果需要保留完整结构化结果，可以加 `--json`：

```bash
.venv/bin/python -m agent.main --repo-path . --max-attempts 3 --all --json
```

## Agent 主流程

入口文件：

```text
agent/main.py
  -> agent/workflow.py::run_once()
```

主流程是：

```text
read_error_logs
-> select_error
-> read_files_for_error
-> call_llm(诊断)
-> call_llm(修复操作)
-> apply_replacements
-> 语法检查
-> 跑定向 pytest
-> 成功则保存 fix_record
-> 失败则回滚并重试
```

当前 `workflow.py` 会优先跑定向测试，而不是每次都跑全量 `tests/`。

例如：

- `/divide` -> `tests/test_service.py::test_divide_by_zero_should_return_400`
- `/users/999` -> `tests/test_service.py::test_user_not_found_should_return_404`
- `/config/invalid-timeout` -> `tests/test_service.py::test_invalid_timeout_should_return_400`

如果没有命中任何已知映射，才会回退到：

```bash
.venv/bin/python -m pytest tests/
```

## 运行 Agent

运行一次：

```bash
.venv/bin/python -m agent.main --repo-path . --max-attempts 3
```

输出是结构化 JSON，大致包含：

- `ok`
- `error`
- `data.error`：本次选择的错误事件
- `data.diagnosis`：LLM 根因分析
- `data.write_result`：改动文件信息
- `data.test_result`：目标测试结果
- `data.record`：修复记录路径

如果修复成功，源码会直接写回项目原文件。

如果测试失败或语法检查失败，当前尝试的改动会自动回滚。

## 修复记录

每次成功或最终失败，都会在 `fix_records/` 下生成 Markdown 记录：

```text
fix_records/<timestamp>-<exception_type>-<fingerprint>.md
```

可以这样查看最新记录：

```bash
ls -lt fix_records | head
cat "$(ls -t fix_records/*.md | head -n 1)"
```

## 如何查看 agent 改了哪些文件

```bash
git diff -- web_service agent tests
```

如果只想看本次修改的文件名：

```bash
git diff --name-only
```

## 如何回退 agent 的修复

如果还没有提交 commit，最稳妥的方式是按文件回退：

```bash
git restore web_service/api/routes/calculator.py
git restore web_service/services/calculator.py
```

不要直接使用下面这种全量回退，除非你确认工作区里没有别的改动：

```bash
git restore .
```

如果已经提交过修复 commit，推荐使用：

```bash
git revert <commit>
```

## 当前项目状态说明

这个项目是一个 bug 靶场，不保证默认全量测试全部通过。

当前更适合这样理解它：

- 服务层故意保留一批常见错误模式
- 测试定义了这些错误修复后的目标行为
- Agent 负责根据日志和测试把某一条错误自动修掉

因此：

- 初始失败是正常的
- 日志能稳定产出很重要
- 定向测试能稳定定位很重要
- 自动回滚很重要

## 一个最小完整示例

终端 1：

```bash
cd /Users/chailyn/Desktop/comp/dcm_group
.venv/bin/python -m uvicorn web_service.app:app --reload
```

终端 2：

```bash
cd /Users/chailyn/Desktop/comp/dcm_group
: > logs/error.log
.venv/bin/python scripts/trigger_bug.py divide
tail -n 80 logs/error.log
.venv/bin/python -m agent.main --repo-path . --max-attempts 3
.venv/bin/python -m pytest tests/test_service.py::test_divide_by_zero_should_return_400 -q
```

这套流程覆盖了这个项目最核心的闭环。
