"""FamilyVault MCP server — exposes the 5 Phase-1 tools for Goose."""
from mcp.server.fastmcp import FastMCP

from tools.photos import search_photos as _search_photos
from tools.projects import (
    list_projects as _list_projects,
    create_project as _create_project,
    get_project as _get_project,
    set_timeline as _set_timeline,
)

mcp = FastMCP("familyvault")

mcp.tool()(_search_photos)
mcp.tool()(_list_projects)
mcp.tool()(_create_project)
mcp.tool()(_get_project)
mcp.tool()(_set_timeline)


if __name__ == "__main__":
    mcp.run()  # stdio transport
