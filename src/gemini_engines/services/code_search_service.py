"""
Simple, robust code search service that actually finds text in files.
No overengineering - just basic text search that works.
"""
import os
import re
import glob
import logging
import time
from typing import List, Dict, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SimpleFileCache:
    """Simple LRU cache for file contents with TTL"""
    
    def __init__(self, ttl_seconds: int = 300, max_size: int = 50):
        self.cache = {}  # {filepath: (content, timestamp)}
        self.ttl = ttl_seconds
        self.max_size = max_size
        
    def get(self, filepath: str) -> Optional[str]:
        """Get cached content if still valid"""
        if filepath in self.cache:
            content, timestamp = self.cache[filepath]
            if time.time() - timestamp < self.ttl:
                logger.debug(f"Cache hit for {filepath}")
                return content
            else:
                # Expired
                del self.cache[filepath]
        return None
    
    def put(self, filepath: str, content: str):
        """Store content in cache"""
        # Simple LRU: if full, remove oldest
        if len(self.cache) >= self.max_size:
            oldest = min(self.cache.items(), key=lambda x: x[1][1])
            del self.cache[oldest[0]]
        
        self.cache[filepath] = (content, time.time())
        logger.debug(f"Cached {filepath}")
    
    def clear(self):
        """Clear all cached content"""
        self.cache.clear()


