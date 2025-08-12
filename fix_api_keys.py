#!/usr/bin/env python
"""
Fix script to ensure API keys are properly configured throughout the system
"""

import os
import sys

def fix_api_keys():
    """Apply comprehensive fix for API key issues"""
    
    print("=" * 60)
    print("Applying API Key Fix")
    print("=" * 60)
    
    # Get API keys from environment
    api_key1 = os.environ.get('GOOGLE_API_KEY')
    api_key2 = os.environ.get('GOOGLE_API_KEY2')
    
    if not (api_key1 or api_key2):
        print("❌ No API keys found in environment variables!")
        print("Please set GOOGLE_API_KEY and/or GOOGLE_API_KEY2")
        return False
    
    print(f"✅ Found API keys:")
    if api_key1:
        print(f"   GOOGLE_API_KEY: {api_key1[:10]}...")
    if api_key2:
        print(f"   GOOGLE_API_KEY2: {api_key2[:10]}...")
    
    # Fix 1: Create .env file in gemini-engines if it doesn't exist
    env_path = "gemini-engines/.env"
    if not os.path.exists(env_path):
        print(f"\n📝 Creating {env_path} with API keys...")
        with open(env_path, 'w') as f:
            if api_key1:
                f.write(f"GOOGLE_API_KEY={api_key1}\n")
            if api_key2:
                f.write(f"GOOGLE_API_KEY2={api_key2}\n")
        print(f"   ✅ Created {env_path}")
    else:
        print(f"\n✅ {env_path} already exists")
    
    # Fix 2: Create .env file in root if it doesn't exist
    root_env_path = ".env"
    if not os.path.exists(root_env_path):
        print(f"\n📝 Creating {root_env_path} with API keys...")
        with open(root_env_path, 'w') as f:
            if api_key1:
                f.write(f"GOOGLE_API_KEY={api_key1}\n")
            if api_key2:
                f.write(f"GOOGLE_API_KEY2={api_key2}\n")
        print(f"   ✅ Created {root_env_path}")
    else:
        print(f"\n✅ {root_env_path} already exists")
    
    print("\n" + "=" * 60)
    print("API Key Fix Applied Successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Restart the MCP server connection")
    print("2. Test the smart tools through MCP")
    
    return True

if __name__ == "__main__":
    success = fix_api_keys()
    sys.exit(0 if success else 1)