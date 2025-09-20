import asyncio

from fastmcp import Client


async def test_oauth():
    async with Client(
        "https://gorilla-major-literally.ngrok-free.app/mcp", auth="oauth"
    ) as client:
        # Test basic tool
        result1 = await client.call_tool("get_last_run_statistics", {})
        print(result1)


asyncio.run(test_oauth())
