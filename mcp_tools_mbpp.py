from mcp.server import MCPServer

from mcp_tools.config import configure_from_argv
from mcp_tools.tools_mbpp import run_tests

mcp = MCPServer("mbpp-tools")
mcp.add_tool(run_tests)

if __name__ == "__main__":
    args = configure_from_argv("mbpp")
    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")
