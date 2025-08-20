"""
Smart Path Resolution Service
Handles file path resolution when user working directory differs from MCP server directory
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)


class PathResolver:
    """
    Intelligent path resolution for Smart Tools MCP server
    
    Handles the case where users work in VENV/project directories
    but MCP server runs from Smart Tools directory
    """
    
    def __init__(self):
        self.server_root = Path(__file__).parent.parent.parent  # claude-smart-tools directory
        self.common_project_indicators = {
            # Python projects
            "pyproject.toml", "setup.py", "requirements.txt", "setup.cfg", "Pipfile",
            # Node.js projects  
            "package.json", "yarn.lock", "npm-lock.json",
            # General projects
            ".git", ".gitignore", "README.md", "README.rst",
            # Configuration files
            ".env", "config.yml", "config.yaml", "docker-compose.yml"
        }
        
    def resolve_file_paths(self, file_paths: Union[str, List[str]]) -> Tuple[List[Path], List[str]]:
        """
        Resolve file paths using intelligent context detection
        
        Args:
            file_paths: Single path or list of paths (relative or absolute)
            
        Returns:
            Tuple of (resolved_paths, resolution_messages)
        """
        if isinstance(file_paths, str):
            file_paths = [file_paths]
            
        resolved_paths = []
        messages = []
        
        for file_path in file_paths:
            resolved_path, message = self._resolve_single_path(file_path)
            if resolved_path:
                resolved_paths.append(resolved_path)
            if message:
                messages.append(message)
                
        return resolved_paths, messages
    
    def _resolve_single_path(self, file_path: str) -> Tuple[Optional[Path], Optional[str]]:
        """Resolve a single file path with context detection"""
        
        path_obj = Path(file_path)
        
        # 1. Absolute path - use directly
        if path_obj.is_absolute():
            if path_obj.exists():
                logger.debug(f"Resolved absolute path: {path_obj}")
                return path_obj, None
            else:
                return None, f"❌ Absolute path not found: {file_path}"
        
        # 2. Relative path - try intelligent resolution
        return self._resolve_relative_path(file_path)
    
    def _resolve_relative_path(self, file_path: str) -> Tuple[Optional[Path], Optional[str]]:
        """Resolve relative path using context detection"""
        
        # Strategy 1: Try common project root locations
        candidate_roots = self._find_potential_project_roots()
        
        for root in candidate_roots:
            candidate_path = root / file_path
            if candidate_path.exists():
                logger.info(f"✅ Resolved '{file_path}' to: {candidate_path}")
                return candidate_path, f"📂 Found in project: {root.name}"
        
        # Strategy 2: Search upward from likely locations
        search_paths = self._get_search_paths()
        for search_base in search_paths:
            found_path = self._search_upward_for_file(search_base, file_path)
            if found_path:
                logger.info(f"✅ Found '{file_path}' via upward search: {found_path}")
                return found_path, f"🔍 Found via search from: {search_base.name}"
        
        # Strategy 3: Fallback to server directory (current behavior)
        fallback_path = self.server_root / file_path
        if fallback_path.exists():
            logger.warning(f"⚠️ Using fallback resolution for '{file_path}': {fallback_path}")
            return fallback_path, f"⚠️ Using Smart Tools directory (fallback)"
        
        # All strategies failed
        suggestions = self._generate_suggestions(file_path)
        error_msg = (
            f"❌ Cannot find '{file_path}'. Tried:\n"
            f"  • {len(candidate_roots)} potential project roots\n" 
            f"  • {len(search_paths)} search locations\n"
            f"  • Smart Tools directory (fallback)\n\n"
            f"💡 Suggestions:\n{chr(10).join(suggestions)}"
        )
        
        return None, error_msg
    
    def _find_potential_project_roots(self) -> List[Path]:
        """Find directories that look like project roots"""
        
        candidate_roots = []
        
        # Look in common locations relative to current working directory
        cwd = Path.cwd()
        search_bases = [
            cwd,  # Current directory
            cwd.parent,  # Parent directory
            cwd.parent.parent,  # Grandparent directory
        ]
        
        # Add user's home directory patterns
        home = Path.home()
        if home.exists():
            # Common project locations
            common_project_dirs = [
                home / "Projects",
                home / "Development", 
                home / "Code",
                home / "src",
                home / "workspace"
            ]
            search_bases.extend([d for d in common_project_dirs if d.exists()])
        
        # Find directories with project indicators
        for base in search_bases:
            if not base.exists() or not base.is_dir():
                continue
                
            # Check if base itself is a project
            if self._looks_like_project_root(base):
                candidate_roots.append(base)
            
            # Check subdirectories
            try:
                for subdir in base.iterdir():
                    if subdir.is_dir() and self._looks_like_project_root(subdir):
                        candidate_roots.append(subdir)
            except PermissionError:
                continue
        
        # Remove duplicates and sort by likelihood
        unique_roots = list(dict.fromkeys(candidate_roots))  # Preserve order, remove duplicates
        return self._sort_roots_by_likelihood(unique_roots)
    
    def _looks_like_project_root(self, directory: Path) -> bool:
        """Check if directory looks like a project root"""
        if not directory.is_dir():
            return False
            
        try:
            files_in_dir = set(f.name for f in directory.iterdir() if f.is_file())
            dirs_in_dir = set(d.name for d in directory.iterdir() if d.is_dir())
            all_items = files_in_dir | dirs_in_dir
            
            # Count project indicators
            indicators_found = len(self.common_project_indicators & all_items)
            
            # Additional scoring
            score = indicators_found
            if "src" in dirs_in_dir or "lib" in dirs_in_dir:
                score += 1
            if "tests" in dirs_in_dir or "test" in dirs_in_dir:
                score += 1  
            if ".venv" in dirs_in_dir or "venv" in dirs_in_dir:
                score += 2  # Strong indicator
                
            return score >= 2  # Needs at least 2 indicators
            
        except PermissionError:
            return False
    
    def _sort_roots_by_likelihood(self, roots: List[Path]) -> List[Path]:
        """Sort project roots by likelihood of being the target"""
        
        def score_root(root: Path) -> int:
            score = 0
            try:
                items = set(f.name for f in root.iterdir())
                
                # High value indicators
                if ".git" in items:
                    score += 5
                if "pyproject.toml" in items or "setup.py" in items:
                    score += 4
                if "requirements.txt" in items:
                    score += 3
                if "package.json" in items:
                    score += 3
                
                # Project structure indicators  
                subdirs = set(d.name for d in root.iterdir() if d.is_dir())
                if "src" in subdirs:
                    score += 2
                if any(venv in subdirs for venv in [".venv", "venv", "env"]):
                    score += 3
                    
            except PermissionError:
                pass
                
            return score
            
        return sorted(roots, key=score_root, reverse=True)
    
    def _get_search_paths(self) -> List[Path]:
        """Get base paths to search upward from"""
        paths = [Path.cwd()]
        
        # Add paths from sys.path that look like project directories
        for path_str in sys.path:
            path = Path(path_str)
            if path.exists() and path.is_dir() and "site-packages" not in str(path):
                paths.append(path)
                
        return list(dict.fromkeys(paths))  # Remove duplicates
    
    def _search_upward_for_file(self, start_path: Path, target_file: str) -> Optional[Path]:
        """Search upward from start_path for target_file"""
        current = start_path.resolve()
        
        # Limit search depth to prevent infinite loops
        max_depth = 10
        depth = 0
        
        while depth < max_depth and current.parent != current:  # Not at root
            candidate = current / target_file
            if candidate.exists():
                return candidate
                
            current = current.parent
            depth += 1
            
        return None
    
    def _generate_suggestions(self, file_path: str) -> List[str]:
        """Generate helpful suggestions when file not found"""
        suggestions = [
            f"  • Use absolute path: {Path.cwd() / file_path}",
            f"  • Check current directory: {Path.cwd()}",
            "  • Ensure you're in the correct project directory",
        ]
        
        # Look for similar files
        file_name = Path(file_path).name
        cwd = Path.cwd()
        
        if cwd.exists():
            similar_files = []
            try:
                for root, dirs, files in os.walk(cwd):
                    for f in files:
                        if f.lower() == file_name.lower() or file_name.lower() in f.lower():
                            rel_path = os.path.relpath(os.path.join(root, f), cwd)
                            similar_files.append(rel_path)
                    
                    # Limit search depth
                    if len(root.split(os.sep)) - len(str(cwd).split(os.sep)) > 3:
                        dirs.clear()
                        
            except (PermissionError, OSError):
                pass
                
            if similar_files:
                suggestions.append(f"  • Similar files found: {', '.join(similar_files[:3])}")
                
        return suggestions


# Global instance
_path_resolver = None

def get_path_resolver() -> PathResolver:
    """Get the global PathResolver instance"""
    global _path_resolver
    if _path_resolver is None:
        _path_resolver = PathResolver()
    return _path_resolver