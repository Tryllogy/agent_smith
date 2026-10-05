from mcp.server.fastmcp import FastMCP

from mcp_tools.config import configure_from_argv
from mcp_tools.tools_exec import get_patch, run_command, run_tests
from mcp_tools.tools_fs import edit_file, list_files, read_file
from mcp_tools.tools_search import (
    find_references,
    search_code,
    search_function_or_class_definition_in_code,
)

mcp = FastMCP("swebench-tools")
mcp.add_tool(read_file)
mcp.add_tool(edit_file)
mcp.add_tool(list_files)
mcp.add_tool(search_code)
mcp.add_tool(search_function_or_class_definition_in_code)
mcp.add_tool(find_references)
mcp.add_tool(run_tests)
mcp.add_tool(get_patch)
mcp.add_tool(run_command)

if __name__ == "__main__":
    args = configure_from_argv("swebench")
    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
