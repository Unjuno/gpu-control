import pytest


@pytest.mark.parametrize("name", [[], {}, 1, True, None])
def test_mcp_non_string_tool_name_rejected(web, name):
    response = web.client.post("/mcp", headers=web.headers, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": {}},
    })
    assert response.status_code == 200
    assert response.json()["error"]["code"] == -32602
