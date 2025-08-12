#!/usr/bin/env python
"""Debug script to test MCP environment variables"""

import os
import sys
import json

def debug_env():
    print("=" * 60)
    print("MCP Server Environment Debug")
    print("=" * 60)
    
    # Check environment variables
    env_vars = {
        "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", "NOT SET"),
        "GOOGLE_API_KEY2": os.environ.get("GOOGLE_API_KEY2", "NOT SET"),
        "PATH": os.environ.get("PATH", "NOT SET")[:100] + "..." if len(os.environ.get("PATH", "")) > 100 else os.environ.get("PATH", "NOT SET")
    }
    
    print("\n1. Environment Variables:")
    for key, value in env_vars.items():
        if key.startswith("GOOGLE"):
            print(f"   {key}: {value[:10] if value != 'NOT SET' else 'NOT SET'}")
        else:
            print(f"   {key}: {value}")
    
    # Check if we're in MCP context
    print("\n2. MCP Context Check:")
    print(f"   Running as: {sys.argv[0]}")
    print(f"   Python executable: {sys.executable}")
    print(f"   Current directory: {os.getcwd()}")
    
    # Try to load configs
    print("\n3. Config Loading Test:")
    
    # Smart tools config
    try:
        sys.path.insert(0, 'src')
        from config import config
        print(f"   Smart Tools Config:")
        print(f"     - API Key 1: {config.google_api_key[:10] if config.google_api_key else 'NONE'}")
        print(f"     - API Key 2: {config.google_api_key2[:10] if config.google_api_key2 else 'NONE'}")
    except Exception as e:
        print(f"   Smart Tools Config Error: {e}")
    
    # Gemini engines config
    try:
        import os
        original_cwd = os.getcwd()
        os.chdir('gemini-engines')
        sys.path.insert(0, os.getcwd())
        from src.config import config as gemini_config
        print(f"   Gemini Engines Config:")
        print(f"     - API Key 1: {gemini_config.google_api_key[:10] if gemini_config.google_api_key else 'NONE'}")
        print(f"     - API Key 2: {gemini_config.google_api_key2[:10] if gemini_config.google_api_key2 else 'NONE'}")
        os.chdir(original_cwd)
    except Exception as e:
        print(f"   Gemini Engines Config Error: {e}")

if __name__ == "__main__":
    debug_env()