class CodeSearchService:
    """Service for searching code in files with multiple strategies"""
    
    def __init__(self):
        self.max_results_per_file = 5
        self.context_lines = 3
        self.file_cache = SimpleFileCache(ttl_seconds=300, max_size=50)
        
    def search(self, 
               query: str, 
               paths: List[str] = None, 
               search_type: str = "text",
               case_sensitive: bool = False) -> Dict:
        """
        Search for query in files with various strategies.
        
        Args:
            query: Search query (text or regex pattern)
            paths: List of file or directory paths to search (auto-detects if None)
            search_type: "text" for literal, "regex" for pattern, "word" for word boundaries
            case_sensitive: Whether search should be case-sensitive
            
        Returns:
            Dictionary with results, debug info, and any errors
        """
        # Smart defaults: auto-detect common directories if no paths provided
        if paths is None or len(paths) == 0:
            paths = self._get_default_paths()
            if not paths:
                return {
                    "results": [],
                    "files_checked": 0,
                    "message": "No paths provided and no common directories found (src/, lib/, app/, tests/)",
                    "debug": {"cwd": os.getcwd()}
                }
        
        results = []
        files_checked = 0
        files_with_errors = []
        sample_content = ""
        
        # Collect all files to search
        all_files = self._collect_files(paths)
        
        if not all_files:
            return {
                "results": [],
                "files_checked": 0,
                "message": f"No files found in paths: {paths}",
                "debug": {"resolved_paths": [os.path.abspath(p) for p in paths]}
            }
        
        # Prepare search pattern
        search_pattern = self._prepare_pattern(query, search_type, case_sensitive)
        
        # Search each file
        for file_path in all_files:
            files_checked += 1
            
            try:
                file_results = self._search_file(
                    file_path, 
                    query,
                    search_pattern,
                    search_type,
                    case_sensitive
                )
                
                if file_results:
                    results.append({
                        "file": file_path,
                        "matches": file_results
                    })
                    
                # Capture sample content from first file for debugging
                if files_checked == 1 and not sample_content:
                    # Use cached content if available
                    cached = self.file_cache.get(file_path)
                    if cached:
                        sample_content = cached[:500]
                    else:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            sample_content = f.read(500)
                        
            except Exception as e:
                files_with_errors.append({"file": file_path, "error": str(e)})
                logger.debug(f"Error searching {file_path}: {e}")
        
        # Build response with helpful debug info
        response = {
            "results": results,
            "files_checked": files_checked,
            "files_with_matches": len(results),
            "total_matches": sum(len(r["matches"]) for r in results)
        }
        
        if not results:
            response["message"] = self._build_no_results_message(
                query, files_checked, sample_content, search_type
            )
            response["debug"] = {
                "sample_file_content": sample_content[:200] if sample_content else "No content read",
                "search_type": search_type,
                "case_sensitive": case_sensitive,
                "files_with_errors": files_with_errors[:3]  # First 3 errors
            }
        
        return response
    
    def _get_default_paths(self) -> List[str]:
        """Auto-detect common project directories"""
        common_dirs = ['src', 'lib', 'app', 'apps', 'source', 'tests', 'test', 
                      'services', 'components', 'modules', 'packages']
        found_paths = []
        
        for dir_name in common_dirs:
            if os.path.isdir(dir_name):
                found_paths.append(dir_name)
        
        # Also check one level up
        parent_dir = os.path.dirname(os.getcwd())
        for dir_name in ['src', 'lib', 'app']:
            check_path = os.path.join(parent_dir, dir_name)
            if os.path.isdir(check_path):
                found_paths.append(check_path)
        
        return found_paths[:5]  # Limit to 5 directories to avoid huge searches
    
    def _collect_files(self, paths: List[str]) -> List[str]:
        """Collect all files from the given paths"""
        all_files = []
        
        for path in paths:
            # Convert to absolute path
            abs_path = os.path.abspath(path)
            
            if os.path.isfile(abs_path):
                all_files.append(abs_path)
            elif os.path.isdir(abs_path):
                # Find code files in directory
                patterns = ['*.py', '*.js', '*.ts', '*.jsx', '*.tsx', 
                           '*.java', '*.go', '*.rs', '*.cpp', '*.c', '*.h']
                
                for pattern in patterns:
                    files = glob.glob(os.path.join(abs_path, '**', pattern), recursive=True)
                    all_files.extend(files[:20])  # Limit per pattern to avoid huge searches
            else:
                # Try to find similar files if path doesn't exist
                logger.debug(f"Path not found: {abs_path}")
                
                # Check if it's a relative path that needs resolution
                if not os.path.isabs(path):
                    # Try common directories
                    for prefix in ['src/', 'lib/', 'app/', 'tests/']:
                        test_path = os.path.join(prefix, path)
                        if os.path.exists(test_path):
                            if os.path.isfile(test_path):
                                all_files.append(test_path)
                            break
        
        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for f in all_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)
        
        return unique_files[:100]  # Cap at 100 files total
    
    def _prepare_pattern(self, query: str, search_type: str, case_sensitive: bool):
        """Prepare the search pattern based on type"""
        if search_type == "regex":
            # User provided regex pattern
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                return re.compile(query, flags)
            except re.error as e:
                # Invalid regex, fall back to literal search
                logger.warning(f"Invalid regex pattern '{query}': {e}")
                search_type = "text"
        
        if search_type == "word":
            # Word boundary search
            escaped = re.escape(query)
            pattern = r'\b' + escaped + r'\b'
            flags = 0 if case_sensitive else re.IGNORECASE
            return re.compile(pattern, flags)
        
        # Default text search - escape special chars
        escaped = re.escape(query)
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.compile(escaped, flags)
    
    def _search_file(self, file_path: str, query: str, pattern, 
                     search_type: str, case_sensitive: bool) -> List[Dict]:
        """Search a single file and return matches with context"""
        matches = []
        
        # Try to get from cache first
        content = self.file_cache.get(file_path)
        if content is None:
            # Read from disk and cache
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                self.file_cache.put(file_path, content)
        
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            # Check if line matches
            if pattern.search(line):
                # Get context
                start = max(0, i - self.context_lines)
                end = min(len(lines), i + self.context_lines + 1)
                
                context_lines = []
                for j in range(start, end):
                    prefix = ">>> " if j == i else "    "
                    context_lines.append(f"{j+1:4d}{prefix}{lines[j].rstrip()}")
                
                matches.append({
                    "line_number": i + 1,
                    "line": line.rstrip(),
                    "context": "\n".join(context_lines)
                })
                
                # Limit matches per file
                if len(matches) >= self.max_results_per_file:
                    break
        
        return matches
    
    def _build_no_results_message(self, query: str, files_checked: int, 
                                   sample_content: str, search_type: str) -> str:
        """Build helpful message when no results found"""
        msg = f"🔍 No results found for '{query}'\n\n"
        msg += f"📊 Search details:\n"
        msg += f"  • Files checked: {files_checked}\n"
        msg += f"  • Search type: {search_type}\n"
        
        if files_checked == 0:
            msg += "\n⚠️ No files were found to search. Check your paths.\n"
        elif sample_content:
            # Show a bit of content to prove we're reading files
            msg += f"\n📄 Sample from first file (proving we can read files):\n"
            msg += f"  {sample_content[:100]}...\n"
            
            # Helpful suggestions
            msg += f"\n💡 Suggestions:\n"
            msg += f"  • Check if the search term exists in the files\n"
            msg += f"  • Try a broader search term\n"
            msg += f"  • Ensure you're searching the right directory\n"
            
            # Check if query might be in sample
            if query.lower() in sample_content.lower():
                msg += f"\n⚠️ Note: The query appears in the sample but wasn't matched. "
                msg += f"This might be a bug in the search logic.\n"
        
        return msg