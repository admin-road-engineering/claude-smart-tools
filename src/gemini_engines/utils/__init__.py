"""
Utility modules for Gemini Engines
Import path utilities from the centralized smart tools location
"""
import sys
import os

# Add the smart tools src directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
smart_tools_src = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), "src")
if smart_tools_src not in sys.path:
    sys.path.insert(0, smart_tools_src)

# Import from centralized location to avoid duplication
from utils.path_utils import normalize_paths, normalize_single_path, safe_path_iteration

__all__ = ['normalize_paths', 'normalize_single_path', 'safe_path_iteration']