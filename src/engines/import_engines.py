#!/usr/bin/env python
"""
Direct importer for Gemini engines - run from the gemini-engines directory
"""
import sys
import os

# Get the gemini-engines path
current_file = os.path.abspath(__file__)
smart_tools_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
gemini_engines_path = os.path.join(smart_tools_root, "gemini-engines")

# Change to gemini-engines directory and set up path
os.chdir(gemini_engines_path)
sys.path.insert(0, gemini_engines_path)

# Now import the implementations
from src.services.gemini_tool_implementations import GeminiToolImplementations
from src.clients.gemini_client import GeminiClient
from src.config import config

# Create instances
tool_implementations = GeminiToolImplementations()
gemini_client = GeminiClient()

# Export these for use
__all__ = ['tool_implementations', 'gemini_client', 'config']