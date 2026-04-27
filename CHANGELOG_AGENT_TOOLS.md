# Agent 工具与 Workflow 变更说明

本文档记录 AutoFix Agent 工具层和主流程的阶段性版本变化，方便团队成员了解当前能力边界。

## v0.1.0

`v0.1.0` 是当前项目的第一个可运行闭环版本。它已经可以从 Web 服务错误日志出发，自动读取相关源码，调用大模型生成修复方案，安全写入代码，并通过目标测试验证修复结果。

### 核心能力

当前版本已经跑通如下主流程：

```text
Web 服务报错
  -> logs/error.log 写入结构化 traceback
  -> read_error_logs(mode="grouped") 读取并聚合同类错误
  -> read_files_for_error() 读取相关源码和测试上下文
  -> LLM diagnose 生成根因分析和修复策略
  -> LLM generate patch 生成 apply_replacements 操作
  -> apply_replacements() 安全写入源码
  -> py_compile 检查被修改 Python 文件的语法
  -> run_tests(command=targeted_test) 运行当前错误对应的目标测试
  -> save_fix_record() 保存本地修复记录
```

### 已验证场景

已通过本地验证的自动修复场景：

```text
/divide?a=10&b=0 -> ZeroDivisionError -> 自动修复为 400
/users/999       -> KeyError           -> 自动修复为 404
```

对应目标测试：

```text
tests/test_service.py::test_divide_by_zero_should_return_400
tests/test_service.py::test_user_not_found_should_return_404
```

### 新增 Agent 主流程文件

```text
agent/main.py          # 命令行入口
agent/workflow.py      # AutoFix 主流程编排
agent/llm_client.py    # OpenAI-compatible Chat Completions 客户端
agent/prompts.py       # 诊断和修复操作生成 prompt
agent/fix_records.py   # 保存本地修复记录
fix_records/.gitkeep   # 保留修复记录目录
```

运行方式：

```bash
python -m agent.main --max-attempts 3
```

### 工具层能力

#### `agent/tools/read_log.py`

负责读取并结构化解析 `logs/error.log`。

能力：

```text
读取多个 AUTO_FIX_BUG_START / AUTO_FIX_BUG_END 日志块
支持 all / latest / grouped 三种读取模式
按 fingerprint 聚合同类错误
保留完整 traceback
提取 project_frames、suspect_frame、context_hints
```

#### `agent/tools/read_file.py`

负责根据错误事件读取相关源码上下文。

能力：

```text
优先读取目标行所在的完整函数或异步函数
找不到函数时退回到目标行附近窗口
支持一次读取多个文件
可以直接消费 read_log 返回的 error_event
默认额外读取 tests/test_service.py，帮助模型理解验收标准
```

#### `agent/tools/write_file.py`

负责把大模型生成的修复安全写入源码文件。

能力：

```text
replace_in_file()      # 单点精确替换
apply_replacements()   # 多文件、多位置批量替换
write_file()           # 受保护的整文件写入
restore_files()        # 根据 before_contents 回滚本轮写入
```

关键保护：

```text
批量替换会先验证全部操作，再统一写回
old_text 必须唯一匹配
默认拒绝写入 .git、.env、logs/error.log、缓存目录等路径
写入结果包含 changed_files、file_hashes、before_contents
```

#### `agent/tools/run_tests.py`

负责运行测试并返回结构化结果。

能力：

```text
默认执行 python -m pytest tests/
支持自定义 command
返回 passed、exit_code、command、stdout、stderr、summary
支持 timeout
```

#### `agent/tools/git_ops.py`

提供后续接入 PR 流程需要的 Git / GitHub 能力：

```text
sync_base_branch()
create_branch()
git_diff()
git_commit()
create_pr()
```

#### `agent/tools/feishu_notify.py`

提供后续接入飞书通知需要的卡片能力：

```text
build_review_card()
send_feishu_card()
```

### 当前未接入主流程的能力

以下工具已经存在，但 `v0.1.0` 暂未接入 `agent/workflow.py` 的自动主链路：

```text
git_diff()
git_commit()
create_pr()
build_review_card()
send_feishu_card()
```

也就是说，当前版本的主链路到“保存本地修复记录”为止。PR 创建和飞书通知可以作为下一阶段能力接入。

### 版本边界

`v0.1.0` 当前采用手写 workflow，不依赖 LangChain / LangGraph 调度。这样做的原因是当前任务链路足够清晰，优先保证可运行、可验证、可回滚。

大模型只负责两件事：

```text
诊断根因
生成结构化替换操作
```

文件读取、文件写入、语法检查、测试运行、失败回滚都由确定性工具完成。

### 发版验证命令

建议在打 tag 前执行：

```bash
python -m py_compile agent/main.py agent/workflow.py agent/llm_client.py agent/prompts.py agent/fix_records.py
python -m py_compile agent/tools/read_log.py agent/tools/read_file.py agent/tools/run_tests.py agent/tools/write_file.py agent/tools/__init__.py
python -m pytest tests/
```

当前如果两个示例 bug 都已经被 Agent 修复，预期测试结果是：

```text
5 passed
```
