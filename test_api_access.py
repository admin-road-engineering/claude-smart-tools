#!/usr/bin/env python
"""Test if the smart tools can access Gemini API"""

import os
import sys
import asyncio

# Add paths
sys.path.insert(0, 'src')
sys.path.insert(0, 'gemini-engines/src')

async def test_api():
    print("=" * 60)
    print("Testing Smart Tools API Access")
    print("=" * 60)
    
    # Test environment variables
    print("\n1. Environment Variables:")
    print(f"   GOOGLE_API_KEY: {'SET' if os.environ.get('GOOGLE_API_KEY') else 'NOT SET'}")
    print(f"   GOOGLE_API_KEY2: {'SET' if os.environ.get('GOOGLE_API_KEY2') else 'NOT SET'}")
    
    # Test smart tools config
    try:
        from config import config as smart_config
        print("\n2. Smart Tools Config:")
        print(f"   API Key 1: {smart_config.google_api_key[:10] if smart_config.google_api_key else 'NONE'}")
        print(f"   API Key 2: {smart_config.google_api_key2[:10] if smart_config.google_api_key2 else 'NONE'}")
        print(f"   Number of keys: {len(smart_config.api_keys)}")
    except Exception as e:
        print(f"   Error loading smart config: {e}")
    
    # Test gemini-engines config
    try:
        os.chdir('gemini-engines')
        sys.path.insert(0, os.getcwd())
        from src.config import config as gemini_config
        print("\n3. Gemini Engines Config:")
        print(f"   API Key 1: {gemini_config.google_api_key[:10] if gemini_config.google_api_key else 'NONE'}")
        print(f"   API Key 2: {gemini_config.google_api_key2[:10] if gemini_config.google_api_key2 else 'NONE'}")
        os.chdir('..')
    except Exception as e:
        print(f"   Error loading gemini config: {e}")
    
    # Test actual Gemini API call
    try:
        import google.generativeai as genai
        print("\n4. Testing Gemini API:")
        genai.configure(api_key=os.environ.get('GOOGLE_API_KEY'))
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content('Say "API working"')
        print(f"   Response: {response.text[:50]}")
        print("   ✅ API ACCESS SUCCESSFUL")
    except Exception as e:
        print(f"   ❌ API ERROR: {e}")
    
    # Test smart tool engine loading
    try:
        from engines.original_tool_adapter import OriginalToolAdapter
        print("\n5. Testing Engine Loading:")
        tool_impl, client, config = OriginalToolAdapter.import_original_implementations()
        if tool_impl:
            print("   ✅ Engines loaded successfully")
        else:
            print("   ❌ Failed to load engines")
    except Exception as e:
        print(f"   ❌ Engine loading error: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())