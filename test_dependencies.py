#!/usr/bin/env python3
"""
Test script to validate dependency changes
"""
import sys
import os

# Add gemini-engines to path
gemini_engines_path = os.path.join(os.path.dirname(__file__), 'gemini-engines')
sys.path.insert(0, gemini_engines_path)

def test_setup_parsing():
    """Test that setup.py can be parsed correctly"""
    try:
        # Read setup.py and check for basic structure
        setup_path = os.path.join(gemini_engines_path, 'setup.py')
        with open(setup_path, 'r') as f:
            content = f.read()
        
        # Basic validation
        assert 'version="1.2.0-beta.1"' in content, "Version not updated correctly"
        assert '"Development Status :: 4 - Beta"' in content, "Status not updated to Beta"
        assert 'google-generativeai>=0.8.0' in content, "google-generativeai version not updated"
        assert 'mcp>=1.0.0' in content, "mcp version not updated"
        assert 'mypy>=1.0.0' in content, "mypy not in dev dependencies"
        
        print("✅ setup.py validation passed")
        return True
    except Exception as e:
        print(f"❌ setup.py validation failed: {e}")
        return False

def test_requirements_cleanup():
    """Test that requirements.txt has been cleaned up"""
    try:
        req_path = os.path.join(gemini_engines_path, 'requirements.txt')
        with open(req_path, 'r') as f:
            content = f.read()
        
        # Check that legacy packages are removed (ignore comments)
        lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('#')]
        content_no_comments = '\n'.join(lines)
        
        assert 'anthropic>=' not in content_no_comments, "anthropic dependency should be removed from requirements.txt"
        assert 'asyncio-mqtt' not in content_no_comments, "asyncio-mqtt should be removed"
        assert 'protobuf' not in content_no_comments, "protobuf should be removed"
        
        # Check that dev dependencies are removed
        assert 'pytest>=' not in content, "pytest should be moved to setup.py dev dependencies"
        assert 'mypy>=' not in content, "mypy should be moved to setup.py dev dependencies"
        
        # Check that production dependencies are present
        assert 'google-generativeai>=0.8.0' in content, "Core dependencies should remain"
        assert 'mcp>=1.0.0' in content, "MCP should remain"
        
        print("✅ requirements.txt cleanup validated")
        return True
    except Exception as e:
        print(f"❌ requirements.txt validation failed: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Testing dependency fixes...")
    
    setup_ok = test_setup_parsing()
    req_ok = test_requirements_cleanup()
    
    if setup_ok and req_ok:
        print("\n🎉 All dependency fixes validated successfully!")
        print("✅ Version updated to 1.2.0-beta.1")
        print("✅ Status downgraded to Beta")  
        print("✅ Dependencies harmonized between setup.py and requirements.txt")
        print("✅ Legacy packages removed")
        print("✅ Development dependencies moved to extras_require")
    else:
        print("\n❌ Some validation checks failed")
        sys.exit(1)