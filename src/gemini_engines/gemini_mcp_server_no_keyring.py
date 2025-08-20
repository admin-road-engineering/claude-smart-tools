#!/usr/bin/env python3
"""
Simple MCP server entry point with keyring disabled
"""
import os
import sys
from pathlib import Path

# CRITICAL: Disable keyring before any imports
os.environ['DISABLE_KEYRING'] = '1'

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Now import and run the server
from src.gemini_mcp_server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())