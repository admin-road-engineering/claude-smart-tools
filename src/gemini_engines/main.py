#!/usr/bin/env python3
"""
Main entry point for Gemini MCP Server
"""
import asyncio
import logging
import os
import sys

from .mcp_server import GeminiMcpServer
from .config import LOG_LEVEL_VALUE, LOGS_DIR

# Configure logging - only to file when running as MCP server
os.makedirs(LOGS_DIR, exist_ok=True)

# Check if running as MCP server (has stdio streams) vs standalone
is_mcp_mode = not sys.stdin.isatty() or not sys.stdout.isatty()

handlers = [logging.FileHandler(f'{LOGS_DIR}/gemini_mcp_server.log')]
if not is_mcp_mode:
    # Only add console output when running standalone (for testing)
    handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=LOG_LEVEL_VALUE,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)

logger = logging.getLogger(__name__)

async def main():
    """Main entry point with dependency injection"""
    # Handle test mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_installation()
        return
        
    try:
        # Import only what's needed for simplified initialization
        logger.info("Starting MCP server initialization...")
        
        logger.info("Initializing MCP server with Phase 2 Enhanced Tool Suite...")
        
        # The GeminiMcpServer now handles all internal dependency injection
        # This simplification prevents the fragile initialization sequence
        server = GeminiMcpServer()
        
        logger.info("All services initialized successfully")
        await server.run()
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

def test_installation():
    """Test installation and configuration"""
    from pathlib import Path
    
    print("Testing Claude-Gemini MCP installation...")
    print()
    
    # Test 1: Check dependencies
    try:
        import google.generativeai as genai
        print("[OK] Google Generative AI library installed")
    except ImportError as e:
        print(f"[FAIL] Missing dependency: {e}")
        return False
    
    try:
        from mcp.server import Server
        print("[OK] MCP library installed")
    except ImportError as e:
        print(f"[FAIL] Missing MCP dependency: {e}")
        return False
    
    # Test 2: Check configuration
    try:
        from .config import API_KEYS, validate_config
        if API_KEYS:
            print(f"[OK] Found {len(API_KEYS)} API key(s)")
            if API_KEYS[0] != "your_api_key_here":
                print("[OK] API key configured (not default)")
            else:
                print("[WARN] Using default API key - please update .env file")
        else:
            print("[FAIL] No API keys configured")
            print("   Please add GOOGLE_API_KEY to .env file")
            return False
    except Exception as e:
        print(f"[FAIL] Configuration error: {e}")
        return False
    
    # Test 3: Check file structure
    required_files = [
        "src/main.py",
        "src/mcp_server.py", 
        "src/services/review_service.py",
        "src/clients/gemini_client.py",
        "src/config.py",
        "requirements.txt"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"[FAIL] Missing files: {', '.join(missing_files)}")
        return False
    else:
        print("[OK] All required files present")
    
    # Test 4: Test API connection (if configured)
    if API_KEYS and API_KEYS[0] != "your_api_key_here":
        try:
            print("[TEST] Testing API connection...")
            
            async def test_api():
                from .clients.gemini_client import GeminiClient
                client = GeminiClient(API_KEYS)
                try:
                    result = await client.generate_content(
                        prompt="Test connection. Respond with 'OK'.",
                        model_name="flash-lite",
                        timeout=10
                    )
                    print("[OK] API connection successful")
                    return True
                except Exception as e:
                    print(f"[FAIL] API connection failed: {e}")
                    return False
            
            # Can't use asyncio.run in test mode, skip API test
            print("[SKIP] API connection test (requires async context)")
            print("       API will be tested when MCP server starts")
                
        except Exception as e:
            print(f"[FAIL] API test error: {e}")
            return False
    
    # Test 5: Check logs directory
    logs_dir = Path("logs")
    if not logs_dir.exists():
        logs_dir.mkdir()
        print("[OK] Created logs directory")
    else:
        print("[OK] Logs directory exists")
    
    print()
    print("[SUCCESS] Installation test completed successfully!")
    print()
    print("Next steps:")
    print("1. Restart Claude Desktop")
    print("2. Test with: 'Review this code: print(\"hello\")'")
    print("3. Check logs/ directory for session data")
    print()
    return True

if __name__ == "__main__":
    asyncio.run(main())