#!/usr/bin/env python
"""Test script to debug import issues"""
import sys
import os

# Add paths
smart_tools_root = os.path.dirname(os.path.abspath(__file__))
gemini_engines_path = os.path.join(smart_tools_root, "gemini-engines")

print(f"Smart tools root: {smart_tools_root}")
print(f"Gemini engines path: {gemini_engines_path}")
print(f"Gemini engines exists: {os.path.exists(gemini_engines_path)}")

# Method 1: Direct chdir and import
print("\n=== Method 1: Direct chdir and import ===")
saved_cwd = os.getcwd()
os.chdir(gemini_engines_path)
sys.path.insert(0, gemini_engines_path)

try:
    from src.services.gemini_tool_implementations import GeminiToolImplementations
    print("✓ Import successful!")
    tool_impl = GeminiToolImplementations()
    print(f"✓ Created instance: {tool_impl}")
except Exception as e:
    print(f"✗ Import failed: {e}")
finally:
    os.chdir(saved_cwd)

# Method 2: Import with module spec
print("\n=== Method 2: Import with importlib ===")
import importlib.util
import importlib.machinery

spec_path = os.path.join(gemini_engines_path, "src", "services", "gemini_tool_implementations.py")
print(f"Module path: {spec_path}")
print(f"Module exists: {os.path.exists(spec_path)}")

if os.path.exists(spec_path):
    # Add gemini-engines to path
    if gemini_engines_path not in sys.path:
        sys.path.insert(0, gemini_engines_path)
    
    try:
        # Try to import the module
        spec = importlib.util.spec_from_file_location(
            "gemini_tool_implementations",
            spec_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print("✓ Import with importlib successful!")
        print(f"✓ Module: {module}")
    except Exception as e:
        print(f"✗ Importlib failed: {e}")
        import traceback
        traceback.print_exc()

print("\n=== Testing complete ===")