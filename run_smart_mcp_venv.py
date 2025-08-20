#!/usr/bin/env python3
"""
VENV-Safe Smart Tools MCP Server Launcher
Ensures proper path setup and engine initialization when running in virtual environments
"""

import os
import sys

# CRITICAL: Set working directory to project root BEFORE any imports
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)

# CRITICAL: Add project root to Python path for imports
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# CRITICAL: Add src directory to path for internal imports
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# CRITICAL: Add gemini-engines to path for engine imports
gemini_engines_path = os.path.join(project_root, "gemini-engines")
if gemini_engines_path not in sys.path:
    sys.path.insert(0, gemini_engines_path)

# Now import and run the server
if __name__ == "__main__":
    # Import the main server module
    from src.smart_mcp_server import main
    
    # Run the server
    main()