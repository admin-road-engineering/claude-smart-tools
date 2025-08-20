"""
Understand Tool - Deep Comprehension Smart Tool
Helps Claude quickly grasp unfamiliar codebases, architectures, patterns
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Union

# Handle imports for both module and script execution
try:
    from .base_smart_tool import BaseSmartTool, SmartToolResult
    from .executive_synthesizer import ExecutiveSynthesizer
except ImportError:
    # Add current directory to path for script execution
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from base_smart_tool import BaseSmartTool, SmartToolResult
    from executive_synthesizer import ExecutiveSynthesizer

import logging
logger = logging.getLogger(__name__)


class UnderstandTool(BaseSmartTool):
    """
    Smart tool for understanding codebases, architectures, and patterns
    Routes to: analyze_code + search_code + analyze_docs
    """
    
    def __init__(self, engines: Dict[str, Any]):
        super().__init__(engines)
        self.executive_synthesizer = ExecutiveSynthesizer(engines)
    
    # Common documentation file patterns
    DOC_EXTENSIONS = ('.md', '.rst', '.txt', '.markdown', '.adoc', '.org')
    DOC_KEYWORDS = ('readme', 'changelog', 'contributing', 'license', 'install',
                   'history', 'upgrade', 'security', 'authors', 'credits',
                   'notice', 'copyright', 'todo', 'roadmap', 'faq')
    
    def _find_documentation_files(self, paths: List[Union[str, Path]]) -> List[str]:
        """
        Finds documentation files from a list of paths (files or directories).
        Handles both individual files and directory traversal with depth limits.
        """
        found_files = set()
        MAX_DEPTH = 3  # Limit directory traversal depth
        MAX_FILES = 50  # Limit total files to avoid overwhelming the tool
        EXCLUDE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 
                       'dist', 'build', '.pytest_cache', '.mypy_cache'}
        
        def should_exclude_dir(dir_path: Path) -> bool:
            """Check if directory should be excluded"""
            return any(part in EXCLUDE_DIRS for part in dir_path.parts)
        
        def search_directory(dir_path: Path, current_depth: int = 0):
            """Search directory with depth limit"""
            if current_depth > MAX_DEPTH or len(found_files) >= MAX_FILES:
                return
            
            try:
                for item in dir_path.iterdir():
                    if len(found_files) >= MAX_FILES:
                        break
                        
                    if item.is_dir():
                        if not should_exclude_dir(item):
                            # Check if this is a docs directory
                            if item.name.lower() == 'docs':
                                # Search docs directories more thoroughly
                                search_directory(item, current_depth + 1)
                            elif current_depth < MAX_DEPTH:
                                # Continue searching other directories
                                search_directory(item, current_depth + 1)
                    elif item.is_file():
                        lower_name = item.name.lower()
                        # Check if it's a doc file by extension or name
                        if (lower_name.endswith(self.DOC_EXTENSIONS) or 
                            any(keyword in lower_name for keyword in self.DOC_KEYWORDS)):
                            found_files.add(str(item))
            except (PermissionError, OSError):
                # Skip directories we can't access
                pass
        
        for path in paths:
            if len(found_files) >= MAX_FILES:
                break
                
            try:
                p = Path(path)
                
                if p.is_dir():
                    if not should_exclude_dir(p):
                        search_directory(p, 0)
                elif p.is_file():
                    lower_name = p.name.lower()
                    # Check if it's a doc file by extension or name
                    if (lower_name.endswith(self.DOC_EXTENSIONS) or 
                        any(keyword in lower_name for keyword in self.DOC_KEYWORDS)):
                        found_files.add(str(p))
            except Exception:
                # Skip paths that cause errors
                continue
        
        return sorted(list(found_files))[:MAX_FILES]  # Ensure we don't exceed limit
    
    async def execute(self, files: List[str], question: str = None, **kwargs) -> SmartToolResult:
        """
        Execute understanding analysis with intelligent routing
        """
        # CRITICAL FIX: Ensure files is always a list of strings
        # Handle case where a single WindowsPath object might be passed
        from pathlib import Path
        if isinstance(files, (str, Path)) or hasattr(files, '__fspath__'):
            files = [str(files)]
            logger.debug(f"Converted single path to list: {files}")
        elif isinstance(files, (list, tuple)):
            files = [str(f) for f in files]
            logger.debug(f"Normalized {len(files)} file paths to strings")
        else:
            # Fallback for unexpected types
            files = [str(files)]
            logger.warning(f"Unexpected files type {type(files)}, converted to string list")
        
        routing_strategy = self.get_routing_strategy(files=files, question=question, **kwargs)
        engines_used = []
        results = {}
        
        try:
            import asyncio
            
            # Read project context early for all engines to use
            project_context = await self._get_project_context(files)
            if project_context and project_context.get('claude_md_content'):
                logger.info(f"Using project-specific CLAUDE.md for understanding ({len(project_context['claude_md_content'])} chars)")
            
            # Pre-compute documentation files for parallel execution
            doc_files = self._find_documentation_files(files) if 'analyze_docs' in routing_strategy['engines'] else []
            
            # Group independent tasks for parallel execution
            parallel_tasks = []
            
            # Phase 1: Core architectural analysis (always included)
            if 'analyze_code' in routing_strategy['engines']:
                parallel_tasks.append(self._run_architectural_analysis(files, question))
            
            # Phase 2: Pattern search (if question provided)
            if question and 'search_code' in routing_strategy['engines']:
                parallel_tasks.append(self._run_pattern_search(files, question))
            
            # Phase 3: Documentation analysis (if docs found)
            if 'analyze_docs' in routing_strategy['engines'] and doc_files:
                parallel_tasks.append(self._run_documentation_analysis(doc_files, question))
            
            # Phase 4: Dependency analysis (for multi-file projects)
            if 'map_dependencies' in routing_strategy['engines']:
                parallel_tasks.append(self._run_dependency_analysis(files))
            
            # Execute all analysis phases in parallel
            if parallel_tasks:
                parallel_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
                
                # Process results and extract engine usage
                for result in parallel_results:
                    if isinstance(result, Exception):
                        logger.error(f"Parallel understanding task failed: {result}")
                    elif isinstance(result, dict):
                        for phase_name, phase_data in result.items():
                            results[phase_name] = phase_data['result']
                            if 'engine' in phase_data:
                                engines_used.append(phase_data['engine'])
            
            # Synthesize results
            synthesized_result = self._synthesize_understanding(results, question)
            
            # Apply executive synthesis for better consolidated response
            if self.executive_synthesizer.should_synthesize(self.tool_name):
                original_request = {
                    'files': files,
                    'question': question,
                    **kwargs
                }
                synthesized_result = await self.executive_synthesizer.synthesize(
                    tool_name=self.tool_name,
                    raw_results=synthesized_result,
                    original_request=original_request
                )
            
            return SmartToolResult(
                tool_name=self.tool_name,
                success=True,
                result=synthesized_result,
                engines_used=engines_used,
                routing_decision=routing_strategy['reasoning'],
                metadata={
                    'files_analyzed': len(files),
                    'question': question,
                    'phases_completed': len(results),
                    'performance_mode': 'parallel',
                    'parallel_tasks': len(parallel_tasks) if 'parallel_tasks' in locals() else 0
                }
            )
            
        except Exception as e:
            return SmartToolResult(
                tool_name=self.tool_name,
                success=False,
                result=f"Understanding analysis failed: {str(e)}",
                engines_used=engines_used,
                routing_decision=routing_strategy.get('reasoning', 'Error during execution'),
                metadata={'error': str(e)}
            )
    
    def get_routing_strategy(self, files: List[str] = None, question: str = None, **kwargs) -> Dict[str, Any]:
        """
        Determine which engines to use for understanding
        """
        engines = ['analyze_code']  # Always start with code analysis
        reasoning_parts = ["Starting with architectural analysis"]
        
        # Add search if we have a specific question
        if question and len(question.strip()) > 0:
            engines.append('search_code')
            reasoning_parts.append("Adding pattern search for specific question")
        
        # Add docs if documentation files are present
        if files:
            doc_files = self._find_documentation_files(files)
            if doc_files:
                engines.append('analyze_docs')
                reasoning_parts.append(f"Including documentation analysis ({len(doc_files)} docs found)")
        
        # Add dependency analysis for multi-file projects or architectural questions
        if files and (len(files) > 1 or (question and any(keyword in question.lower() for keyword in 
                    ['architecture', 'dependency', 'dependencies', 'structure', 'coupling', 'component']))):
            engines.append('map_dependencies')
            reasoning_parts.append("Adding dependency analysis for architectural understanding")
        
        # Prioritize based on file count
        if files and len(files) > 20:
            reasoning_parts.append("Large codebase - focusing on high-level architecture first")
        
        return {
            'engines': engines,
            'reasoning': '; '.join(reasoning_parts),
            'strategy': 'sequential_synthesis'
        }
    
    def _synthesize_understanding(self, results: Dict[str, Any], question: str = None) -> str:
        """
        Synthesize results from multiple engines into coherent understanding
        """
        synthesis = ["# 🎯 Code Understanding Analysis\n"]
        
        if question:
            synthesis.append(f"**Question**: {question}\n")
        
        # Architecture section
        if 'architecture' in results:
            synthesis.append("## 🏗️ Architecture Overview")
            synthesis.append(str(results['architecture']))
            synthesis.append("")
        
        # Pattern analysis section
        if 'patterns' in results:
            synthesis.append("## 🔍 Pattern Analysis")
            synthesis.append(str(results['patterns']))
            synthesis.append("")
        
        # Documentation insights
        if 'documentation' in results:
            synthesis.append("## 📚 Documentation Insights") 
            synthesis.append(str(results['documentation']))
            synthesis.append("")
        
        # Dependency analysis
        if 'dependencies' in results:
            synthesis.append("## 🔗 Dependency Analysis")
            synthesis.append(str(results['dependencies']))
            synthesis.append("")
        
        # Summary and key takeaways
        synthesis.append("## 💡 Key Understanding Points")
        synthesis.append(self._extract_key_points(results))
        
        return '\n'.join(synthesis)
    
    def _extract_key_points(self, results: Dict[str, Any]) -> str:
        """
        Extract key understanding points from analysis results
        """
        points = []
        
        # This is a simplified extraction - in production, you'd want
        # more sophisticated parsing of the Gemini analysis results
        if 'architecture' in results:
            points.append("- **Architecture**: System structure and component relationships analyzed")
        
        if 'patterns' in results:
            points.append("- **Patterns**: Specific code patterns and implementations identified")
        
        if 'documentation' in results:
            points.append("- **Documentation**: Context and design decisions from docs reviewed")
        
        if 'dependencies' in results:
            points.append("- **Dependencies**: Component relationships, coupling analysis, and dependency graph insights")
        
        if not points:
            points.append("- Analysis completed - see detailed results above")
        
        return '\n'.join(points)
    
    # Parallel execution helper methods
    async def _run_architectural_analysis(self, files: List[str], question: str = None) -> Dict[str, Any]:
        """Run architectural analysis in parallel"""
        try:
            result = await self.execute_engine(
                'analyze_code',
                paths=files,
                analysis_type='architecture',
                question=question,
                verbose=True
            )
            return {'architecture': {'result': result, 'engine': 'analyze_code'}}
        except Exception as e:
            return {'architecture': {'result': f"Architectural analysis failed: {str(e)}", 'engine': 'analyze_code'}}
    
    async def _run_pattern_search(self, files: List[str], question: str) -> Dict[str, Any]:
        """Run pattern search in parallel"""
        try:
            result = await self.execute_engine(
                'search_code',
                query=question,
                paths=files,
                context_question=f"How does this relate to: {question}",
                output_format='text'
            )
            return {'patterns': {'result': result, 'engine': 'search_code'}}
        except Exception as e:
            return {'patterns': {'result': f"Pattern search failed: {str(e)}", 'engine': 'search_code'}}
    
    async def _run_documentation_analysis(self, doc_files: List[str], question: str = None) -> Dict[str, Any]:
        """Run documentation analysis in parallel"""
        try:
            result = await self.execute_engine(
                'analyze_docs',
                sources=doc_files,
                synthesis_type='summary',
                questions=[question] if question else None
            )
            return {'documentation': {'result': result, 'engine': 'analyze_docs'}}
        except Exception as e:
            return {'documentation': {'result': f"Documentation analysis failed: {str(e)}", 'engine': 'analyze_docs'}}
    
    async def _run_dependency_analysis(self, files: List[str]) -> Dict[str, Any]:
        """Run dependency analysis in parallel"""
        try:
            result = await self.execute_engine(
                'map_dependencies',
                project_paths=files,
                analysis_depth='transitive'
            )
            return {'dependencies': {'result': result, 'engine': 'map_dependencies'}}
        except Exception as e:
            return {'dependencies': {'result': f"Dependency analysis failed: {str(e)}", 'engine': 'map_dependencies'}}