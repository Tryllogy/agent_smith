from mcp.server import MCPServer
from mcp_tools.tools_fs import read_file

mcp = MCPServer("swebench-tools")
mcp.add_tool(read_file)

if __name__ == "__main__":
    mcp.run(transport="stdio")
