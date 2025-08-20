"""
Chunking strategy for handling large codebases without timeouts
Based on user feedback about analyze_code timing out on large projects
"""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import asyncio

logger = logging.getLogger(__name__)


class CodebaseChunker:
    """
    Intelligently chunks large codebases for analysis without timeouts
    Addresses the analyze_code 30-second timeout issue
    """
    
    # File size thresholds (Generous for 32GB RAM system)
    MAX_FILES_PER_CHUNK = 50  # Increased from 20 for powerful system
    MAX_CHARS_PER_CHUNK = 200000  # ~200KB per chunk (was 50KB)
    MAX_CHUNK_SIZE_MB = 5  # 5MB max per chunk (was 1MB)
    
    # Log-specific thresholds (logs are different from code)
    MAX_LOG_CHUNK_SIZE_MB = 2  # Smaller chunks for logs (dense content)
    MAX_LOG_LINES_PER_CHUNK = 10000  # ~10K lines per log chunk
    
    # Priority for file types (analyze most important first)
    FILE_PRIORITY = {
        # High priority - core application logic
        ".py": 1,
        ".js": 1,
        ".ts": 1,
        ".java": 1,
        ".go": 1,
        ".rs": 1,
        ".rb": 1,
        
        # Medium priority - configuration and setup
        ".yaml": 2,
        ".yml": 2,
        ".json": 2,
        ".toml": 2,
        ".ini": 2,
        ".env": 2,
        
        # Lower priority - docs and tests
        ".md": 3,
        ".txt": 3,
        ".test.js": 3,
        ".spec.ts": 3,
        "_test.py": 3,
        
        # Lowest priority - generated/vendor
        ".lock": 4,
        ".min.js": 4,
        ".map": 4,
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def should_chunk(self, file_paths: List[str], tool_name: str = None) -> bool:
        """
        Determine if chunking is needed based on codebase size
        
        Returns True if:
        - More than MAX_FILES_PER_CHUNK files
        - Total size exceeds reasonable limits
        - Estimated processing time > 25 seconds
        - Special case: check_quality tool chunks more aggressively
        """
        # check_quality needs more aggressive chunking due to intensive analysis
        if tool_name == "check_quality":
            max_files = 20  # Lower threshold for check_quality
        else:
            max_files = self.MAX_FILES_PER_CHUNK
            
        if len(file_paths) > max_files:
            return True
        
        total_size = 0
        for path_str in file_paths:
            path = Path(path_str)
            if path.is_file() and path.exists():
                total_size += path.stat().st_size
            elif path.is_dir():
                # Estimate directory size (don't walk entire tree)
                for child in path.iterdir():
                    if child.is_file():
                        total_size += child.stat().st_size
                        if total_size > self.MAX_CHUNK_SIZE_MB * 1024 * 1024:
                            return True
        
        return total_size > self.MAX_CHUNK_SIZE_MB * 1024 * 1024
    
    def create_chunks(self, file_paths: List[str], max_chunks: int = 5) -> List[Dict[str, Any]]:
        """
        Create intelligent chunks from file paths
        
        Strategy:
        1. Group by file type/purpose
        2. Prioritize core application code
        3. Keep related files together
        4. Respect size limits
        
        Returns:
            List of chunks, each containing:
            - files: List of file paths
            - description: What this chunk contains
            - priority: Importance level
            - estimated_tokens: Rough token estimate
        """
        # Collect and categorize all files
        categorized_files = self._categorize_files(file_paths)
        
        chunks = []
        
        # Create chunks by priority
        for priority_level in sorted(categorized_files.keys()):
            category_files = categorized_files[priority_level]
            
            if not category_files:
                continue
            
            # Split category into size-appropriate chunks
            current_chunk = {
                "files": [],
                "description": self._get_chunk_description(priority_level),
                "priority": priority_level,
                "size_bytes": 0,
                "file_count": 0
            }
            
            for file_path in category_files:
                file_size = self._get_file_size(file_path)
                
                # Check if adding this file would exceed limits
                if (current_chunk["file_count"] >= self.MAX_FILES_PER_CHUNK or
                    current_chunk["size_bytes"] + file_size > self.MAX_CHUNK_SIZE_MB * 1024 * 1024):
                    
                    # Save current chunk if it has files
                    if current_chunk["files"]:
                        chunks.append(current_chunk)
                    
                    # Start new chunk
                    current_chunk = {
                        "files": [],
                        "description": self._get_chunk_description(priority_level),
                        "priority": priority_level,
                        "size_bytes": 0,
                        "file_count": 0
                    }
                
                # Add file to current chunk
                current_chunk["files"].append(file_path)
                current_chunk["size_bytes"] += file_size
                current_chunk["file_count"] += 1
            
            # Add final chunk for this priority
            if current_chunk["files"]:
                chunks.append(current_chunk)
        
        # Limit total chunks if needed
        if len(chunks) > max_chunks:
            self.logger.info(f"Limiting from {len(chunks)} to {max_chunks} chunks")
            chunks = chunks[:max_chunks]
        
        return chunks
    
    def _categorize_files(self, file_paths: List[str]) -> Dict[int, List[str]]:
        """Categorize files by priority level"""
        categorized = {1: [], 2: [], 3: [], 4: []}
        
        for path_str in file_paths:
            path = Path(path_str)
            
            if path.is_file():
                priority = self._get_file_priority(path)
                categorized[priority].append(path_str)
            elif path.is_dir():
                # Expand directory to files
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        priority = self._get_file_priority(file_path)
                        categorized[priority].append(str(file_path))
        
        return categorized
    
    def _get_file_priority(self, file_path: Path) -> int:
        """Get priority level for a file based on extension and name"""
        name_lower = file_path.name.lower()
        
        # Check specific patterns
        if "_test" in name_lower or ".test." in name_lower or ".spec." in name_lower:
            return 3  # Test files
        
        # Check extension
        for ext, priority in self.FILE_PRIORITY.items():
            if name_lower.endswith(ext):
                return priority
        
        # Default to medium priority
        return 2
    
    def _get_file_size(self, file_path: str) -> int:
        """Get file size in bytes, return 0 if file doesn't exist"""
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                return path.stat().st_size
        except:
            pass
        return 0
    
    def _get_chunk_description(self, priority: int) -> str:
        """Get description for chunk based on priority"""
        descriptions = {
            1: "Core application code (business logic)",
            2: "Configuration and setup files",
            3: "Tests and documentation",
            4: "Generated and vendor files"
        }
        return descriptions.get(priority, "Mixed files")
    
    async def analyze_in_chunks(self, file_paths: List[str], 
                               analysis_func: callable,
                               combine_func: callable = None) -> str:
        """
        Analyze files in chunks and combine results
        
        Args:
            file_paths: Files to analyze
            analysis_func: Async function to analyze each chunk
            combine_func: Function to combine chunk results (optional)
            
        Returns:
            Combined analysis result
        """
        if not self.should_chunk(file_paths):
            # Small enough to analyze directly
            return await analysis_func(file_paths)
        
        self.logger.info(f"Chunking {len(file_paths)} files for analysis")
        chunks = self.create_chunks(file_paths)
        
        # Analyze chunks in order of priority
        chunk_results = []
        for i, chunk in enumerate(chunks, 1):
            self.logger.info(f"Analyzing chunk {i}/{len(chunks)}: {chunk['description']} "
                           f"({chunk['file_count']} files, {chunk['size_bytes'] / 1024:.1f}KB)")
            
            try:
                result = await analysis_func(chunk['files'])
                chunk_results.append({
                    "chunk_id": i,
                    "description": chunk['description'],
                    "result": result
                })
            except asyncio.TimeoutError:
                self.logger.warning(f"Chunk {i} timed out, skipping")
                chunk_results.append({
                    "chunk_id": i,
                    "description": chunk['description'],
                    "result": "Analysis timed out for this chunk"
                })
            except Exception as e:
                self.logger.error(f"Error analyzing chunk {i}: {e}")
                chunk_results.append({
                    "chunk_id": i,
                    "description": chunk['description'],
                    "result": f"Error: {str(e)}"
                })
        
        # Combine results
        if combine_func:
            return combine_func(chunk_results)
        else:
            # Default combination: concatenate with headers
            combined = "# Chunked Analysis Results\n\n"
            for chunk_result in chunk_results:
                combined += f"## Chunk {chunk_result['chunk_id']}: {chunk_result['description']}\n\n"
                combined += chunk_result['result'] + "\n\n"
            return combined
    
    def should_chunk_logs(self, log_paths: List[str]) -> bool:
        """Determine if log files need chunking (more aggressive than code)"""
        for path_str in log_paths:
            path = Path(path_str)
            if path.is_file() and path.exists():
                file_size = path.stat().st_size
                # Chunk logs at 2MB instead of 5MB
                if file_size > self.MAX_LOG_CHUNK_SIZE_MB * 1024 * 1024:
                    return True
        return False
    
    def create_log_chunks(self, log_file_path: str, overlap_lines: int = 100) -> List[Dict[str, Any]]:
        """
        Create overlapping chunks from a single large log file
        
        Args:
            log_file_path: Path to the log file to chunk
            overlap_lines: Number of lines to overlap between chunks
            
        Returns:
            List of log chunks with content and metadata
        """
        path = Path(log_file_path)
        if not path.exists() or not path.is_file():
            return []
        
        chunks = []
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            if len(lines) <= self.MAX_LOG_LINES_PER_CHUNK:
                # Small enough, no chunking needed
                return [{
                    "content": "".join(lines),
                    "start_line": 1,
                    "end_line": len(lines),
                    "file_path": log_file_path,
                    "chunk_id": 1,
                    "total_chunks": 1
                }]
            
            total_lines = len(lines)
            chunk_size = self.MAX_LOG_LINES_PER_CHUNK
            chunk_id = 1
            start_line = 0
            
            while start_line < total_lines:
                end_line = min(start_line + chunk_size, total_lines)
                
                # Extract chunk content
                chunk_lines = lines[start_line:end_line]
                chunk_content = "".join(chunk_lines)
                
                # Add metadata about time range if log has timestamps
                start_timestamp = self._extract_timestamp(chunk_lines[0]) if chunk_lines else None
                end_timestamp = self._extract_timestamp(chunk_lines[-1]) if chunk_lines else None
                
                chunks.append({
                    "content": chunk_content,
                    "start_line": start_line + 1,  # 1-indexed
                    "end_line": end_line,
                    "file_path": log_file_path,
                    "chunk_id": chunk_id,
                    "total_chunks": 0,  # Will be updated later
                    "start_timestamp": start_timestamp,
                    "end_timestamp": end_timestamp,
                    "size_kb": len(chunk_content) / 1024
                })
                
                # Move start position, accounting for overlap
                start_line = end_line - overlap_lines if end_line < total_lines else end_line
                chunk_id += 1
            
            # Update total_chunks for all chunks
            total_chunks = len(chunks)
            for chunk in chunks:
                chunk["total_chunks"] = total_chunks
            
            self.logger.info(f"Created {total_chunks} log chunks from {log_file_path} "
                           f"({total_lines:,} lines, {path.stat().st_size / 1024 / 1024:.1f}MB)")
            
            return chunks
            
        except Exception as e:
            self.logger.error(f"Failed to chunk log file {log_file_path}: {e}")
            return []
    
    def _extract_timestamp(self, line: str) -> Optional[str]:
        """Try to extract timestamp from log line"""
        import re
        # Common log timestamp patterns
        patterns = [
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',  # YYYY-MM-DD HH:MM:SS
            r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})',   # MM/DD/YYYY HH:MM:SS
            r'(\w{3} \d{1,2} \d{2}:\d{2}:\d{2})',        # MMM DD HH:MM:SS
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',    # ISO format
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(1)
        
        return None
    
    async def analyze_log_chunks(self, log_file_path: str, analysis_func: callable) -> str:
        """
        Analyze a large log file in chunks and combine results
        
        Args:
            log_file_path: Path to log file
            analysis_func: Async function to analyze each chunk's content
            
        Returns:
            Combined analysis with chunk summaries
        """
        if not self.should_chunk_logs([log_file_path]):
            # File is small enough to analyze directly
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return await analysis_func(content)
        
        # Create chunks
        chunks = self.create_log_chunks(log_file_path)
        if not chunks:
            return f"Failed to process log file: {log_file_path}"
        
        self.logger.info(f"Analyzing {len(chunks)} log chunks")
        
        # Analyze each chunk
        chunk_results = []
        for chunk in chunks:
            try:
                self.logger.info(f"Analyzing chunk {chunk['chunk_id']}/{chunk['total_chunks']} "
                               f"(lines {chunk['start_line']}-{chunk['end_line']}, {chunk['size_kb']:.1f}KB)")
                
                result = await analysis_func(chunk['content'])
                chunk_results.append({
                    "chunk_id": chunk['chunk_id'],
                    "line_range": f"{chunk['start_line']}-{chunk['end_line']}",
                    "time_range": f"{chunk.get('start_timestamp', 'N/A')} to {chunk.get('end_timestamp', 'N/A')}",
                    "result": result
                })
            except Exception as e:
                self.logger.error(f"Error analyzing log chunk {chunk['chunk_id']}: {e}")
                chunk_results.append({
                    "chunk_id": chunk['chunk_id'],
                    "line_range": f"{chunk['start_line']}-{chunk['end_line']}",
                    "time_range": "Error",
                    "result": f"Analysis failed: {str(e)}"
                })
        
        # Combine results with log-specific formatting
        combined = f"# Log Analysis Results: {Path(log_file_path).name}\n\n"
        combined += f"**File**: {log_file_path}\n"
        combined += f"**Chunks analyzed**: {len(chunk_results)}\n\n"
        
        for chunk_result in chunk_results:
            combined += f"## Chunk {chunk_result['chunk_id']} (Lines {chunk_result['line_range']})\n"
            combined += f"**Time range**: {chunk_result['time_range']}\n\n"
            combined += chunk_result['result'] + "\n\n"
        
        return combined