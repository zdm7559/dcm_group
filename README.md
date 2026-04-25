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
```

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

如果环境中已经安装过依赖，可以跳过这一步。

## 启动服务

```bash
cd /home/zhaodongmin/飞书挑战赛/project
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
