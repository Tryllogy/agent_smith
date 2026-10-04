from mcp.server import MCPServer

mcp = MCPServer("mbpp-tools")

if __name__ == "__main__":
    mcp.run(transport="stdio")
