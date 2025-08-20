"""
FileIntegrityValidator - Business logic for file freshness and integrity validation
Enforces file state business rules and detects stale analysis references
"""
import logging
import os
import re
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Set, List, Optional
from pathlib import Path
from enum import Enum, auto

from .file_content_provider import FileContentProvider
from .structured_logger import get_logger, LogContext, EventType
from ..security import get_path_validator

# Use pathspec for .gitignore support
try:
    import pathspec
    PATHSPEC_AVAILABLE = True
except ImportError:
    PATHSPEC_AVAILABLE = False
    logging.warning("pathspec not available - file filtering will be basic")


class StaleReferenceAction(Enum):
    """Structured recommendation for stale reference handling"""
    RETRY_ANALYSIS_WITH_UPDATED_FILES = auto()
    WARN_USER_OF_POTENTIAL_HALLUCINATION = auto()
    PROCEED_WITH_CAUTION = auto()
    ANALYSIS_APPEARS_CURRENT = auto()


@dataclass
class ValidationReport:
    """Result of pre-analysis file path validation"""
    timestamp: datetime
    requested_paths: List[str]
    verified_files: List[str]
    missing_paths: List[str]
    filtered_files: List[str]  # Files ignored due to .gitignore etc
    total_size_bytes: int
    has_critical_issues: bool
    validation_summary: str
    
    def format_current_state_report(self) -> str:
        """Generate human-readable current state report"""
        status = "⚠️ CRITICAL ISSUES" if self.has_critical_issues else "✅ VALIDATION PASSED"
        
        return f"""
🔍 FILE STATE VALIDATION REPORT
═══════════════════════════════════
Timestamp: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Status: {status}

📊 Analysis Target:
  • Requested paths: {len(self.requested_paths)}
  • Verified files: {len(self.verified_files)}
  • Missing paths: {len(self.missing_paths)}
  • Filtered files: {len(self.filtered_files)}
  • Total size: {self.total_size_bytes:,} bytes

📁 Sample Files (first 5):
{chr(10).join(f'  ✅ {f}' for f in self.verified_files[:5])}

{'⚠️ Missing Paths:' + chr(10) + chr(10).join(f'  ❌ {p}' for p in self.missing_paths) if self.missing_paths else ''}

⚠️ CRITICAL: Analysis will ONLY process the {len(self.verified_files)} verified files above.
Any references to other files in results indicate stale/cached data.
═══════════════════════════════════
"""


@dataclass 
class StaleReferenceReport:
    """Result of post-analysis stale reference detection"""
    analysis_timestamp: datetime
    stale_files_detected: Set[str]
    known_valid_files: Set[str]
    confidence_score: float  # 0.0 to 1.0 - ratio of stale refs to total refs
    is_stale: bool
    actionable_recommendation: StaleReferenceAction
    
    def format_stale_detection_report(self) -> str:
        """Format stale detection results"""
        if not self.is_stale:
            return "✅ No stale file references detected"
        
        action_messages = {
            StaleReferenceAction.RETRY_ANALYSIS_WITH_UPDATED_FILES: "Re-run analysis on current codebase",
            StaleReferenceAction.WARN_USER_OF_POTENTIAL_HALLUCINATION: "Results may contain AI hallucinations",
            StaleReferenceAction.PROCEED_WITH_CAUTION: "Review results carefully for accuracy",
            StaleReferenceAction.ANALYSIS_APPEARS_CURRENT: "No action needed"
        }
        
        return f"""
🚨 STALE ANALYSIS DETECTED
═══════════════════════════
Detection Time: {self.analysis_timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Confidence: {self.confidence_score:.1%}

❌ Files mentioned that don't exist:
{chr(10).join(f'  • {f}' for f in sorted(self.stale_files_detected))}

✅ Valid files at analysis time: {len(self.known_valid_files)}

💡 Recommendation: {action_messages.get(self.actionable_recommendation, 'Unknown action')}
═══════════════════════════
"""


