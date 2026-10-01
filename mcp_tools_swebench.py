from mcp.server import MCPServer
from mcp_tools.tools_fs import read_file, edit_file, list_files
from mcp_tools.tools_exec import run_command, run_tests, get_patch
from mcp_tools.tools_search import search_code, find_references
from mcp_tools.tools_search import search_function_or_class_definition_in_code


mcp = MCPServer("swebench-tools")
mcp.add_tool(read_file)
mcp.add_tool(edit_file)
mcp.add_tool(list_files)
mcp.add_tool(run_command)
mcp.add_tool(run_tests)
mcp.add_tool(get_patch)
mcp.add_tool(search_code)
mcp.add_tool(search_function_or_class_definition_in_code)
mcp.add_tool(find_references)

if __name__ == "__main__":
    mcp.run(transport="stdio")
