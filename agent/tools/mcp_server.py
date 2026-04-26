from typing import Any
import sys
from typing import Literal, Annotated
from pydantic import Field
import os
from dotenv import load_dotenv
from read_file import read_file_content
import json

DEFAULT_MAX_CHARS = 8000

load_dotenv()

from mcp.server.fastmcp import FastMCP

# 初始化 FastMCP 服务器
mcp = FastMCP[Any]("WaterLeakDetection")
"""
在复杂的 MCP 服务器中,你的各个工具(Tools)往往需要共享一些“上下文”或“依赖项”
（比如：全局的数据库连接池、配置信息、用户认证状态等）。

FastMCP 允许你把这些共享状态作为一个对象传递给各个工具函数.
为了让代码编辑器(如 VS Code)能准确知道这个共享状态是什么
类型并提供代码补全,FastMCP 就设计成了泛型:FastMCP[你的上下文类型]。
"""


# 使用 @mcp.tool() 装饰器将普通函数转换为 MCP 工具
@mcp.tool()
def read_file(
    file_path: str,
    encoding: str = "utf-8",
    max_chars: int = DEFAULT_MAX_CHARS,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """
    "读取文本文件内容。适合查看配置文件、日志文件和代码文件。"
    "输入 file_path，必要时可传 start_line、end_line、encoding、max_chars。"
    
    Args:
        file_path: 文件路径
        encoding:文件编码方式
        max_chars:文件最大可读长度
        start_line:开始读的位置（非必须）
        end_line:结束读的位置（非必须）
    """
    result = read_file_content(
        file_path=file_path,
        encoding=encoding,
        max_chars=max_chars,
        start_line=start_line,
        end_line=end_line,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)






if __name__ == "__main__":
    # 运行 MCP 服务器 (默认使用 stdio 标准输入输出进行通信)
    mcp.run()