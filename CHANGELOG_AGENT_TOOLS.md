# Agent 工具层改动说明

本文档用于说明当前分支在 Agent 工具层新增的能力，方便队友在暂不合并分支的情况下了解改动范围和使用方式。

## 背景

项目当前目标是跑通 AutoFix Agent 的 MVP 闭环：

```text
Web 服务报错 -> 写入 logs/error.log -> Agent 读取日志 -> 定位代码 -> 修改代码 -> 运行测试 -> 提交修复记录/通知
```

队友此前已经实现了：

- `agent/tools/git_ops.py`：Git 分支、diff、commit、GitHub PR 等工具。
- `agent/tools/feishu_notify.py`：飞书卡片构造和 webhook 通知工具。

本分支补充了 Agent 修复流程前半段需要的两个工具：

- `agent/tools/read_log.py`
- `agent/tools/run_tests.py`

## 新增文件

### `agent/tools/read_log.py`

作用：读取并结构化解析 `logs/error.log`。

核心能力：

- 支持读取多个 `AUTO_FIX_BUG_START` / `AUTO_FIX_BUG_END` 日志块。
- 支持三种读取模式：
  - `all`：返回全部错误事件。
  - `latest`：返回最新错误事件。
  - `grouped`：按 fingerprint 聚合同类错误，默认模式。
- 为每条错误生成 `fingerprint`，用于识别同一种错误是否重复出现。
- 保留完整 `traceback`，同时额外提取：
  - `project_frames`：项目内 traceback 栈帧。
  - `suspect_frame`：最可能出错的项目代码位置。
  - `context_hints`：建议 Agent 优先读取的源码文件。

示例用法：

```python
from agent.tools import read_error_logs

result = read_error_logs(mode="grouped")
```

返回结构示例：

```json
{
  "ok": true,
  "data": {
    "mode": "grouped",
    "count": 2,
    "errors": [
      {
        "fingerprint": "379050a2308c3096",
        "occurrences": 5,
        "latest": {
          "path": "/divide",
          "exception_type": "ZeroDivisionError",
          "project_frames": [
            {
              "file": "web_service/api/routes/calculator.py",
              "line": 13,
              "function": "divide"
            },
            {
              "file": "web_service/services/calculator.py",
              "line": 5,
              "function": "divide_numbers"
            }
          ],
          "suspect_frame": {
            "file": "web_service/services/calculator.py",
            "line": 5,
            "function": "divide_numbers"
          },
          "context_hints": {
            "primary_file": "web_service/services/calculator.py",
            "files_to_read": [
              "web_service/services/calculator.py",
              "web_service/api/routes/calculator.py"
            ]
          }
        }
      }
    ],
    "invalid_blocks": []
  },
  "error": null
}
```

### `agent/tools/run_tests.py`

作用：在 Agent 修改代码后运行测试，判断修复是否成功。

核心能力：

- 默认执行当前 Python 环境下的 `python -m pytest tests/`。
- 支持自定义测试命令。
- 捕获：
  - `exit_code`
  - `stdout`
  - `stderr`
  - `summary`
- 支持超时控制。
- 返回统一 ToolResult 格式。

示例用法：

```python
from agent.tools import run_tests

result = run_tests(cwd=".")
```

返回结构示例：

```json
{
  "ok": false,
  "data": {
    "passed": false,
    "exit_code": 1,
    "command": ["...", "-m", "pytest", "tests/"],
    "stdout": "...",
    "stderr": "",
    "summary": "FAILED tests/test_service.py::test_divide_by_zero_should_return_400 ..."
  },
  "error": "tests failed"
}
```

## 更新文件

### `agent/tools/__init__.py`

新增导出：

```python
read_error_logs
read_latest_error_log
run_tests
```

因此 Agent 主流程后续可以直接这样导入：

```python
from agent.tools import read_error_logs, run_tests
```

## 当前预期测试结果

当前 Web 靶场中仍然故意保留两个 bug：

- `/divide?a=10&b=0` 当前返回 `500`，后续期望修复为 `400`。
- `/users/999` 当前返回 `500`，后续期望修复为 `404`。

因此当前运行：

```bash
python -m pytest tests/
```

预期结果是：

```text
3 passed, 2 failed
```

这不是工具层错误，而是靶场设计的一部分。后续 Agent 修复代码后，`run_tests` 应该返回 `ok: true`。

## 验证命令

```bash
python -m py_compile agent/tools/read_log.py agent/tools/run_tests.py agent/tools/__init__.py
python -m pytest tests/
```

## 后续接入 Agent 的建议流程

```text
read_error_logs(mode="grouped")
  -> Agent 选择要处理的错误
  -> 根据 context_hints.files_to_read 调用 read_file
  -> Agent 生成修复方案
  -> 写入代码
  -> run_tests()
  -> 测试通过后调用 git_ops / feishu_notify
```

## 备注

`read_log` 没有删除完整 traceback。它保留原始 `traceback`，并额外提取项目内栈帧，目的是同时保留完整诊断信息和提供稳定的源码定位提示。
