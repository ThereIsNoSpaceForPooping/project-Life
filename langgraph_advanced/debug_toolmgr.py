"""运行时探针：直接查询 tool_manager 内部的实际状态"""
import asyncio
import sys
from app.agent.nodes import tool_manager
from app.agent.mcp.tools_loader import load_mcp_tools, MCP_TOOL_PREFIX
from app.agent.a2a.tools_loader import load_a2a_tools

async def main():
    # 1. 探针：tool_manager 当前状态
    sys.stdout.buffer.write(b"=== Before force-load ===\n")
    sys.stdout.buffer.write(f"all_tools count: {len(tool_manager.get_all_tools())}\n".encode('utf-8'))
    sys.stdout.buffer.write(f"mcp_tools count: {len(tool_manager.get_mcp_tools())}\n".encode('utf-8'))
    sys.stdout.buffer.write(f"a2a_tools count: {len(tool_manager.get_a2a_tools())}\n".encode('utf-8'))

    # 2. 主动调一次 load
    sys.stdout.buffer.write(b"\n=== Force load ===\n")
    mcp_loaded = await load_mcp_tools()
    a2a_loaded = await load_a2a_tools()
    sys.stdout.buffer.write(f"load_mcp_tools returned: {len(mcp_loaded)} tools\n".encode('utf-8'))
    sys.stdout.buffer.write(f"load_a2a_tools returned: {len(a2a_loaded)} tools\n".encode('utf-8'))

    # 3. 探针：load 后状态
    sys.stdout.buffer.write(b"\n=== After load ===\n")
    sys.stdout.buffer.write(f"all_tools count: {len(tool_manager.get_all_tools())}\n".encode('utf-8'))
    sys.stdout.buffer.write(f"mcp_tools count: {len(tool_manager.get_mcp_tools())}\n".encode('utf-8'))
    sys.stdout.buffer.write(f"a2a_tools count: {len(tool_manager.get_a2a_tools())}\n".encode('utf-8'))

    sys.stdout.buffer.write(b"\n=== Tool names ===\n")
    for t in tool_manager.get_all_tools():
        sys.stdout.buffer.write(f"  - {t.name}\n".encode('utf-8'))

asyncio.run(main())
