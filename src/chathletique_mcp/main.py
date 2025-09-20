"""MCP Server Template"""

# Import modules containing MCP tools to register them
from .mcp_utils import auth, mcp


def main():
    """Main entry point for the MCP server."""
    # run both apps in one file
    # Don't deploy in prod
    import threading

    # Start MCP server in another thread
    threading.Thread(
        target=lambda: mcp.run(
            transport="streamable-http", port=3000, stateless_http=True
        ),
        daemon=True,
    ).start()

    # Run FastAPI server (blocks main thread)
    import uvicorn

    uvicorn.run(auth, port=8000)


if __name__ == "__main__":
    main()
