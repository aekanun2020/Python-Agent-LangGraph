"""ตรวจการเชื่อมต่อ MCP MSSQL จริง (ngrok) + ค้นพบ tools และ schema."""
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

URL = "https://9f9a-184-22-55-183.ngrok-free.app/mcp"


async def main():
    client = MultiServerMCPClient(
        {"mssql": {"url": URL, "transport": "streamable_http"}}
    )
    tools = await client.get_tools()
    print(f"[MCP] connected. discovered {len(tools)} tools:\n")
    for t in tools:
        print("=" * 60)
        print(f"name        : {t.name}")
        print(f"description : {t.description}")
        try:
            schema = t.args_schema
            print(f"args        : {schema}")
        except Exception as e:
            print(f"args        : (n/a) {e}")


if __name__ == "__main__":
    asyncio.run(main())
