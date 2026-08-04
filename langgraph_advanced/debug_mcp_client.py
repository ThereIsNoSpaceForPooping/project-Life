import asyncio
import sys
from app.agent.mcp.simple_client import mcp_client

async def main():
    tools = await mcp_client.list_tools()
    sys.stdout.buffer.write(f"Got {len(tools)} tools\n".encode('utf-8'))
    for t in tools[:3]:
        name = t["name"]
        desc = t["description"]
        sys.stdout.buffer.write(f"tool: {name}\n".encode('utf-8'))
        sys.stdout.buffer.write(f"  desc type: {type(desc).__name__}\n".encode('utf-8'))
        sys.stdout.buffer.write(f"  desc repr: {repr(desc[:30])}\n".encode('utf-8'))
        sys.stdout.buffer.write(f"  desc bytes: {desc.encode('utf-8')[:30]}\n".encode('utf-8'))

asyncio.run(main())
