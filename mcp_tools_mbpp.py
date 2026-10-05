from mcp.server.fastmcp import FastMCP

from mcp_tools.config import configure_from_argv
from mcp_tools.tools_mbpp import run_tests

mcp = FastMCP("mbpp-tools")
mcp.add_tool(run_tests)

if __name__ == "__main__":
    args = configure_from_argv("mbpp")
    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
