import asyncio
import sys
from app.agent.mcp.tools_loader import load_mcp_tools
from app.agent.nodes import tool_manager

async def main():
    tools = await load_mcp_tools()
    sys.stdout.buffer.write(f"Loaded {len(tools)} MCP tools:\n".encode('utf-8'))
    for t in tools:
        sys.stdout.buffer.write(f"  - {t.name}\n".encode('utf-8'))
        sys.stdout.buffer.write(f"    desc: {t.description[:200]}\n".encode('utf-8'))

asyncio.run(main())
