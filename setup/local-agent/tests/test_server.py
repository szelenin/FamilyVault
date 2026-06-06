import asyncio


def test_server_registers_five_tools():
    import server
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "search_photos", "list_projects", "create_project",
        "get_project", "set_timeline",
    }
