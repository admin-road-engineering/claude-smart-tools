#!/usr/bin/env python3
"""
MCP Server Wrapper Script for Claude Smart Tools
Handles Python path setup for proper imports when run by Claude Desktop
"""
import sys
import os
from pathlib import Path

# Get the directory containing this script and the src directory
script_dir = Path(__file__).parent.absolute()
src_dir = script_dir / "src"

# Add the src directory to Python path
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Change to the project directory
os.chdir(script_dir)

# Now import and run the actual MCP server
if __name__ == "__main__":
    try:
        # Import the main server function
        from src.smart_mcp_server import main
        
        # Run the server
        main()
    except Exception as e:
        print(f"Error starting MCP server: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)