class FileIntegrityValidator:
    """
    Business logic service for file freshness and integrity validation
    
    Responsibilities:
    - Enforce file state business rules
    - Create validation reports for pre-analysis checks
    - Detect stale references in analysis outputs
    - File filtering (.gitignore, code file detection)
    """
    
    def __init__(self, content_provider: FileContentProvider, enable_filtering: bool = True):
        self.logger = logging.getLogger(__name__)
        self.structured_logger = get_logger(f"{__name__}.FileIntegrityValidator")
        self.content_provider = content_provider
        self.enable_filtering = enable_filtering
        self._gitignore_cache = {}  # Cache compiled gitignore patterns
        
        # File extension patterns for code files
        self.code_extensions = {
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.cpp', '.c', '.h', 
            '.hpp', '.cs', '.rb', '.php', '.swift', '.kt', '.scala', '.clj', '.cljs',
            '.sh', '.bash', '.zsh', '.ps1', '.sql', '.yaml', '.yml', '.json', '.toml',
            '.ini', '.conf', '.cfg', '.xml', '.html', '.css', '.scss', '.less', '.md',
            '.txt', '.log', '.proto', '.graphql', '.dockerfile'
        }
    
    async def create_validation_report(self, paths: List[str]) -> ValidationReport:
        """
        Create comprehensive pre-analysis validation report
        
        Args:
            paths: List of file paths or directories to validate
            
        Returns:
            ValidationReport with current file state and validation results
        """
        start_time = time.time()
        
        context = LogContext(file_paths=paths)
        
        self.structured_logger.debug(
            f"Starting validation for {len(paths)} paths",
            EventType.FILE_VALIDATION,
            context,
            {"requested_path_count": len(paths)}
        )
        
        # Discover current files from paths
        discovered_files = await self._discover_files_from_paths(paths)
        
        self.structured_logger.debug(
            f"File discovery completed: {len(discovered_files)} files found",
            EventType.FILE_VALIDATION,
            context,
            {"discovered_file_count": len(discovered_files)}
        )
        
        # Filter files (gitignore, etc.)
        verified_files, filtered_files = await self._filter_files(discovered_files, paths)
        
        # Validate file existence and get stats
        final_verified_files = []
        missing_paths = []
        total_size = 0
        
        for file_path in verified_files:
            stats = await self.content_provider.get_file_stats(file_path)
            if stats:
                final_verified_files.append(file_path)
                total_size += stats['size']
            else:
                missing_paths.append(file_path)
        
        # Determine if there are critical issues
        has_critical_issues = len(final_verified_files) == 0
        
        validation_summary = f"Validated {len(final_verified_files)} files, filtered {len(filtered_files)}, missing {len(missing_paths)}"
        
        report = ValidationReport(
            timestamp=datetime.now(),
            requested_paths=paths,
            verified_files=final_verified_files,
            missing_paths=missing_paths,
            filtered_files=filtered_files,
            total_size_bytes=total_size,
            has_critical_issues=has_critical_issues,
            validation_summary=validation_summary
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Log validation completion with structured logging
        self.structured_logger.log_file_validation(
            session_id=context.session_id or "unknown",
            validated_files=len(final_verified_files),
            missing_files=len(missing_paths),
            filtered_files=len(filtered_files),
            validation_time_ms=duration_ms,
            has_critical_issues=has_critical_issues
        )
        
        return report
    
    async def detect_stale_references(self, analysis_output: str, known_valid_files: Set[str]) -> StaleReferenceReport:
        """
        Detect stale file references in analysis output
        
        Args:
            analysis_output: The AI-generated analysis text
            known_valid_files: Set of file paths that were verified at analysis start
            
        Returns:
            StaleReferenceReport indicating whether stale references were found
        """
        start_time = time.time()
        
        self.structured_logger.debug(
            "Starting stale reference detection",
            EventType.STALE_ANALYSIS,
            details={
                "analysis_size_chars": len(analysis_output),
                "known_valid_files_count": len(known_valid_files)
            }
        )
        
        # Extract file path references from analysis output
        mentioned_files = self._extract_file_references(analysis_output)
        
        # Find files mentioned that weren't in our verified set
        stale_files = mentioned_files - known_valid_files
        
        # Calculate confidence score based on stale reference ratio
        total_mentions = len(mentioned_files)
        stale_count = len(stale_files)
        
        if total_mentions == 0:
            confidence_score = 0.0
        else:
            confidence_score = min(stale_count / total_mentions, 1.0)
        
        # Determine if this is actually problematic (threshold for significance)
        is_stale = len(stale_files) > 0 and confidence_score > 0.1
        
        # Determine actionable recommendation based on confidence
        if not is_stale:
            recommendation = StaleReferenceAction.ANALYSIS_APPEARS_CURRENT
        elif confidence_score < 0.3:
            recommendation = StaleReferenceAction.PROCEED_WITH_CAUTION
        elif confidence_score < 0.7:
            recommendation = StaleReferenceAction.WARN_USER_OF_POTENTIAL_HALLUCINATION
        else:
            recommendation = StaleReferenceAction.RETRY_ANALYSIS_WITH_UPDATED_FILES
        
        duration_ms = (time.time() - start_time) * 1000
        
        if is_stale:
            # Use specialized structured logging for stale detection
            self.structured_logger.log_stale_analysis(
                session_id="unknown",  # Will be provided by caller in real usage
                tool_name="unknown",   # Will be provided by caller in real usage
                stale_files=list(stale_files),
                confidence_score=confidence_score,
                action_taken=recommendation.name
            )
        else:
            self.structured_logger.debug(
                "No significant stale references detected",
                EventType.STALE_ANALYSIS,
                details={
                    "mentioned_files": len(mentioned_files),
                    "confidence_score": confidence_score,
                    "detection_time_ms": duration_ms
                }
            )
        
        return StaleReferenceReport(
            analysis_timestamp=datetime.now(),
            stale_files_detected=stale_files,
            known_valid_files=known_valid_files,
            confidence_score=confidence_score,
            is_stale=is_stale,
            actionable_recommendation=recommendation
        )
    
    async def _discover_files_from_paths(self, paths: List[str]) -> List[str]:
        """Discover all files from given paths (files and directories)"""
        discovered = []
        validator = get_path_validator()
        
        for path in paths:
            try:
                # SECURITY: Validate path before processing
                validated_path = validator.validate_path(path, "discover")
                path_str = str(validated_path)
                
                if os.path.isfile(path_str):
                    discovered.append(path_str)
                elif os.path.isdir(path_str):
                    dir_files = await self._discover_files_in_directory(path_str)
                    discovered.extend(dir_files)
                else:
                    self.logger.warning(f"Path does not exist: {path_str}")
            except Exception as e:
                self.logger.error(f"Error processing path {path}: {e}")
        
        return discovered
    
    async def _discover_files_in_directory(self, directory: str) -> List[str]:
        """Recursively discover code files in directory"""
        files = []
        validator = get_path_validator()
        
        try:
            # Use pathlib for directory traversal (sync is fine for discovery)
            path_obj = Path(directory)
            for file_path in path_obj.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in self.code_extensions:
                    # SECURITY: Validate each discovered file path
                    try:
                        validated_path = validator.validate_path(str(file_path), "discover")
                        files.append(str(validated_path))
                    except:
                        # Skip files outside project boundaries
                        pass
        except Exception as e:
            self.logger.error(f"Error discovering files in {directory}: {e}")
        
        return files
    
    async def _filter_files(self, files: List[str], original_paths: List[str]) -> tuple[List[str], List[str]]:
        """Filter files based on .gitignore and other rules"""
        if not self.enable_filtering:
            return files, []
        
        verified_files = []
        filtered_files = []
        
        # Load gitignore patterns
        gitignore_spec = await self._load_gitignore_patterns(original_paths)
        
        for file_path in files:
            if self._should_include_file(file_path, gitignore_spec):
                verified_files.append(file_path)
            else:
                filtered_files.append(file_path)
        
        return verified_files, filtered_files
    
    async def _load_gitignore_patterns(self, paths: List[str]) -> Optional[object]:
        """Load .gitignore patterns for file filtering"""
        if not PATHSPEC_AVAILABLE:
            return None
        
        # Find .gitignore files in the paths
        gitignore_files = []
        for path in paths:
            if os.path.isdir(path):
                gitignore_path = os.path.join(path, '.gitignore')
                if os.path.exists(gitignore_path):
                    gitignore_files.append(gitignore_path)
            else:
                # Look for .gitignore in parent directory
                parent_dir = os.path.dirname(path)
                gitignore_path = os.path.join(parent_dir, '.gitignore')
                if os.path.exists(gitignore_path):
                    gitignore_files.append(gitignore_path)
        
        if not gitignore_files:
            return None
        
        # Check cache first
        cache_key = tuple(sorted(set(gitignore_files)))
        if cache_key in self._gitignore_cache:
            return self._gitignore_cache[cache_key]
        
        # Read and compile gitignore patterns
        try:
            patterns = []
            for gitignore_file in set(gitignore_files):  # Remove duplicates
                try:
                    content = await self.content_provider.get_content(gitignore_file)
                    patterns.extend(line.strip() for line in content.splitlines() 
                                  if line.strip() and not line.startswith('#'))
                except Exception as e:
                    self.logger.debug(f"Could not read .gitignore {gitignore_file}: {e}")
            
            if patterns:
                spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)
                self._gitignore_cache[cache_key] = spec
                return spec
        except Exception as e:
            self.logger.warning(f"Error loading gitignore patterns: {e}")
        
        return None
    
    def _should_include_file(self, file_path: str, gitignore_spec) -> bool:
        """Determine if file should be included based on filtering rules"""
        # Always exclude certain patterns
        exclude_patterns = [
            '__pycache__', '.git', '.pytest_cache', 'node_modules', 
            '.venv', 'venv', '.env', 'dist', 'build', 'target',
            '.mypy_cache', '.tox', 'coverage.xml'
        ]
        
        for pattern in exclude_patterns:
            if pattern in file_path:
                return False
        
        # Apply gitignore if available
        if gitignore_spec:
            try:
                # Convert absolute path to relative for gitignore matching
                # Simple heuristic: remove common prefixes to make path relative
                relative_path = file_path
                for prefix in ['src/', 'lib/', 'app/', './']:
                    if file_path.startswith(prefix):
                        relative_path = file_path[len(prefix):]
                        break
                
                # Also try basename for simple matching
                if gitignore_spec.match_file(relative_path) or gitignore_spec.match_file(os.path.basename(file_path)):
                    return False
            except Exception as e:
                self.logger.debug(f"Gitignore pattern matching error for {file_path}: {e}")
        
        return True
    
    def _extract_file_references(self, text: str) -> Set[str]:
        """Extract file path references from analysis text"""
        file_patterns = [
            # Python files
            r'\b[\w/.-]+\.py\b',
            # JavaScript/TypeScript files  
            r'\b[\w/.-]+\.(?:js|ts|tsx|jsx)\b',
            # Other common code files
            r'\b[\w/.-]+\.(?:java|go|rs|cpp|c|h|hpp|cs|rb|php)\b',
            # Config files
            r'\b[\w/.-]+\.(?:json|yaml|yml|toml|ini|conf|cfg)\b',
            # General file paths with extensions (more conservative)
            r'\b[\w/-]+/[\w.-]+\.[\w]{2,5}\b'
        ]
        
        mentioned_files = set()
        for pattern in file_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            mentioned_files.update(matches)
        
        # Filter out obvious false positives
        filtered = set()
        for file_ref in mentioned_files:
            # Skip very short matches, URLs, or common false positives
            if (len(file_ref) > 3 and 
                not any(prefix in file_ref.lower() for prefix in ['http', 'www.', 'example.', 'test.com']) and
                '/' in file_ref or '\\' in file_ref or file_ref.count('.') >= 1):
                filtered.add(file_ref)
        
        return filtered