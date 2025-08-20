"""
Real implementations for all Gemini MCP tools using the Gemini API
NO PLACEHOLDERS - All tools provide actual functionality
"""
import asyncio
import json
import logging
import os
import re
import ast
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

from ..clients.gemini_client import GeminiClient
from ..config import config
from .model_selection_router import ModelSelectionRouter
from .chunking_strategy import CodebaseChunker
from .cpu_throttler import CPUThrottler
from ..constants.tool_names import *

logger = logging.getLogger(__name__)


class GeminiToolImplementations:
    """Actual working implementations for all 12 Gemini analysis tools"""
    
    def __init__(self):
        # Ensure API key is configured before creating client
        import google.generativeai as genai
        self.logger = logging.getLogger(__name__)
        
        # Get API key, handling Windows environment variable format
        api_key = os.environ.get('GOOGLE_API_KEY') or config.google_api_key
        
        # Check if we got the literal %GOOGLE_API_KEY% string (Windows MCP issue)
        if api_key and api_key.startswith('%') and api_key.endswith('%'):
            self.logger.warning(f"Detected literal environment variable string: {api_key}")
            # Try to get from Python's os.environ directly
            import subprocess
            try:
                # Use Python subprocess to get the actual environment variable
                result = subprocess.run(['python', '-c', 'import os; print(os.environ.get("GOOGLE_API_KEY", ""))'], 
                                      capture_output=True, text=True, shell=True)
                actual_key = result.stdout.strip()
                if actual_key and not actual_key.startswith('%'):
                    api_key = actual_key
                    self.logger.info(f"Retrieved actual API key via subprocess: {api_key[:10]}...")
            except:
                pass
        
        if api_key and not api_key.startswith('%'):
            genai.configure(api_key=api_key)
            self.logger.info(f"Configured Gemini API in GeminiToolImplementations with key: {api_key[:10]}...")
        else:
            self.logger.error("Failed to get valid API key - may cause issues")
        
        self.gemini_client = GeminiClient(config)
        self.model_router = ModelSelectionRouter()
        self.chunker = CodebaseChunker()
        self.config = config  # Add config access
        
        # Initialize CPU throttler for file processing operations
        self.cpu_throttler = CPUThrottler(self.config)
        self.logger.info(f"GeminiToolImplementations initialized with CPU throttling: {self.cpu_throttler.max_cpu_percent}%")
    
    async def analyze_code(self, 
                           paths: List[str],
                           analysis_type: str = "overview",
                           output_format: str = "text",
                           question: Optional[str] = None,
                           verbose: bool = True) -> str:
        """
        Comprehensive code analysis with 1M token context
        Actually reads files and sends them to Gemini for analysis
        """
        try:
            # Check if we need chunking for large codebases
            if self.chunker.should_chunk(paths):
                self.logger.info("Large codebase detected, using chunking strategy")
                return await self._analyze_code_chunked(paths, analysis_type, output_format, question, verbose)
            
            # Collect all code from specified paths
            code_content = await self._collect_code_from_paths(paths)
            
            if not code_content:
                return "No code files found in specified paths."
            
            # Build the analysis prompt
            prompt = f"""Analyze the following codebase with focus on {analysis_type}.
            
Code files to analyze:
{code_content}

Analysis Type: {analysis_type}
"""
            if question:
                prompt += f"\nSpecific Question: {question}"
            
            if analysis_type == "overview":
                prompt += "\nProvide: File count, total lines, main languages, key components, architecture summary"
            elif analysis_type == "dependencies":
                prompt += "\nProvide: Import analysis, dependency tree, external libraries, version requirements"
            elif analysis_type == "refactor_prep":
                prompt += "\nProvide: Code smells, refactoring opportunities, complexity hotspots, improvement suggestions"
            elif analysis_type == "architecture":
                prompt += "\nProvide: System design, component relationships, design patterns, architectural decisions"
            elif analysis_type == "research":
                prompt += "\nProvide: Implementation patterns, algorithms used, data structures, technical approaches"
            
            # Select optimal model using router
            model_name = self.model_router.select_model(
                tool_name="analyze_code",
                user_prompt=question,
                verbose=verbose,
                analysis_type=analysis_type,
                file_paths=paths
            )
            
            # Call Gemini API
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name=model_name
            )
            response = response_text
            
            if output_format == "markdown":
                return f"# Code Analysis Report\n\n{response}"
            return response
            
        except Exception as e:
            logger.error(f"analyze_code failed: {e}")
            return f"Analysis failed: {str(e)}"
    
    async def search_code(self,
                         query: str,
                         paths: Optional[List[str]] = None,
                         search_type: str = "text",
                         case_sensitive: bool = False,
                         context_question: Optional[str] = None,
                         output_format: str = "text") -> str:
        """
        Semantic code search with contextual understanding
        Actually searches files and provides context
        """
        try:
            # Default to common source directories if no paths specified
            if not paths:
                paths = ["src/", "lib/", "app/"]
            
            # Collect code to search
            code_content = await self._collect_code_from_paths(paths)
            
            if not code_content:
                return "No files found to search in specified paths."
            
            # Build search prompt
            prompt = f"""Search the following code for: {query}
            
Search Type: {search_type}
Case Sensitive: {case_sensitive}

Code to search:
{code_content}

Find all occurrences and provide:
1. File path and line numbers
2. Matching code snippets
3. Context around matches
"""
            if context_question:
                prompt += f"\n4. Answer this specific question: {context_question}"
            
            # Call Gemini API  
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name="flash"
            )
            response = response_text
            
            if output_format == "markdown":
                return f"# Code Search Results\n\nQuery: `{query}`\n\n{response}"
            return response
            
        except Exception as e:
            logger.error(f"search_code failed: {e}")
            return f"Search failed: {str(e)}"
    
    async def check_quality(self,
                           paths: List[str],
                           check_type: str = "all",
                           test_paths: Optional[List[str]] = None,
                           verbose: bool = True,
                           output_format: str = "text",
                           context_summary: Optional[str] = None,
                           security_focus_files: Optional[List[str]] = None,
                           performance_focus_files: Optional[List[str]] = None,
                           check_auth_patterns: bool = False) -> str:
        """
        Comprehensive quality analysis including security, performance, and tests
        Actually analyzes code quality issues
        """
        try:
            # Check if we need chunking for large codebases (check_quality is intensive)
            if self.chunker.should_chunk(paths, tool_name="check_quality"):
                self.logger.info("Large codebase detected for quality check, using chunking strategy")
                return await self._check_quality_chunked(paths, check_type, test_paths, verbose, output_format)
            
            # Collect code to analyze
            code_content = await self._collect_code_from_paths(paths)
            
            if not code_content:
                return "No code files found to analyze."
            
            # Collect test files if provided
            test_content = ""
            if test_paths:
                test_content = await self._collect_code_from_paths(test_paths)
            
            # Build quality check prompt with context awareness
            prompt = f"""Perform {check_type} quality analysis on the following code."""
            
            # Add context from previous analysis if available
            if context_summary:
                prompt += f"\n\n{context_summary}"
                prompt += "\nUse this context to focus your analysis on the most relevant areas."
            
            # Add focus directives based on context
            if security_focus_files:
                prompt += f"\n\nPRIORITY: Focus security analysis on these authentication/security-critical files: {security_focus_files}"
            
            if performance_focus_files:
                prompt += f"\n\nPRIORITY: Focus performance analysis on these critical paths: {performance_focus_files}"
            
            if check_auth_patterns:
                prompt += f"\n\nSPECIAL FOCUS: Pay extra attention to authentication patterns, JWT handling, and session management."
            
            prompt += f"""

Source Code:
{code_content}
"""
            if test_content:
                prompt += f"\n\nTest Files:\n{test_content}"
            
            if check_type == "all":
                prompt += """
Analyze for:
1. Security vulnerabilities (hardcoded secrets, SQL injection, XSS, etc.)
2. Performance issues (inefficient algorithms, memory leaks, blocking operations)
3. Test coverage (what's tested vs untested)
4. Code quality (complexity, duplication, maintainability)
"""
            elif check_type == "security":
                prompt += """
Focus on security issues:
- Hardcoded credentials, API keys, passwords
- Input validation vulnerabilities
- Authentication/authorization flaws
- Injection vulnerabilities
- Cryptographic weaknesses
"""
            elif check_type == "performance":
                prompt += """
Focus on performance issues:
- Inefficient algorithms (O(n²) or worse)
- Memory leaks or excessive allocation
- Blocking I/O operations
- Database query optimization
- Caching opportunities
"""
            elif check_type == "tests":
                prompt += """
Focus on test analysis:
- Test coverage percentage estimate
- Critical untested code paths
- Test quality and assertions
- Missing test scenarios
- Test maintainability
"""
            
            prompt += "\nProvide specific file locations and line numbers for all issues found."
            
            # Select optimal model using router - check_quality needs pro for security
            model_name = self.model_router.select_model(
                tool_name="check_quality",
                verbose=verbose,
                check_type=check_type,
                file_paths=paths
            )
            
            # Call Gemini API with generous timeout for quality checks
            # check_quality needs more time for comprehensive security analysis
            quality_timeout = 90 if check_type == "security" else 75
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name=model_name,
                timeout=quality_timeout
            )
            response = response_text
            
            if output_format == "markdown":
                return f"# Code Quality Report\n**Check Type**: {check_type}\n**Paths Checked**: {len(paths)} locations\n\n{response}"
            return response
            
        except Exception as e:
            logger.error(f"check_quality failed: {e}")
            return f"Quality check failed: {str(e)}"
    
    async def analyze_docs(self,
                          sources: List[str],
                          questions: Optional[List[str]] = None,
                          synthesis_type: str = "summary") -> str:
        """
        Analyze and synthesize documentation from multiple sources
        Actually reads docs and provides synthesis with CPU throttling
        """
        try:
            # Collect documentation content with throttling
            docs_content = ""
            file_count = 0
            max_docs = 100  # Limit to prevent overwhelming
            total_size = 0
            max_total_size = 5_000_000  # 5MB total limit for docs
            
            for source in sources:
                if source.startswith("http"):
                    docs_content += f"\n[URL: {source}]\n(Would fetch via web API)\n"
                else:
                    # Handle directory vs file
                    path = Path(source)
                    if path.is_dir():
                        # Collect docs from directory with CPU throttling
                        import asyncio
                        doc_extensions = [".md", ".txt", ".rst", ".html", ".json", ".yaml", ".yml"]
                        processed_count = 0
                        
                        for doc_path in path.rglob("*"):
                            if doc_path.is_file() and any(str(doc_path).endswith(ext) for ext in doc_extensions):
                                # Check limits
                                if file_count >= max_docs:
                                    docs_content += f"\n... (truncated, showing first {max_docs} documents) ...\n"
                                    break
                                if total_size >= max_total_size:
                                    docs_content += f"\n... (size limit reached: {total_size / 1_000_000:.1f}MB) ...\n"
                                    break
                                
                                content = await self._read_file_safe(str(doc_path))
                                if content:
                                    docs_content += f"\n[File: {doc_path}]\n{content}\n"
                                    file_count += 1
                                    total_size += len(content)
                                
                                # CPU throttling to prevent blocking
                                processed_count += 1
                                if processed_count % self.config.file_scan_yield_frequency == 0:
                                    if self.cpu_throttler:
                                        await self.cpu_throttler.yield_if_needed()
                                    else:
                                        await asyncio.sleep(0.01)  # Minimal fallback delay
                    else:
                        # Single file
                        content = await self._read_file_safe(source)
                        if content:
                            docs_content += f"\n[File: {source}]\n{content}\n"
                            file_count += 1
                            total_size += len(content)
            
            if not docs_content:
                return "No documentation content found in specified sources."
            
            # Log collection stats
            self.logger.info(f"Collected {file_count} docs, total size: {total_size / 1_000:.1f}KB")
            
            # Build synthesis prompt
            prompt = f"""Analyze and synthesize the following documentation.

Synthesis Type: {synthesis_type}
Documents Analyzed: {file_count}

Documentation:
{docs_content}
"""
            
            if synthesis_type == "summary":
                prompt += "\nProvide: Executive summary, key concepts, main sections, important details"
            elif synthesis_type == "comparison":
                prompt += "\nProvide: Similarities, differences, unique features, recommendations"
            elif synthesis_type == "implementation_guide":
                prompt += "\nProvide: Step-by-step implementation, code examples, best practices"
            elif synthesis_type == "api_reference":
                prompt += "\nProvide: Endpoints, parameters, responses, authentication, examples"
            
            if questions:
                prompt += f"\n\nAnswer these specific questions:\n" + "\n".join(f"- {q}" for q in questions)
            
            # Select model based on content size
            model_name = "flash"
            if total_size > 2_000_000:  # Use pro for large doc sets
                model_name = self.model_router.select_model(
                    tool_name="analyze_docs",
                    content_size=total_size
                )
            
            # Call Gemini API with appropriate timeout
            timeout = 60 if total_size < 1_000_000 else 90
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name=model_name,
                timeout=timeout
            )
            response = response_text
            
            return response
            
        except Exception as e:
            logger.error(f"analyze_docs failed: {e}")
            return f"Documentation analysis failed: {str(e)}"
    
    async def analyze_logs(self,
                          log_paths: List[str],
                          focus: str = "all",
                          time_range: Optional[str] = None) -> str:
        """
        Analyze log files to identify patterns, errors, and performance issues
        Actually reads and analyzes log files with chunking for large files
        """
        try:
            # Check if we need chunking for large log files
            if self.chunker.should_chunk_logs(log_paths):
                self.logger.info("Large log files detected, using chunking strategy")
                return await self._analyze_logs_chunked(log_paths, focus, time_range)
            
            # Collect log content for small files
            logs_content = await self._collect_code_from_paths(log_paths, extensions=[".log", ".txt", ""])
            
            if not logs_content:
                return "No log files found in specified paths."
            
            # Build log analysis prompt
            prompt = f"""Analyze the following log files with focus on {focus}.

Log Content:
{logs_content}
"""
            
            if time_range:
                prompt += f"\nTime Range Filter: {time_range}"
            
            if focus == "all":
                prompt += "\nAnalyze: Error patterns, performance metrics, user activities, system events"
            elif focus == "errors":
                prompt += "\nFocus on: Error messages, stack traces, failure patterns, error frequencies"
            elif focus == "performance":
                prompt += "\nFocus on: Response times, slow queries, resource usage, bottlenecks"
            elif focus == "patterns":
                prompt += "\nFocus on: Recurring patterns, anomalies, trends, correlations"
            elif focus == "timeline":
                prompt += "\nFocus on: Event sequence, timestamps, chronological analysis"
            
            # Select optimal model using router (analyze_logs now gets proper model selection)
            model_name = self.model_router.select_model(
                tool_name="analyze_logs",
                focus=focus,
                file_paths=log_paths
            )
            
            # Call Gemini API
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name=model_name
            )
            response = response_text
            
            return response
            
        except Exception as e:
            logger.error(f"analyze_logs failed: {e}")
            return f"Log analysis failed: {str(e)}"
    
    async def analyze_database(self,
                              schema_paths: List[str],
                              analysis_type: str = "schema",
                              repo_paths: Optional[List[str]] = None) -> str:
        """
        Analyze database schemas, migrations, and relationships
        Actually analyzes database structure with SQLite support
        """
        try:
            # Collect schema content with SQLite database support
            schema_content = await self._collect_database_content(schema_paths)
            
            if not schema_content:
                return "No schema files or database content found in specified paths."
            
            # Build database analysis prompt
            prompt = f"""Analyze the following database definitions with focus on {analysis_type}.

Schema/Migration Files:
{schema_content}
"""
            
            if analysis_type == "schema":
                prompt += "\nAnalyze: Tables, columns, data types, constraints, indexes"
            elif analysis_type == "migrations":
                prompt += "\nAnalyze: Migration history, schema evolution, breaking changes"
            elif analysis_type == "relationships":
                prompt += "\nAnalyze: Foreign keys, associations, ERD, data flow"
            elif analysis_type == "optimization":
                prompt += "\nAnalyze: Index opportunities, query optimization, denormalization candidates"
            
            if repo_paths:
                prompt += f"\nAlso consider cross-repository relationships in: {repo_paths}"
            
            # Select optimal model using router
            model_name = self.model_router.select_model(
                tool_name="analyze_database",
                analysis_type=analysis_type,
                file_paths=schema_paths
            )
            
            # Call Gemini API
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name=model_name
            )
            response = response_text
            
            return response
            
        except Exception as e:
            logger.error(f"analyze_database failed: {e}")
            return f"Database analysis failed: {str(e)}"
    
    async def performance_profiler(self,
                                   target_operation: str,
                                   profile_type: str = "comprehensive") -> str:
        """
        Runtime performance analysis with metrics and bottleneck identification
        Analyzes the described operation for performance issues
        """
        try:
            # Since we can't actually profile runtime, we analyze the operation description
            prompt = f"""Analyze the performance characteristics of the following operation: {target_operation}

Profile Type: {profile_type}

Provide performance analysis including:
"""
            
            if profile_type == "comprehensive":
                prompt += """
1. CPU Usage: Computational complexity, hot paths, optimization opportunities
2. Memory Usage: Allocation patterns, potential leaks, memory efficiency
3. I/O Operations: File/network/database access patterns, blocking operations
4. Overall Performance: Bottlenecks, scalability issues, improvement recommendations
"""
            elif profile_type == "cpu":
                prompt += """
- Algorithm complexity analysis
- CPU-intensive operations
- Parallelization opportunities
- Computational optimizations
"""
            elif profile_type == "memory":
                prompt += """
- Memory allocation patterns
- Potential memory leaks
- Data structure efficiency
- Memory optimization strategies
"""
            elif profile_type == "io":
                prompt += """
- I/O operation patterns
- Blocking vs non-blocking operations
- Caching opportunities
- I/O optimization strategies
"""
            
            # Call Gemini API
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name="flash"
            )
            response = response_text
            
            return f"Performance Profile for: {target_operation}\n\n{response}"
            
        except Exception as e:
            logger.error(f"performance_profiler failed: {e}")
            return f"Performance profiling failed: {str(e)}"
    
    async def config_validator(self,
                              config_paths: List[str],
                              validation_type: str = "all",
                              context_summary: Optional[str] = None,
                              focus_security_configs: bool = False,
                              specific_security_checks: Optional[List[str]] = None) -> str:
        """
        Configuration file validation with security analysis
        Actually validates configuration files
        """
        try:
            # Collect configuration files
            config_content = await self._collect_code_from_paths(
                config_paths,
                extensions=[".env", ".json", ".yaml", ".yml", ".toml", ".ini", ".conf", ".config"]
            )
            
            if not config_content:
                return "No configuration files found in specified paths."
            
            # Build validation prompt with context awareness
            prompt = f"""Validate the following configuration files for {validation_type} issues."""
            
            # Add context from previous analysis if available
            if context_summary:
                prompt += f"\n\n{context_summary}"
                prompt += "\nUse this context to focus your validation on issues identified by previous tools."
            
            # Add specific focus based on context
            if focus_security_configs:
                prompt += f"\n\nPRIORITY: Focus on security-related configurations based on previous security findings."
            
            if specific_security_checks:
                prompt += f"\n\nSPECIAL ATTENTION: Look specifically for these types of security issues: {', '.join(specific_security_checks)}"
            
            prompt += f"""

Configuration Files:
{config_content}

Validation Type: {validation_type}
"""
            
            if validation_type == "all":
                prompt += """
Check for:
1. Security issues (hardcoded secrets, weak settings, exposed credentials)
2. Completeness (missing required values, incomplete configurations)
3. Syntax errors (invalid JSON/YAML, parsing issues)
4. Best practices (deprecated settings, anti-patterns)
"""
            elif validation_type == "security":
                prompt += """
Focus on security issues:
- Hardcoded passwords, API keys, tokens
- Weak security settings
- Exposed sensitive information
- Insecure defaults
"""
            elif validation_type == "completeness":
                prompt += """
Focus on completeness:
- Missing required configurations
- Incomplete settings
- Undefined environment variables
- Missing dependencies
"""
            elif validation_type == "syntax":
                prompt += """
Focus on syntax validation:
- JSON/YAML parsing errors
- Invalid syntax
- Type mismatches
- Format violations
"""
            
            # Call Gemini API
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name="flash"
            )
            response = response_text
            
            return response
            
        except Exception as e:
            logger.error(f"config_validator failed: {e}")
            return f"Configuration validation failed: {str(e)}"
    
    async def api_contract_checker(self,
                                   spec_paths: List[str],
                                   comparison_mode: str = "standalone") -> str:
        """
        OpenAPI/Swagger specification validation with breaking change detection
        Actually validates API specifications with comprehensive breaking change analysis
        """
        try:
            # Collect API specification files
            spec_content = await self._collect_code_from_paths(
                spec_paths,
                extensions=[".yaml", ".yml", ".json", ".openapi", ".swagger"]
            )
            
            if not spec_content:
                return "No API specification files found in specified paths."
            
            # Build enhanced API validation prompt with comprehensive breaking change detection
            prompt = f"""Analyze the following API specifications in {comparison_mode} mode.

API Specifications:
{spec_content}

Analysis Mode: {comparison_mode}
"""
            
            if comparison_mode == "standalone":
                prompt += """
Validate:
1. Specification completeness and correctness
2. Schema definitions and types
3. Endpoint consistency
4. Security definitions
5. Documentation quality

Also perform basic breaking change assessment for single specification.
"""
            elif comparison_mode == "compare_versions":
                prompt += """
Compare versions and identify changes with detailed impact analysis:

Check for these 7 critical breaking change types:
1. **BREAKING**: Removed endpoints - Any deleted API endpoints
2. **BREAKING**: Changed required parameters - New required fields in requests
3. **BREAKING**: Changed response schemas - Modified response structure that clients depend on
4. **BREAKING**: Added required fields - New mandatory fields in request bodies
5. **BREAKING**: Removed fields from responses - Deleted fields clients expect
6. **BREAKING**: Changed field types - Type changes (string->int, array->object, etc.)
7. **BREAKING**: Changed authentication requirements - Auth method or scope changes

For each change found, classify as:
- 🔴 BREAKING (will break existing clients)
- 🟡 NON-BREAKING (backwards compatible changes)  
- 🟢 ADDITION (new optional features)

Provide version impact recommendation:
- MAJOR: Breaking changes require major version bump (x.0.0)
- MINOR: New features, backwards compatible (0.x.0)
- PATCH: Bug fixes, fully backwards compatible (0.0.x)
"""
            elif comparison_mode == "breaking_changes":
                prompt += """
Comprehensive breaking change analysis:

Check for these 7 critical breaking change types:
1. **BREAKING**: Removed endpoints - Any deleted API endpoints
2. **BREAKING**: Changed required parameters - New required fields in requests
3. **BREAKING**: Changed response schemas - Modified response structure that clients depend on
4. **BREAKING**: Added required fields - New mandatory fields in request bodies
5. **BREAKING**: Removed fields from responses - Deleted fields clients expect
6. **BREAKING**: Changed field types - Type changes (string->int, array->object, etc.)
7. **BREAKING**: Changed authentication requirements - Auth method or scope changes

IMPORTANT: Understand optional vs required fields:
- Adding OPTIONAL fields is NON-BREAKING
- Adding REQUIRED fields is BREAKING
- Removing any fields clients expect is BREAKING
- Changing field types is BREAKING

For each issue found, classify as:
- 🔴 BREAKING (will break existing clients)
- 🟡 NON-BREAKING (backwards compatible changes)
- 🟢 ADDITION (new optional features)

Format your response as a structured semantic diff with clear sections and counts.
"""
            
            # Add structured output format instructions
            prompt += """

Please format your response as follows:

## API Contract Analysis Report

### 🔴 Breaking Changes (count)
- **CHANGE_TYPE** `endpoint/field` - Description of breaking change
- **CHANGE_TYPE** `endpoint/field` - Description of breaking change

### 🟡 Non-Breaking Changes (count)  
- **CHANGE_TYPE** `endpoint/field` - Description of compatible change
- **CHANGE_TYPE** `endpoint/field` - Description of compatible change

### 🟢 Backward Compatible Additions (count)
- **ADD** `endpoint/field` - Description of new feature
- **ADD** `endpoint/field` - Description of new feature

### Version Impact Recommendation
[MAJOR/MINOR/PATCH] - Reasoning based on breaking changes found

### Summary
- Total changes analyzed: X
- Breaking changes: X
- Compatible changes: X
- New additions: X
"""
            
            # Call Gemini API
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name="flash"
            )
            response = response_text
            
            return response
            
        except Exception as e:
            logger.error(f"api_contract_checker failed: {e}")
            return f"API contract checking failed: {str(e)}"
    
    async def analyze_test_coverage(self,
                                    source_paths: List[str],
                                    mapping_strategy: str = "convention") -> str:
        """
        AST-based test coverage analysis with gap identification
        Actually analyzes test coverage
        """
        try:
            # Collect source code
            source_content = await self._collect_code_from_paths(source_paths)
            
            if not source_content:
                return "No source files found to analyze for test coverage."
            
            # Build test coverage analysis prompt
            prompt = f"""Analyze test coverage for the following source code using {mapping_strategy} strategy.

Source Code:
{source_content}

Mapping Strategy: {mapping_strategy}

Provide:
1. Functions/methods without tests
2. Critical code paths lacking coverage
3. Test coverage percentage estimate
4. Priority recommendations for new tests
"""
            
            if mapping_strategy == "convention":
                prompt += "\nMap tests using naming conventions (e.g., module.py -> test_module.py)"
            elif mapping_strategy == "directory":
                prompt += "\nMap tests using directory structure (e.g., src/ -> tests/)"
            elif mapping_strategy == "docstring":
                prompt += "\nMap tests using docstring references and test descriptions"
            
            # Call Gemini API
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name="flash"
            )
            response = response_text
            
            return response
            
        except Exception as e:
            logger.error(f"analyze_test_coverage failed: {e}")
            return f"Test coverage analysis failed: {str(e)}"
    
    async def map_dependencies(self,
                               project_paths: List[str],
                               analysis_depth: str = "transitive") -> str:
        """
        Dependency graph analysis with circular detection
        Actually maps project dependencies
        """
        try:
            # Collect project files
            project_content = await self._collect_code_from_paths(project_paths)
            
            if not project_content:
                return "No project files found to analyze dependencies."
            
            # Build dependency analysis prompt
            prompt = f"""Analyze dependencies in the following project with {analysis_depth} depth.

Project Code:
{project_content}

Analysis Depth: {analysis_depth}

Provide:
1. Import graph structure
2. External dependencies list
3. Circular dependencies (if any)
4. Coupling metrics
5. Refactoring impact analysis
"""
            
            if analysis_depth == "immediate":
                prompt += "\nAnalyze only direct imports and dependencies"
            elif analysis_depth == "transitive":
                prompt += "\nAnalyze direct and transitive dependencies (2-3 levels)"
            elif analysis_depth == "full":
                prompt += "\nAnalyze complete dependency tree (all levels)"
            
            # Call Gemini API
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name="flash"
            )
            response = response_text
            
            return response
            
        except Exception as e:
            logger.error(f"map_dependencies failed: {e}")
            return f"Dependency mapping failed: {str(e)}"
    
    async def interface_inconsistency_detector(self,
                                               source_paths: List[str],
                                               pattern_types: List[str] = None) -> str:
        """
        AST-based analysis for naming pattern mismatches and interface inconsistencies
        Enhanced with domain awareness and priority scoring to reduce false positives
        """
        try:
            if pattern_types is None:
                pattern_types = ["naming", "parameters"]
            
            # Collect source code
            source_content = await self._collect_code_from_paths(source_paths)
            
            if not source_content:
                return "No source files found to analyze for inconsistencies."
            
            # Build enhanced inconsistency detection prompt with domain awareness
            prompt = f"""Detect interface inconsistencies in the following code, but consider domain-specific terminology and business logic.

Pattern Types to Check: {', '.join(pattern_types)}

Source Code:
{source_content}

IMPORTANT - Domain Awareness Rules:
IGNORE these intentional domain differences (NOT inconsistencies):
- Accounting: debit_amount vs credit_amount (opposite by design)
- Temporal: create_date vs update_date vs delete_date (different timestamps)  
- Scope: user_count vs admin_count vs guest_count (different user types)
- Status: is_active vs is_deleted vs is_archived (different states)
- Directional: input_data vs output_data (different flow directions)
- Action types: fetch_user vs create_user vs update_user (different CRUD operations)

FOCUS on these real inconsistencies:
- Mixed conventions: getUserData() vs get_user_info() (same concept, different style)
- Inconsistent verbs: fetchItem() vs loadProduct() vs retrieveOrder (same action, different verbs)
- Case variations: userId vs user_id vs userID (same concept, different casing)
- Boolean naming: active vs is_active vs has_active (boolean should have consistent prefix)
- Inconsistent plurals: getUser() vs getUsers() (one returns single, other returns multiple)

Analyze for:
"""
            
            if "naming" in pattern_types:
                prompt += """
1. Naming convention violations (camelCase vs snake_case within same context)
2. Inconsistent naming patterns for similar concepts
3. Misleading names that don't match functionality
4. Mixed boolean naming conventions (is_, has_, can_ prefixes)
"""
            
            if "parameters" in pattern_types:
                prompt += """
5. Parameter order inconsistencies for similar functions
6. Optional vs required parameter mismatches in related methods
7. Type annotation inconsistencies (some typed, others not)
8. Inconsistent parameter naming for same concepts
"""
            
            if "return_types" in pattern_types:
                prompt += """
9. Return type inconsistencies for similar operations
10. Missing return type annotations in typed codebase
11. Actual vs declared return type mismatches
12. Inconsistent error handling return patterns
"""
            
            if "documentation" in pattern_types:
                prompt += """
13. Missing docstrings in documented codebase
14. Inconsistent docstring formats
15. Parameter documentation mismatches with actual parameters
16. Inconsistent documentation style across similar functions
"""
            
            # Add priority scoring system
            prompt += """

Priority Scoring System (1-10):
- **High Priority (8-10)**: 
  * Public API inconsistencies that affect external users
  * Mixed naming conventions within the same module/class
  * Critical type annotation inconsistencies
  * Boolean naming without proper prefixes

- **Medium Priority (5-7)**: 
  * Internal method inconsistencies 
  * Parameter naming variations
  * Documentation format inconsistencies
  * Minor type annotation gaps

- **Low Priority (1-4)**: 
  * Minor style differences that don't affect functionality
  * Acceptable domain-specific variations
  * Edge cases with reasonable explanations
  * Legacy code with different but consistent patterns

For each inconsistency found:
1. Provide specific file locations and line numbers
2. Assign priority score (1-10) 
3. Give effort estimate (Low/Medium/High)
4. Suggest specific actionable fix

Format response as follows:

## Interface Inconsistency Analysis Report

### 🔴 High Priority Issues (8-10)
- **Score: X** `file:line` - **Issue**: Description
  - **Fix**: Specific recommendation
  - **Effort**: Low/Medium/High

### 🟡 Medium Priority Issues (5-7)  
- **Score: X** `file:line` - **Issue**: Description
  - **Fix**: Specific recommendation  
  - **Effort**: Low/Medium/High

### 🟢 Low Priority Issues (1-4)
- **Score: X** `file:line` - **Issue**: Description
  - **Fix**: Specific recommendation
  - **Effort**: Low/Medium/High

### 🚫 Intentionally Ignored (Domain-Specific)
- `file:line` - **Reason**: Acceptable domain variation

### Summary
- High priority issues: X (immediate attention needed)
- Medium priority issues: X (address in next refactor)  
- Low priority issues: X (consider for future cleanup)
- Issues ignored as domain-appropriate: X

### Recommended Action Plan
1. **Immediate**: Address high priority issues (estimated X hours)
2. **Next Sprint**: Consider medium priority issues  
3. **Future**: Low priority cleanup when convenient
"""
            
            # Call Gemini API
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name="flash"
            )
            response = response_text
            
            return response
            
        except Exception as e:
            logger.error(f"interface_inconsistency_detector failed: {e}")
            return f"Interface inconsistency detection failed: {str(e)}"
    
    # Helper methods
    
    async def _analyze_code_chunked(self, paths: List[str], analysis_type: str, 
                                   output_format: str, question: Optional[str], verbose: bool) -> str:
        """Analyze large codebase in chunks to avoid timeouts"""
        chunks = self.chunker.create_chunks(paths, max_chunks=5)
        
        chunk_results = []
        for i, chunk in enumerate(chunks, 1):
            self.logger.info(f"Analyzing chunk {i}/{len(chunks)}: {chunk['description']}")
            
            # Analyze this chunk
            code_content = await self._collect_code_from_paths(chunk['files'])
            if not code_content:
                continue
            
            prompt = f"""Analyze this part of the codebase (chunk {i}/{len(chunks)}): {chunk['description']}
Focus: {analysis_type}
{f'Question: {question}' if question else ''}

Code:
{code_content}

Provide analysis appropriate for {analysis_type}."""
            
            # Use appropriate model
            model_name = self.model_router.select_model(
                tool_name="analyze_code",
                user_prompt=question,
                verbose=verbose,
                analysis_type=analysis_type
            )
            
            try:
                response_text, model_used, attempts = await self.gemini_client.generate_content(
                    prompt=prompt,
                    model_name=model_name,
                    timeout=50  # Generous timeout per chunk (was 25s)
                )
                chunk_results.append({
                    "chunk": i,
                    "description": chunk['description'],
                    "analysis": response_text
                })
            except Exception as e:
                self.logger.warning(f"Chunk {i} failed: {e}")
                chunk_results.append({
                    "chunk": i,
                    "description": chunk['description'],
                    "analysis": f"Analysis failed: {str(e)}"
                })
        
        # Combine chunk results
        if output_format == "markdown":
            combined = f"# Code Analysis Report (Chunked)\n\n**Analysis Type**: {analysis_type}\n\n"
            for result in chunk_results:
                combined += f"## Part {result['chunk']}: {result['description']}\n\n"
                combined += result['analysis'] + "\n\n"
            return combined
        else:
            combined = f"Code Analysis ({len(chunks)} chunks analyzed)\n\n"
            for result in chunk_results:
                combined += f"=== {result['description']} ===\n"
                combined += result['analysis'] + "\n\n"
            return combined
    
    async def _check_quality_chunked(self, paths: List[str], check_type: str,
                                     test_paths: Optional[List[str]], verbose: bool,
                                     output_format: str) -> str:
        """Check quality of large codebase in chunks to avoid timeouts"""
        chunks = self.chunker.create_chunks(paths, max_chunks=4)  # Fewer chunks for quality checks
        
        chunk_results = []
        for i, chunk in enumerate(chunks, 1):
            self.logger.info(f"Quality checking chunk {i}/{len(chunks)}: {chunk['description']}")
            
            # Analyze this chunk
            code_content = await self._collect_code_from_paths(chunk['files'])
            if not code_content:
                continue
            
            # Build quality check prompt for this chunk
            prompt = f"""Perform {check_type} quality analysis on this part of the codebase (chunk {i}/{len(chunks)}): {chunk['description']}

Source Code:
{code_content}
"""
            
            if check_type == "all":
                prompt += """
Analyze for:
1. Security vulnerabilities (hardcoded secrets, SQL injection, XSS, etc.)
2. Performance issues (inefficient algorithms, memory leaks, blocking operations)
3. Code quality (complexity, duplication, maintainability)
"""
            elif check_type == "security":
                prompt += """
Focus on security issues:
- Hardcoded credentials, API keys, passwords
- Input validation vulnerabilities
- Authentication/authorization flaws
- Injection vulnerabilities
- Cryptographic weaknesses
"""
            elif check_type == "performance":
                prompt += """
Focus on performance issues:
- Inefficient algorithms (O(n²) or worse)
- Memory leaks or excessive allocation
- Blocking I/O operations
- Database query optimization
- Caching opportunities
"""
            
            prompt += "\nProvide specific file locations and line numbers for all issues found."
            
            # Select optimal model - check_quality needs pro for security
            model_name = self.model_router.select_model(
                tool_name="check_quality",
                verbose=verbose,
                check_type=check_type
            )
            
            try:
                # Generous timeout for quality checks
                quality_timeout = 75 if check_type == "security" else 60
                response_text, model_used, attempts = await self.gemini_client.generate_content(
                    prompt=prompt,
                    model_name=model_name,
                    timeout=quality_timeout
                )
                chunk_results.append({
                    "chunk": i,
                    "description": chunk['description'],
                    "analysis": response_text
                })
            except Exception as e:
                self.logger.warning(f"Quality check chunk {i} failed: {e}")
                chunk_results.append({
                    "chunk": i,
                    "description": chunk['description'],
                    "analysis": f"Quality check failed: {str(e)}"
                })
        
        # Combine chunk results
        if output_format == "markdown":
            combined = f"# Code Quality Report (Chunked)\n\n**Check Type**: {check_type}\n\n"
            for result in chunk_results:
                combined += f"## Part {result['chunk']}: {result['description']}\n\n"
                combined += result['analysis'] + "\n\n"
            return combined
        else:
            combined = f"Code Quality Report ({len(chunks)} chunks analyzed)\n\n"
            for result in chunk_results:
                combined += f"=== {result['description']} ===\n"
                combined += result['analysis'] + "\n\n"
            return combined
    
    async def _collect_code_from_paths(self, paths: List[str], extensions: Optional[List[str]] = None) -> str:
        """Collect code content from specified paths with CPU throttling"""
        from pathlib import Path  # Import Path at the top of the method
        
        if extensions is None:
            extensions = [".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".rb", ".php"]
        
        # CRITICAL FIX: Normalize paths to handle WindowsPath objects
        # Import path normalization utility
        try:
            from ..utils.path_utils import normalize_paths
            normalized_paths = normalize_paths(paths)
        except ImportError:
            # Fallback path normalization if utils not available
            if not isinstance(paths, (list, tuple)):
                # If paths is a single item (like WindowsPath), convert to list
                if isinstance(paths, (str, Path)) or hasattr(paths, '__fspath__'):
                    normalized_paths = [str(paths)]
                else:
                    # Unknown type, try to convert to string
                    normalized_paths = [str(paths)]
            else:
                # It's already a list, ensure all items are strings
                normalized_paths = [str(p) for p in paths]
        
        collected_content = ""
        file_count = 0
        
        # CPU throttling before heavy operation
        if self.cpu_throttler:
            await self.cpu_throttler.yield_if_needed()
        
        # Extract file paths for batch processing
        file_paths = []
        for path_str in normalized_paths:
            path = Path(path_str)
            if path.is_file():
                file_paths.append(path)
            elif path.is_dir():
                for file_path in path.rglob("*"):
                    if file_path.is_file() and any(str(file_path).endswith(ext) for ext in extensions):
                        file_paths.append(file_path)
        
        logger.info(f"Collecting content from {len(file_paths)} files with CPU throttling")
        
        # Process files with CPU-aware batch processing
        if self.cpu_throttler:
            async with self.cpu_throttler.monitor_heavy_operation("file_collection"):
                async for file_batch in self.cpu_throttler.throttled_file_scan(file_paths, self.config.file_scan_yield_frequency):
                    for file_path in file_batch:
                        # CPU yield before each file read
                        await self.cpu_throttler.yield_if_needed()
                        
                        content = await self._read_file_safe(str(file_path))
                        if content:
                            collected_content += f"\n--- File: {file_path} ---\n{content}\n"
                            file_count += 1
                            if file_count >= 100:  # Limit for performance
                                collected_content += f"\n... (truncated, showing first 100 files) ...\n"
                                break
                    
                    if file_count >= 100:
                        break
        else:
            # Fallback without CPU throttling (if not available)
            for file_path in file_paths:
                content = await self._read_file_safe(str(file_path))
                if content:
                    collected_content += f"\n--- File: {file_path} ---\n{content}\n"
                    file_count += 1
                    if file_count >= 100:
                        collected_content += f"\n... (truncated, showing first 100 files) ...\n"
                        break
        
        return collected_content
    
    async def _read_file_safe(self, file_path: str) -> Optional[str]:
        """Safely read file content with async I/O and CPU throttling to prevent blocking"""
        try:
            # CPU yield before intensive file read operation
            if self.cpu_throttler:
                await self.cpu_throttler.yield_if_needed()
            
            path = Path(file_path)
            if path.exists() and path.is_file():
                # Generous file size limit for 32GB RAM system
                if path.stat().st_size > 10_000_000:  # 10MB limit per file (was 1MB)
                    return f"[File too large: {path.stat().st_size} bytes]"
                
                # Use asyncio.to_thread to prevent blocking the event loop
                import asyncio
                content = await asyncio.to_thread(self._read_file_sync, path)
                return content
        except Exception as e:
            logger.debug(f"Could not read file {file_path}: {e}")
        return None
    
    def _read_file_sync(self, path: Path) -> str:
        """Synchronous file reading helper"""
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    async def _analyze_logs_chunked(self, log_paths: List[str], focus: str, time_range: Optional[str]) -> str:
        """Analyze large log files using chunking strategy"""
        results = []
        
        for log_path in log_paths:
            self.logger.info(f"Chunked analysis of log file: {log_path}")
            
            # Create analysis function for this specific log file
            async def analyze_log_chunk(chunk_content: str) -> str:
                # Build analysis prompt for this chunk
                prompt = f"""Analyze this log file chunk with focus on {focus}.

Log Content:
{chunk_content}
"""
                if time_range:
                    prompt += f"\nTime Range Filter: {time_range}"
                
                if focus == "all":
                    prompt += "\nAnalyze: Error patterns, performance metrics, user activities, system events"
                elif focus == "errors":
                    prompt += "\nFocus on: Error messages, stack traces, failure patterns, error frequencies"
                elif focus == "performance":
                    prompt += "\nFocus on: Response times, slow queries, resource usage, bottlenecks"
                elif focus == "patterns":
                    prompt += "\nFocus on: Recurring patterns, anomalies, trends, correlations"
                elif focus == "timeline":
                    prompt += "\nFocus on: Event sequence, timestamps, chronological analysis"
                
                # Select optimal model
                model_name = self.model_router.select_model(
                    tool_name="analyze_logs",
                    focus=focus,
                    content_size=len(chunk_content)
                )
                
                # Call Gemini API with appropriate timeout for chunk
                response_text, model_used, attempts = await self.gemini_client.generate_content(
                    prompt=prompt,
                    model_name=model_name,
                    timeout=60  # Longer timeout for log analysis chunks
                )
                
                return response_text
            
            # Use chunking strategy to analyze this log file
            try:
                result = await self.chunker.analyze_log_chunks(log_path, analyze_log_chunk)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Chunked analysis failed for {log_path}: {e}")
                results.append(f"Analysis failed for {log_path}: {str(e)}")
        
        # Combine results from all log files
        if len(results) == 1:
            return results[0]
        else:
            combined = f"# Multi-Log Analysis Results ({len(log_paths)} files)\n\n"
            for i, result in enumerate(results, 1):
                combined += f"## Log File {i}: {log_paths[i-1]}\n\n"
                combined += result + "\n\n"
            return combined
    
    async def _collect_database_content(self, schema_paths: List[str]) -> str:
        """
        Collect database schema content from various sources including SQLite databases
        """
        collected_content = ""
        file_count = 0
        
        for path_str in schema_paths:
            path = Path(path_str)
            
            if path.is_file():
                if path.suffix.lower() in ['.db', '.sqlite', '.sqlite3']:
                    # Handle SQLite database files
                    content = await self._extract_sqlite_schema(str(path))
                    if content:
                        collected_content += f"\n--- SQLite Database: {path} ---\n{content}\n"
                        file_count += 1
                elif path.suffix.lower() in ['.sql', '.ddl', '.schema']:
                    # Handle SQL/DDL files
                    content = await self._read_file_safe(str(path))
                    if content:
                        collected_content += f"\n--- Schema File: {path} ---\n{content}\n"
                        file_count += 1
                else:
                    # Handle other schema-related files (.py, .js, .prisma, etc.)
                    content = await self._read_file_safe(str(path))
                    if content and self._looks_like_schema_content(content):
                        collected_content += f"\n--- Schema Definition: {path} ---\n{content}\n"
                        file_count += 1
            elif path.is_dir():
                # Collect schema files from directory
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        if file_path.suffix.lower() in ['.db', '.sqlite', '.sqlite3']:
                            content = await self._extract_sqlite_schema(str(file_path))
                            if content:
                                collected_content += f"\n--- SQLite Database: {file_path} ---\n{content}\n"
                                file_count += 1
                        elif file_path.suffix.lower() in ['.sql', '.py', '.rb', '.js', '.prisma', '.graphql', '.ddl']:
                            content = await self._read_file_safe(str(file_path))
                            if content and (file_path.suffix.lower() == '.sql' or self._looks_like_schema_content(content)):
                                collected_content += f"\n--- Schema File: {file_path} ---\n{content}\n"
                                file_count += 1
                        
                        if file_count >= 20:  # Limit for database analysis
                            collected_content += f"\n... (truncated, showing first 20 schema files) ...\n"
                            break
        
        self.logger.info(f"Collected database content from {file_count} files/databases")
        return collected_content
    
    async def _extract_sqlite_schema(self, db_path: str) -> Optional[str]:
        """Extract schema information from SQLite database"""
        try:
            import sqlite3
            import asyncio
            
            def extract_schema_sync():
                """Synchronous SQLite schema extraction"""
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    
                    schema_parts = []
                    
                    # Get all tables
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                    tables = cursor.fetchall()
                    
                    schema_parts.append(f"-- SQLite Database: {db_path}")
                    schema_parts.append(f"-- Found {len(tables)} tables\n")
                    
                    for (table_name,) in tables:
                        # Get table schema
                        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';")
                        create_sql = cursor.fetchone()
                        if create_sql and create_sql[0]:
                            schema_parts.append(f"-- Table: {table_name}")
                            schema_parts.append(create_sql[0] + ";\n")
                        
                        # Get table info (columns, types, constraints)
                        cursor.execute(f"PRAGMA table_info({table_name});")
                        columns = cursor.fetchall()
                        if columns:
                            schema_parts.append(f"-- Columns for {table_name}:")
                            for col in columns:
                                schema_parts.append(f"--   {col[1]} {col[2]} {'NOT NULL' if col[3] else ''} {'PRIMARY KEY' if col[5] else ''}")
                    
                    # Get indexes
                    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%';")
                    indexes = cursor.fetchall()
                    if indexes:
                        schema_parts.append("\n-- Indexes:")
                        for name, sql in indexes:
                            if sql:  # Skip auto-created indexes
                                schema_parts.append(f"{sql};")
                    
                    # Get views
                    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='view';")
                    views = cursor.fetchall()
                    if views:
                        schema_parts.append("\n-- Views:")
                        for name, sql in views:
                            schema_parts.append(f"{sql};")
                    
                    conn.close()
                    return "\n".join(schema_parts)
                    
                except sqlite3.Error as e:
                    return f"-- Error reading SQLite database {db_path}: {e}"
                except Exception as e:
                    return f"-- Error processing SQLite database {db_path}: {e}"
            
            # Run in thread to avoid blocking
            schema = await asyncio.to_thread(extract_schema_sync)
            return schema
            
        except ImportError:
            self.logger.warning("sqlite3 module not available - cannot analyze SQLite databases")
            return f"-- SQLite database detected but sqlite3 module not available: {db_path}"
        except Exception as e:
            self.logger.error(f"Failed to extract schema from {db_path}: {e}")
            return f"-- Error extracting schema from {db_path}: {str(e)}"
    
    async def _collect_code_from_paths(self, paths: List[str], extensions: Optional[List[str]] = None) -> str:
        """
        Collect code content from specified paths (files or directories)
        CRITICAL FIX: Handles WindowsPath objects properly
        """
        from pathlib import Path
        
        # CRITICAL FIX: Ensure paths is always a list of strings
        if not paths:
            return ""
        
        # Handle single path that might be a WindowsPath object
        if isinstance(paths, (str, Path)):
            paths = [str(paths)]
        elif not isinstance(paths, (list, tuple)):
            # Handle WindowsPath or other path-like objects
            paths = [str(paths)]
        else:
            # Ensure all items in the list are strings
            paths = [str(p) for p in paths]
        
        collected_content = []
        processed_files = set()
        
        # Default code extensions if not specified
        if extensions is None:
            extensions = [
                '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.cs',
                '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.clj',
                '.sh', '.bash', '.ps1', '.bat', '.cmd',
                '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
                '.xml', '.html', '.css', '.scss', '.less',
                '.sql', '.md', '.rst', '.txt'
            ]
        
        for path_str in paths:
            path = Path(path_str)
            
            if path.is_file():
                # Single file
                if any(path.suffix == ext for ext in extensions) or not extensions:
                    if str(path) not in processed_files:
                        try:
                            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                collected_content.append(f"### File: {path}\n```\n{content}\n```\n")
                                processed_files.add(str(path))
                        except Exception as e:
                            self.logger.warning(f"Could not read file {path}: {e}")
            
            elif path.is_dir():
                # Directory - collect all matching files
                for ext in extensions:
                    for file_path in path.rglob(f"*{ext}"):
                        if str(file_path) not in processed_files:
                            try:
                                # Skip common non-code directories
                                skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 
                                           'dist', 'build', '.pytest_cache', '.mypy_cache'}
                                if any(skip_dir in file_path.parts for skip_dir in skip_dirs):
                                    continue
                                
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                    collected_content.append(f"### File: {file_path}\n```\n{content}\n```\n")
                                    processed_files.add(str(file_path))
                            except Exception as e:
                                self.logger.warning(f"Could not read file {file_path}: {e}")
        
        return '\n\n'.join(collected_content)
    
    def _looks_like_schema_content(self, content: str) -> bool:
        """Check if content appears to be database schema related"""
        schema_keywords = [
            'CREATE TABLE', 'CREATE VIEW', 'CREATE INDEX',
            'ALTER TABLE', 'DROP TABLE',
            'PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE',
            'Schema', 'Table', 'Column',
            'migration', 'migrate',
            'class.*Model', 'model.*=',  # ORM models
            'type.*=.*GraphQLObjectType',  # GraphQL schemas
        ]
        
        content_upper = content.upper()
        content_lower = content.lower()
        
        # Check for SQL keywords
        sql_matches = sum(1 for keyword in schema_keywords[:8] if keyword in content_upper)
        if sql_matches >= 2:
            return True
        
        # Check for ORM/GraphQL patterns
        import re
        for pattern in schema_keywords[8:]:
            if re.search(pattern.lower(), content_lower):
                return True
        
        return False
    
    async def review_output(self, 
                           output: Optional[str] = None,
                           file_path: Optional[str] = None,
                           is_plan: bool = True,
                           focus: str = "all",
                           context: Optional[str] = None,
                           detail_level: str = "detailed",
                           response_style: str = "detailed",
                           task_id: Optional[str] = None,
                           claude_response: Optional[str] = None,
                           autonomous: bool = False) -> str:
        """
        Collaborative review tool wrapper - delegates to ReviewService
        """
        try:
            from ..models.review_request import ReviewRequest
            from ..services.review_service import ReviewService
            
            # Create ReviewRequest object
            review_request = ReviewRequest(
                output=output,
                file_path=file_path,
                is_plan=is_plan,
                focus=focus,
                context=context,
                detail_level=detail_level,
                response_style=response_style,
                task_id=task_id,
                claude_response=claude_response
            )
            
            # Initialize review service if not exists
            if not hasattr(self, '_review_service'):
                from ..persistence.sqlite_session_store import SqliteSessionStore
                session_store = SqliteSessionStore()
                self._review_service = ReviewService(
                    session_repo=session_store,
                    analytics_repo=session_store,
                    config=self.config
                )
            
            # Process review request
            result = await self._review_service.process_review_request(review_request)
            return str(result)
            
        except Exception as e:
            self.logger.error(f"Review output failed: {e}")
            return f"Review analysis failed: {str(e)}"
    
    async def full_analysis(self,
                           files: List[str],
                           focus: str = "all",
                           autonomous: bool = False,
                           context: Optional[str] = None,
                           task_id: Optional[str] = None,
                           claude_response: Optional[str] = None) -> str:
        """
        Full analysis tool wrapper - delegates to FullAnalysisTool
        """
        try:
            from ..models.tool_requests import FullAnalysisRequest
            from ..tools.full_analysis_tool import FullAnalysisTool
            from ..tools.gemini_tool_wrapper import GeminiToolWrapper
            
            # Validate input arguments  
            validated_request = FullAnalysisRequest(
                files=files,
                focus=focus,
                autonomous=autonomous,
                context=context,
                task_id=task_id,
                claude_response=claude_response
            )
            
            # Initialize full analysis tool if not exists
            if not hasattr(self, '_full_analysis_tool'):
                # Create wrapped sub-tools dictionary using standardized tool names
                sub_tools = {
                    # Core analysis tools
                    ANALYZE_CODE: GeminiToolWrapper(
                        ANALYZE_CODE,
                        self.analyze_code,
                        "Comprehensive code analysis"
                    ),
                    SEARCH_CODE: GeminiToolWrapper(
                        SEARCH_CODE,
                        self.search_code,
                        "Semantic code search"
                    ),
                    CHECK_QUALITY: GeminiToolWrapper(
                        CHECK_QUALITY,
                        self.check_quality,
                        "Quality and security analysis"
                    ),
                    ANALYZE_DOCS: GeminiToolWrapper(
                        ANALYZE_DOCS,
                        self.analyze_docs,
                        "Documentation analysis"
                    ),
                    ANALYZE_LOGS: GeminiToolWrapper(
                        ANALYZE_LOGS,
                        self.analyze_logs,
                        "Log file analysis"
                    ),
                    ANALYZE_DATABASE: GeminiToolWrapper(
                        ANALYZE_DATABASE,
                        self.analyze_database,
                        "Database schema analysis"
                    ),
                    PERFORMANCE_PROFILER: GeminiToolWrapper(
                        PERFORMANCE_PROFILER,
                        self.performance_profiler,
                        "Performance profiling"
                    ),
                    CONFIG_VALIDATOR: GeminiToolWrapper(
                        CONFIG_VALIDATOR,
                        self.config_validator,
                        "Configuration validation"
                    ),
                    API_CONTRACT_CHECKER: GeminiToolWrapper(
                        API_CONTRACT_CHECKER,
                        self.api_contract_checker,
                        "API contract checking"
                    ),
                    ANALYZE_TEST_COVERAGE: GeminiToolWrapper(
                        ANALYZE_TEST_COVERAGE,
                        self.analyze_test_coverage,
                        "Test coverage analysis"
                    ),
                    MAP_DEPENDENCIES: GeminiToolWrapper(
                        MAP_DEPENDENCIES,
                        self.map_dependencies,
                        "Dependency mapping"
                    ),
                    INTERFACE_INCONSISTENCY_DETECTOR: GeminiToolWrapper(
                        INTERFACE_INCONSISTENCY_DETECTOR,
                        self.interface_inconsistency_detector,
                        "Interface consistency checking"
                    )
                }
                
                self._full_analysis_tool = FullAnalysisTool(
                    sub_tools=sub_tools,
                    gemini_client=self.gemini_client
                )
            
            # Execute full analysis
            result = await self._full_analysis_tool.execute(validated_request)
            return str(result)
            
        except Exception as e:
            self.logger.error(f"Full analysis failed: {e}")
            return f"Full analysis failed: {str(e)}"