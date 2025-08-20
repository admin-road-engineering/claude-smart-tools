#!/usr/bin/env python3
"""
Wrapper script for backward compatibility
Now uses the production server with full error handling and all features
"""
import sys
import os
import asyncio
import logging
from pathlib import Path

# CRITICAL: Set up logging BEFORE any other imports to capture startup failures
log_file_path = Path(__file__).parent.parent / "logs" / "startup.log"
log_file_path.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler(sys.stdout)  # For manual runs
    ]
)

logger = logging.getLogger(__name__)
logger.info("=== MCP SERVER STARTUP ===")
logger.info(f"Current Working Directory: {Path.cwd()}")
logger.info(f"Script location: {Path(__file__).resolve()}")
logger.info(f"Python path: {sys.path}")
logger.info(f"Python version: {sys.version}")

# Add the parent directory to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
logger.info(f"Added to Python path: {project_root}")

# Import the main server with Phase 2 Enhanced Tool Suite
try:
    logger.info("Importing GeminiMcpServer...")
    from src.mcp_server import GeminiMcpServer
    logger.info("GeminiMcpServer imported successfully")
except ImportError as e:
    logger.error(f"FATAL: Failed to import GeminiMcpServer: {e}")
    logger.error("Available modules in src/:")
    src_dir = Path(__file__).parent
    logger.error(f"Contents: {list(src_dir.glob('*.py'))}")
    raise

async def main():
    logger.info("Main function started")
    
    try:
        logger.info("Creating GeminiMcpServer instance...")
        server = GeminiMcpServer()
        logger.info("GeminiMcpServer created successfully")
        
        logger.info("Starting server run loop...")
        await server.run()
        logger.info("Server run completed")
        
    except Exception as e:
        logger.error(f"FATAL: Server failed to start: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())