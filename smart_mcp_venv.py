#!/usr/bin/env python3
"""
VENV-Compatible Smart Tools MCP Server
Ensures proper working directory and path setup when launched from VENV environments
"""

import os
import sys
import logging

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_venv_environment():
    """Setup environment for VENV compatibility"""
    
    # CRITICAL: Determine project root from script location
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(script_path)
    
    logger.info(f"Script location: {script_path}")
    logger.info(f"Project root: {project_root}")
    logger.info(f"Current working directory: {os.getcwd()}")
    
    # CRITICAL: Change to project root
    if os.getcwd() != project_root:
        os.chdir(project_root)
        logger.info(f"Changed working directory to: {project_root}")
    
    # CRITICAL: Add project paths to sys.path
    paths_to_add = [
        project_root,  # Root for local imports
        os.path.join(project_root, "src"),  # Source directory
        os.path.join(project_root, "gemini-engines"),  # Gemini engines
    ]
    
    for path in paths_to_add:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added to Python path: {path}")
    
    # Verify critical paths exist
    gemini_engines_path = os.path.join(project_root, "gemini-engines")
    if not os.path.exists(gemini_engines_path):
        logger.error(f"CRITICAL: gemini-engines directory not found at: {gemini_engines_path}")
        raise FileNotFoundError(f"gemini-engines directory not found: {gemini_engines_path}")
    
    src_path = os.path.join(project_root, "src")
    if not os.path.exists(src_path):
        logger.error(f"CRITICAL: src directory not found at: {src_path}")
        raise FileNotFoundError(f"src directory not found: {src_path}")
        
    logger.info("✅ VENV environment setup complete")

async def main():
    """Main entry point"""
    try:
        logger.info("=== Smart Tools VENV MCP Server Starting ===")
        
        # Setup VENV-compatible environment
        setup_venv_environment()
        
        # Import and run the actual MCP server main function
        from smart_mcp_server import main as server_main
        
        # Run the server
        await server_main()
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("This typically means the path setup failed")
        logger.error(f"Current sys.path: {sys.path}")
        raise
    except Exception as e:
        logger.error(f"Failed to start Smart Tools MCP server: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())