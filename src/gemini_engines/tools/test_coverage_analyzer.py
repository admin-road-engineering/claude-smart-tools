"""
Test Coverage Analyzer - Phase 2 Enhanced Tool Suite
AST-based test gap identification with AI-guided testing strategy
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass

from .base_tool import FileAnalysisTool, ToolResult
from .ai_interpreter import TestCoverageAIInterpreter
from ..integration.file_freshness_decorator import with_file_freshness_check


@dataclass
class UncoveredFunction:
    """Represents an uncovered function needing tests"""
    file: str
    function: str
    line: int
    complexity: str  # "low", "medium", "high"
    class_name: Optional[str] = None
    docstring: Optional[str] = None


@dataclass
class TestQualityIssue:
    """Represents a test quality issue"""
    test_file: str
    test_function: str
    issue_type: str  # "no_assertions", "empty_test", "no_docstring"
    line: int
    description: str


@dataclass
class CoverageSummary:
    """Overall coverage summary"""
    total_functions: int
    covered_functions: int
    coverage_percentage: float
    total_classes: int
    covered_classes: int
    priority_gaps: int


class TestCoverageAnalyzer(FileAnalysisTool):
    """
    Analyzes Python codebases for test coverage gaps using AST parsing
    Follows the 4-stage Tool-as-a-Service pattern with File Freshness Guardian integration
    """
    
    def __init__(self, ai_interpreter: Optional[TestCoverageAIInterpreter] = None):
        """
        Initialize Test Coverage Analyzer
        
        Args:
            ai_interpreter: AI interpreter for generating insights (defaults to mock)
        """
        super().__init__()
        self.ai_interpreter = ai_interpreter or TestCoverageAIInterpreter()
        
        # Test mapping patterns
        self.test_patterns = [
            r"test_.*\.py$",
            r".*_test\.py$",
            r".*_tests\.py$"
        ]
        
        # Complexity scoring weights
        self.complexity_weights = {
            "lines": 0.3,
            "cyclomatic": 0.4,
            "parameters": 0.2,
            "nested_depth": 0.1
        }
    
    @with_file_freshness_check
    async def analyze(self, source_paths: List[str], test_paths: Optional[List[str]] = None, **kwargs) -> str:
        """
        Public-facing method for test coverage analysis
        Decorator injects verified_files into kwargs
        
        Args:
            source_paths: List of source code file/directory paths
            test_paths: Optional list of test file/directory paths
            **kwargs: Contains verified_files from decorator
            
        Returns:
            JSON string with analysis results and AI insights
        """
        # Extract verified files from decorator
        verified_data = kwargs.get('verified_files', {})
        verified_sources = verified_data.get('source_paths', [])
        verified_tests = verified_data.get('test_paths', test_paths or [])
        
        # Core analysis
        core_results = self._core_utility(verified_sources, verified_tests)
        
        # AI interpretation
        context = {
            "source_count": len(verified_sources),
            "test_count": len(verified_tests),
            "analysis_type": "test_coverage"
        }
        ai_insights = await self.ai_interpreter.interpret(core_results, context)
        
        # Format final results
        result = ToolResult(
            tool_name="TestCoverageAnalyzer",
            status="success",
            data={**core_results, **ai_insights},
            metadata={
                "source_files_analyzed": len(verified_sources),
                "test_files_analyzed": len(verified_tests),
                "parsing_errors": len(core_results.get("parsing_errors", []))
            }
        )
        
        return result.to_json()
    
    def _core_utility(self, source_files: List[str], test_files: List[str]) -> Dict[str, Any]:
        """
        Core AST-based coverage gap detection (Stage 1)
        Pure analysis logic without I/O or AI dependencies
        
        Args:
            source_files: Verified source file paths
            test_files: Verified test file paths
            
        Returns:
            Structured analysis results
        """
        # Initialize results structure
        results = {
            "source_to_test_mapping": {},
            "uncovered_functions": [],
            "uncovered_classes": [],
            "test_quality_issues": [],
            "parsing_errors": [],
            "coverage_summary": {}
        }
        
        # Parse source files
        source_analysis = self._analyze_source_files(source_files)
        results["parsing_errors"].extend(source_analysis["errors"])
        
        # Parse test files
        test_analysis = self._analyze_test_files(test_files)
        results["parsing_errors"].extend(test_analysis["errors"])
        
        # Create source-to-test mapping
        results["source_to_test_mapping"] = self._create_source_test_mapping(
            source_analysis["modules"], test_analysis["modules"]
        )
        
        # Find coverage gaps
        coverage_gaps = self._find_coverage_gaps(
            source_analysis["modules"], test_analysis["modules"]
        )
        results["uncovered_functions"] = coverage_gaps["functions"]
        results["uncovered_classes"] = coverage_gaps["classes"]
        
        # Analyze test quality
        results["test_quality_issues"] = self._analyze_test_quality(test_analysis["modules"])
        
        # Generate coverage summary
        results["coverage_summary"] = self._generate_coverage_summary(
            source_analysis["modules"], coverage_gaps
        )
        
        return results
    
    def _analyze_source_files(self, source_files: List[str]) -> Dict[str, Any]:
        """Parse and analyze source files using AST"""
        modules = {}
        errors = []
        
        for file_path in source_files:
            if not self._is_python_file(file_path):
                continue
                
            ast_tree, error = self._safe_parse_file(file_path)
            if error:
                errors.append({"file": file_path, "error": error})
                continue
            
            module_info = self._extract_module_info(file_path, ast_tree)
            modules[file_path] = module_info
        
        return {"modules": modules, "errors": errors}
    
    def _analyze_test_files(self, test_files: List[str]) -> Dict[str, Any]:
        """Parse and analyze test files"""
        modules = {}
        errors = []
        
        for file_path in test_files:
            if not self._is_python_file(file_path) or not self._is_test_file(file_path):
                continue
                
            ast_tree, error = self._safe_parse_file(file_path)
            if error:
                errors.append({"file": file_path, "error": error})
                continue
            
            test_info = self._extract_test_info(file_path, ast_tree)
            modules[file_path] = test_info
        
        return {"modules": modules, "errors": errors}
    
    def _safe_parse_file(self, file_path: str) -> Tuple[Optional[ast.AST], Optional[str]]:
        """Parse file with graceful error recovery"""
        try:
            content = self.read_file_safe(file_path)
            if not content.strip():
                return None, "Empty file"
            return ast.parse(content), None
        except SyntaxError as e:
            return None, f"Syntax error: {str(e)}"
        except Exception as e:
            return None, f"Parse error: {str(e)}"
    
    def _extract_module_info(self, file_path: str, ast_tree: ast.AST) -> Dict[str, Any]:
        """Extract functions and classes from source module"""
        info = {
            "functions": [],
            "classes": [],
            "imports": [],
            "file_path": file_path
        }
        
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private methods and test functions
                if not node.name.startswith('_') and not node.name.startswith('test_'):
                    complexity = self._calculate_function_complexity(node)
                    info["functions"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args],
                        "docstring": ast.get_docstring(node),
                        "complexity": complexity,
                        "is_async": isinstance(node, ast.AsyncFunctionDef)
                    })
            
            elif isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and not item.name.startswith('_'):
                        methods.append({
                            "name": item.name,
                            "line": item.lineno,
                            "complexity": self._calculate_function_complexity(item)
                        })
                
                info["classes"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "methods": methods,
                    "docstring": ast.get_docstring(node)
                })
            
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                info["imports"].append(self._extract_import_info(node))
        
        return info
    
    def _extract_test_info(self, file_path: str, ast_tree: ast.AST) -> Dict[str, Any]:
        """Extract test functions from test module"""
        info = {
            "test_functions": [],
            "test_classes": [],
            "imports": [],
            "file_path": file_path
        }
        
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                info["test_functions"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "docstring": ast.get_docstring(node),
                    "has_assertions": self._has_assertions(node),
                    "tested_function": self._infer_tested_function(node.name)
                })
            
            elif isinstance(node, ast.ClassDef) and 'Test' in node.name:
                test_methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                        test_methods.append({
                            "name": item.name,
                            "line": item.lineno,
                            "has_assertions": self._has_assertions(item)
                        })
                
                info["test_classes"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "test_methods": test_methods
                })
        
        return info
    
    def _calculate_function_complexity(self, func_node: ast.FunctionDef) -> str:
        """Calculate function complexity score"""
        # Line count
        line_count = len([n for n in ast.walk(func_node) if hasattr(n, 'lineno')])
        
        # Cyclomatic complexity (simplified)
        complexity_nodes = [ast.If, ast.While, ast.For, ast.Try, ast.With]
        cyclomatic = sum(1 for n in ast.walk(func_node) if type(n) in complexity_nodes)
        
        # Parameter count
        param_count = len(func_node.args.args)
        
        # Nested depth (simplified)
        nested_depth = max(self._calculate_nesting_depth(func_node, 0), 1)
        
        # Weighted score
        score = (
            (line_count / 20) * self.complexity_weights["lines"] +
            (cyclomatic / 5) * self.complexity_weights["cyclomatic"] +
            (param_count / 5) * self.complexity_weights["parameters"] +
            (nested_depth / 3) * self.complexity_weights["nested_depth"]
        )
        
        if score > 0.7:
            return "high"
        elif score > 0.4:
            return "medium"
        else:
            return "low"
    
    def _calculate_nesting_depth(self, node: ast.AST, current_depth: int) -> int:
        """Calculate maximum nesting depth"""
        max_depth = current_depth
        nesting_nodes = [ast.If, ast.While, ast.For, ast.Try, ast.With, ast.FunctionDef, ast.ClassDef]
        
        for child in ast.iter_child_nodes(node):
            if type(child) in nesting_nodes:
                child_depth = self._calculate_nesting_depth(child, current_depth + 1)
                max_depth = max(max_depth, child_depth)
        
        return max_depth
    
    def _has_assertions(self, func_node: ast.FunctionDef) -> bool:
        """Check if function contains assertion statements"""
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assert):
                return True
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr.startswith('assert'):
                    return True
                if isinstance(func, ast.Name) and func.id.startswith('assert'):
                    return True
        return False
    
    def _infer_tested_function(self, test_name: str) -> Optional[str]:
        """Infer source function name from test name"""
        if test_name.startswith('test_'):
            return test_name[5:]  # Remove 'test_' prefix
        return None
    
    def _extract_import_info(self, node) -> Dict[str, Any]:
        """Extract import information"""
        if isinstance(node, ast.Import):
            return {"type": "import", "names": [alias.name for alias in node.names]}
        elif isinstance(node, ast.ImportFrom):
            return {
                "type": "from_import",
                "module": node.module,
                "names": [alias.name for alias in node.names] if node.names else ["*"]
            }
    
    def _create_source_test_mapping(self, source_modules: Dict, test_modules: Dict) -> Dict[str, List[str]]:
        """Create mapping between source files and their test files"""
        mapping = {}
        
        for source_path in source_modules:
            source_name = Path(source_path).stem
            mapped_tests = []
            
            # Look for test files that might test this source
            for test_path in test_modules:
                test_name = Path(test_path).stem
                
                # Convention-based matching
                if (f"test_{source_name}" in test_name or 
                    f"{source_name}_test" in test_name or
                    test_name == f"test_{source_name}"):
                    mapped_tests.append(test_path)
                    continue
                
                # Directory-based matching (test mirrors source structure)
                source_dir = str(Path(source_path).parent)
                test_dir = str(Path(test_path).parent)
                if "test" in test_dir.lower() and source_name in test_name:
                    mapped_tests.append(test_path)
            
            mapping[source_path] = mapped_tests
        
        return mapping
    
    def _find_coverage_gaps(self, source_modules: Dict, test_modules: Dict) -> Dict[str, List]:
        """Find functions and classes without test coverage"""
        gaps = {"functions": [], "classes": []}
        
        # Get all tested function names
        tested_functions = set()
        for test_module in test_modules.values():
            for test_func in test_module["test_functions"]:
                if test_func["tested_function"]:
                    tested_functions.add(test_func["tested_function"])
        
        # Find uncovered functions
        for source_path, module_info in source_modules.items():
            for func in module_info["functions"]:
                if func["name"] not in tested_functions:
                    gaps["functions"].append(UncoveredFunction(
                        file=source_path,
                        function=func["name"],
                        line=func["line"],
                        complexity=func["complexity"],
                        docstring=func["docstring"]
                    ).__dict__)
            
            # Find uncovered classes (simplified - checks if any methods are tested)
            for cls in module_info["classes"]:
                class_tested = any(
                    method["name"] in tested_functions 
                    for method in cls["methods"]
                )
                if not class_tested and cls["methods"]:  # Only report classes with methods
                    gaps["classes"].append({
                        "file": source_path,
                        "class": cls["name"],
                        "line": cls["line"],
                        "methods": [m["name"] for m in cls["methods"]],
                        "docstring": cls["docstring"]
                    })
        
        return gaps
    
    def _analyze_test_quality(self, test_modules: Dict) -> List[Dict[str, Any]]:
        """Analyze quality of existing tests"""
        issues = []
        
        for test_path, test_info in test_modules.items():
            # Check test functions
            for test_func in test_info["test_functions"]:
                if not test_func["has_assertions"]:
                    issues.append(TestQualityIssue(
                        test_file=test_path,
                        test_function=test_func["name"],
                        issue_type="no_assertions",
                        line=test_func["line"],
                        description="Test function has no assertion statements"
                    ).__dict__)
                
                if not test_func["docstring"]:
                    issues.append(TestQualityIssue(
                        test_file=test_path,
                        test_function=test_func["name"],
                        issue_type="no_docstring",
                        line=test_func["line"],
                        description="Test function lacks descriptive docstring"
                    ).__dict__)
        
        return issues
    
    def _generate_coverage_summary(self, source_modules: Dict, coverage_gaps: Dict) -> Dict[str, Any]:
        """Generate overall coverage summary"""
        total_functions = sum(len(module["functions"]) for module in source_modules.values())
        uncovered_functions = len(coverage_gaps["functions"])
        covered_functions = total_functions - uncovered_functions
        
        total_classes = sum(len(module["classes"]) for module in source_modules.values())
        uncovered_classes = len(coverage_gaps["classes"])
        
        # Count high-priority gaps (high complexity functions)
        priority_gaps = len([
            func for func in coverage_gaps["functions"] 
            if func.get("complexity") == "high"
        ])
        
        coverage_percentage = (covered_functions / total_functions * 100) if total_functions > 0 else 0
        
        return CoverageSummary(
            total_functions=total_functions,
            covered_functions=covered_functions,
            coverage_percentage=round(coverage_percentage, 2),
            total_classes=total_classes,
            covered_classes=total_classes - uncovered_classes,
            priority_gaps=priority_gaps
        ).__dict__
    
    def _is_python_file(self, file_path: str) -> bool:
        """Check if file is a Python file"""
        return file_path.endswith('.py')
    
    def _is_test_file(self, file_path: str) -> bool:
        """Check if file is a test file based on patterns"""
        filename = os.path.basename(file_path)
        return any(re.match(pattern, filename) for pattern in self.test_patterns)
    
    async def _get_ai_interpretation(self, core_results: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
        """Get AI interpretation (Stage 3) - delegated to AI interpreter"""
        ai_insights = await self.ai_interpreter.interpret(core_results, context)
        return ai_insights.get("ai_insights", ["No insights generated"])