"""Exercise the Streamable HTTP surface with the official MCP Python client."""
import asyncio
import json

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from gpu_gateway.app import create_app


def test_official_sdk_lists_tools_and_calls_read_only_capabilities(web):
    app = create_app(web.settings, service=web.service, auth=web.auth)

    async def exercise_client():
        async with httpx2.AsyncClient(
            headers=web.headers,
            transport=httpx2.ASGITransport(app=app),
            base_url=web.settings.public_url,
            timeout=30,
        ) as http_client:
            transport = streamable_http_client(
                f"{web.settings.public_url}/mcp", http_client=http_client
            )
            async with Client(transport) as client:
                assert client.protocol_version == "2026-07-28"
                listing = await client.list_tools()
                assert {tool.name for tool in listing.tools} == {
                    "experiment_artifact",
                    "experiment_cancel",
                    "experiment_capabilities",
                    "experiment_list",
                    "experiment_prepare",
                    "experiment_result",
                    "experiment_status",
                    "experiment_submit",
                }

                capabilities = await client.call_tool(
                    "experiment_capabilities", {}
                )
                assert capabilities.is_error is False
                assert len(capabilities.content) == 1
                payload = json.loads(capabilities.content[0].text)
                assert payload["status"] == "blocked"
                assert payload["blocking_reason"] == "NO_QUEUEABLE_RESOURCE"

    asyncio.run(exercise_client())
