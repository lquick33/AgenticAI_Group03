"""
MCP Server that exposes the UrlFetcherTool as an MCP tool.

This server can be run as a standalone MCP server using stdio transport.
"""

import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import the UrlFetcherTool from the parent package
from agentic_ai.tools.url_fetcher import UrlFetcherTool


# Create the server instance
server = Server("url-fetcher-mcp-server")

# Create the tool instance
url_fetcher = UrlFetcherTool()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="fetch_url",
            description=url_fetcher.description,
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch (must be a valid HTTP/HTTPS URL)"
                    },
                    "extract_text": {
                        "type": "boolean",
                        "description": "Whether to extract text from HTML (default: True). Set to False to get raw HTML.",
                        "default": True
                    }
                },
                "required": ["url"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    if name == "fetch_url":
        url = arguments.get("url")
        extract_text = arguments.get("extract_text", True)
        
        if not url:
            return [TextContent(
                type="text",
                text="Error: 'url' parameter is required"
            )]
        
        try:
            # Call the tool's _run method
            result = url_fetcher._run(url=url, extract_text=extract_text)
            return [TextContent(
                type="text",
                text=result
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error fetching URL: {str(e)}"
            )]
    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


async def main():
    """Run the MCP server using stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

