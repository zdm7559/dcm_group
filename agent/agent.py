"""
react-agent


"""
import os
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# 初始化 OpenAI
client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
)

# 配置你要连接的 MCP 服务器路径
server_params = StdioServerParameters(
    command="python",
    args=["agent/tools/mcp_server.py"], # 确保路径正确
)

async def run_agent(user_msg: str):
    # 1. 启动并连接 MCP 服务器
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化会话
            await session.initialize()
            
            # 2. 从 MCP 服务器获取可用工具并转换为 OpenAI 格式
            mcp_tools = await session.list_tools()
            openai_tools = []
            for tool in mcp_tools.tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })

            messages = [{"role": "user", "content": user_msg}]
            
            # 3. 经典的 Agent 循环
            while True:
                resp = client.chat.completions.create(
                    model="qwen3-max",
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )
                msg = resp.choices[0].message
                messages.append(msg)

                if not msg.tool_calls:
                    return msg.content

                # 4. 当 LLM 决定调用工具时，委托给 MCP 服务器执行
                for tc in msg.tool_calls:
                    print(f"执行 MCP 工具: {tc.function.name}")
                    import json
                    args = json.loads(tc.function.arguments)
                    
                    # 通过 MCP 协议调用远端工具
                    mcp_result = await session.call_tool(tc.function.name, args)
                    
                    # 提取文本结果
                    #result_content = mcp_result.content[0].text if mcp_result.content else "No result"
                    # 将所有的返回块拼接成一个完整的字符串发给大模型
                    if mcp_result.content:
                        result_content = "\n".join([c.text for c in mcp_result.content if hasattr(c, 'text')])
                    else:
                        result_content = "No result"
                    #print(result_content)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_content
                    })

if __name__ == "__main__":
    user_msg = "查看web_service/services/calculator.py的文件内容"
    # 因为 MCP client 涉及异步通信，需要用 asyncio 运行
    result = asyncio.run(run_agent(user_msg))
    print("\n最终回答:\n", result)