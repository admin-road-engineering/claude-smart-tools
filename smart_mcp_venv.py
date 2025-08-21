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
    
    # NEW: Store original user directory before changing
    original_cwd = os.getcwd()
    os.environ['SMART_TOOLS_USER_DIR'] = original_cwd
    logger.info(f"Stored user's original directory: {original_cwd}")
    
    logger.info("=== COMPREHENSIVE VENV DIAGNOSTIC INFORMATION ===")
    logger.info(f"Script location: {script_path}")
    logger.info(f"Project root: {project_root}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Python executable: {sys.executable}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Current sys.path (first 5 entries): {sys.path[:5]}")
    
    # Log environment variables that might affect path resolution
    important_env_vars = ['PYTHONPATH', 'PATH', 'VIRTUAL_ENV', 'CONDA_DEFAULT_ENV']
    for var in important_env_vars:
        value = os.environ.get(var, 'NOT SET')
        logger.info(f"Environment {var}: {value}")
    
    # CRITICAL: Change to project root
    if os.getcwd() != project_root:
        os.chdir(project_root)
        logger.info(f"Changed working directory to: {project_root}")
        logger.info(f"Verified new working directory: {os.getcwd()}")
    
    # CRITICAL: Add project paths to sys.path
    paths_to_add = [
        project_root,  # Root for local imports
        os.path.join(project_root, "src"),  # Source directory
        os.path.join(project_root, "gemini-engines"),  # Gemini engines
    ]
    
    logger.info("=== PATH SETUP DIAGNOSTIC ===")
    for path in paths_to_add:
        abs_path = os.path.abspath(path)
        exists = os.path.exists(abs_path)
        in_path = abs_path in sys.path
        logger.info(f"Path: {abs_path}")
        logger.info(f"  Exists: {exists}")
        logger.info(f"  In sys.path: {in_path}")
        
        if exists and not in_path:
            sys.path.insert(0, abs_path)
            logger.info(f"  ✅ Added to Python path: {abs_path}")
        elif not exists:
            logger.error(f"  ❌ Path does not exist: {abs_path}")
    
    # Verify critical paths exist and log contents
    verification_paths = {
        'project_root': project_root,
        'src': os.path.join(project_root, "src"),
        'gemini-engines': os.path.join(project_root, "gemini-engines"),
        'src/smart_tools': os.path.join(project_root, "src", "smart_tools"),
        'src/engines': os.path.join(project_root, "src", "engines")
    }
    
    logger.info("=== PATH VERIFICATION DIAGNOSTIC ===")
    for name, path in verification_paths.items():
        abs_path = os.path.abspath(path)
        exists = os.path.exists(abs_path)
        logger.info(f"{name}: {abs_path} - {'EXISTS' if exists else 'NOT FOUND'}")
        
        if exists and os.path.isdir(abs_path):
            try:
                contents = os.listdir(abs_path)[:10]  # First 10 items
                logger.info(f"  Contents (first 10): {contents}")
            except Exception as e:
                logger.error(f"  Error listing contents: {e}")
    
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
    logger.info("=== END DIAGNOSTIC INFORMATION ===")

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