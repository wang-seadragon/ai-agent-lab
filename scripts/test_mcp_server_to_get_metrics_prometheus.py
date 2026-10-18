import asyncio
from app.mcp_client import create_mcp_client

async def main():
    client = create_mcp_client()
    tools = await client.get_tools()

    metrics_tool = next(
        t for t in tools
        if t.name == "get_incident_metrics_mcp"
    )

    result = await metrics_tool.ainvoke({
        "incident_id": "LAB-INC-1"
    })

    print(result)

asyncio.run(main())