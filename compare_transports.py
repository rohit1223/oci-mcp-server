#!/usr/bin/env python3
"""
Compare stdio vs streamable-http transport behavior
"""
import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.stdio import stdio_client

async def test_stdio():
    print("=== Testing STDIO Transport ===")
    try:
        # Test with stdio client
        async with stdio_client(
            command="python", 
            args=["src/server.py"],
            cwd="."
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ STDIO: Initialize successful")
                
                # Test tools/list
                tools = await session.list_tools()
                print(f"✅ STDIO: list_tools successful - {len(tools.tools)} tools")
                for tool in tools.tools:
                    print(f"   - {tool.name}: {tool.description}")
                
    except Exception as e:
        print(f"❌ STDIO: Failed - {e}")

async def test_streamable_http():
    print("\n=== Testing Streamable HTTP Transport ===")
    try:
        async with streamablehttp_client("http://127.0.0.1:8000") as (read, write, get_session):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ Streamable HTTP: Initialize successful")
                
                # Test tools/list
                tools = await session.list_tools()
                print(f"✅ Streamable HTTP: list_tools successful - {len(tools.tools)} tools")
                for tool in tools.tools:
                    print(f"   - {tool.name}: {tool.description}")
                
    except Exception as e:
        print(f"❌ Streamable HTTP: Failed - {e}")

async def main():
    await test_stdio()
    await test_streamable_http()

if __name__ == "__main__":
    asyncio.run(main())