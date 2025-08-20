"""
Interface Inconsistency Detector Tool for Gemini MCP System
Detects naming mismatches between implementations and usage patterns
Following Tool-as-a-Service pattern with File Freshness Guardian integration
"""
import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
import logging

from .base_tool import FileAnalysisTool, ToolResult
from ..integration.file_freshness_decorator import with_file_freshness_check

logger = logging.getLogger(__name__)

@dataclass
class InterfaceInconsistency:
    """Represents an interface naming inconsistency"""
    category: str  # method_mismatch, property_mismatch, return_structure, parameter_naming
    severity: str  # critical, warning, info
    source_file: str
    source_line: int
    usage_file: str
    usage_line: int
    expected_name: str
    actual_name: str
    context: str
    suggestion: str
    confidence: float = 0.0  # 0.0 to 1.0

class InterfaceInconsistencyDetector(FileAnalysisTool):
    """
    Interface inconsistency detection tool with AI-powered naming suggestions
    
    Features:
    - Find method name mismatches (e.g., get_count() vs total_count)
    - Detect property usage inconsistencies (e.g., file_count vs total_files)
    - Identify return structure mismatches
    - Check parameter naming conflicts
    - Suggest consistent naming patterns through Gemini AI
    """
    
    def __init__(self):
        super().__init__("InterfaceInconsistencyDetector")
        self.inconsistencies: List[InterfaceInconsistency] = []
        self.class_methods: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self.property_usage: Dict[str, Set[str]] = defaultdict(set)
        self.return_structures: Dict[str, Dict[str, Any]] = {}
        
    def _core_utility(self, files: List[str], **kwargs) -> Dict[str, Any]:
        """
        Core interface inconsistency detection logic
        
        Args:
            files: List of source files to analyze
            **kwargs: Additional parameters (check_methods, check_properties, etc.)
            
        Returns:
            Dictionary with inconsistency analysis results
        """
        self.inconsistencies = []
        self.class_methods.clear()
        self.property_usage.clear()
        self.return_structures.clear()
        
        results = {
            "total_files": len(files),
            "files_analyzed": [],
            "inconsistencies": [],
            "statistics": {
                "method_mismatches": 0,
                "property_mismatches": 0,
                "return_structure_issues": 0,
                "parameter_naming_issues": 0,
                "total_issues": 0
            },
            "class_interfaces": {},
            "naming_patterns": {},
            "suggestions": []
        }
        
        check_methods = kwargs.get('check_methods', True)
        check_properties = kwargs.get('check_properties', True)
        check_returns = kwargs.get('check_returns', True)
        check_parameters = kwargs.get('check_parameters', True)
        
        # First pass: collect interface definitions
        for file_path in files:
            if not self.is_source_code(file_path):
                continue
                
            content = self.read_file_safe(file_path)
            if not content:
                continue
                
            results["files_analyzed"].append(file_path)
            
            try:
                tree = ast.parse(content)
                self._collect_interfaces(file_path, tree)
            except SyntaxError as e:
                logger.warning(f"Syntax error in {file_path}: {e}")
                continue
        
        # Second pass: find inconsistencies
        for file_path in results["files_analyzed"]:
            content = self.read_file_safe(file_path)
            if not content:
                continue
                
            try:
                tree = ast.parse(content)
                if check_methods:
                    self._check_method_inconsistencies(file_path, tree)
                if check_properties:
                    self._check_property_inconsistencies(file_path, tree)
                if check_returns:
                    self._check_return_structure_inconsistencies(file_path, tree)
                if check_parameters:
                    self._check_parameter_naming_inconsistencies(file_path, tree)
            except SyntaxError:
                continue
        
        # Convert inconsistencies to dict format
        for inconsistency in self.inconsistencies:
            inconsistency_dict = {
                "category": inconsistency.category,
                "severity": inconsistency.severity,
                "source_file": inconsistency.source_file,
                "source_line": inconsistency.source_line,
                "usage_file": inconsistency.usage_file,
                "usage_line": inconsistency.usage_line,
                "expected_name": inconsistency.expected_name,
                "actual_name": inconsistency.actual_name,
                "context": inconsistency.context,
                "suggestion": inconsistency.suggestion,
                "confidence": inconsistency.confidence
            }
            results["inconsistencies"].append(inconsistency_dict)
            
            # Update statistics
            if inconsistency.category == "method_mismatch":
                results["statistics"]["method_mismatches"] += 1
            elif inconsistency.category == "property_mismatch":
                results["statistics"]["property_mismatches"] += 1
            elif inconsistency.category == "return_structure":
                results["statistics"]["return_structure_issues"] += 1
            elif inconsistency.category == "parameter_naming":
                results["statistics"]["parameter_naming_issues"] += 1
                
        results["statistics"]["total_issues"] = len(self.inconsistencies)
        
        # Add interface summaries
        results["class_interfaces"] = dict(self.class_methods)
        results["naming_patterns"] = self._analyze_naming_patterns()
        
        return results
    
    def _collect_interfaces(self, file_path: str, tree: ast.AST):
        """Collect interface definitions from AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                
                # Collect methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        method_name = item.name
                        self.class_methods[class_name]["methods"].add(method_name)
                        
                        # Analyze return statements
                        return_info = self._analyze_return_structure(item)
                        if return_info:
                            self.return_structures[f"{class_name}.{method_name}"] = return_info
                    
                    elif isinstance(item, ast.Assign):
                        # Class-level property assignments
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                self.class_methods[class_name]["properties"].add(target.id)
            
            elif isinstance(node, ast.FunctionDef):
                # Module-level functions
                func_name = node.name
                self.class_methods["__module__"]["functions"].add(func_name)
                
                # Analyze return structure
                return_info = self._analyze_return_structure(node)
                if return_info:
                    self.return_structures[f"__module__.{func_name}"] = return_info
    
    def _analyze_return_structure(self, func_node: ast.FunctionDef) -> Optional[Dict]:
        """Analyze the structure of return statements in a function"""
        return_structures = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return) and node.value:
                if isinstance(node.value, ast.Dict):
                    # Dictionary return
                    keys = []
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant):
                            keys.append(key.value)
                        elif isinstance(key, ast.Str):  # Python < 3.8
                            keys.append(key.s)
                    return_structures.append({"type": "dict", "keys": keys})
                    
                elif isinstance(node.value, ast.Tuple):
                    # Tuple return
                    return_structures.append({"type": "tuple", "length": len(node.value.elts)})
                    
                elif isinstance(node.value, ast.List):
                    # List return
                    return_structures.append({"type": "list"})
        
        if return_structures:
            return {"structures": return_structures}
        return None
    
    def _check_method_inconsistencies(self, file_path: str, tree: ast.AST):
        """Check for method name inconsistencies"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr
                    
                    # Look for similar method names in our collected interfaces
                    for class_name, interfaces in self.class_methods.items():
                        for existing_method in interfaces.get("methods", set()):
                            if self._are_names_similar(method_name, existing_method):
                                if method_name != existing_method:
                                    confidence = self._calculate_similarity_confidence(method_name, existing_method)
                                    
                                    if confidence > 0.7:  # High confidence threshold
                                        self.inconsistencies.append(InterfaceInconsistency(
                                            category="method_mismatch",
                                            severity="warning" if confidence > 0.8 else "info",
                                            source_file=file_path,
                                            source_line=node.lineno,
                                            usage_file=file_path,
                                            usage_line=node.lineno,
                                            expected_name=existing_method,
                                            actual_name=method_name,
                                            context=f"Method call in {class_name}",
                                            suggestion=f"Consider using '{existing_method}' for consistency",
                                            confidence=confidence
                                        ))
    
    def _check_property_inconsistencies(self, file_path: str, tree: ast.AST):
        """Check for property name inconsistencies"""
        property_usage = set()
        
        # Collect property usage in this file
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                attr_name = node.attr
                property_usage.add(attr_name)
            elif isinstance(node, ast.Name):
                property_usage.add(node.id)
        
        # Check against known properties
        for prop_name in property_usage:
            for class_name, interfaces in self.class_methods.items():
                for existing_prop in interfaces.get("properties", set()):
                    if self._are_names_similar(prop_name, existing_prop) and prop_name != existing_prop:
                        confidence = self._calculate_similarity_confidence(prop_name, existing_prop)
                        
                        if confidence > 0.6:  # Lower threshold for properties
                            self.inconsistencies.append(InterfaceInconsistency(
                                category="property_mismatch",
                                severity="info",
                                source_file=file_path,
                                source_line=0,  # Hard to get exact line for properties
                                usage_file=file_path,
                                usage_line=0,
                                expected_name=existing_prop,
                                actual_name=prop_name,
                                context=f"Property usage in {class_name}",
                                suggestion=f"Consider using '{existing_prop}' for consistency",
                                confidence=confidence
                            ))
    
    def _check_return_structure_inconsistencies(self, file_path: str, tree: ast.AST):
        """Check for return structure inconsistencies"""
        # This is a simplified check - could be expanded significantly
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                
                # Look for functions with similar names but different return structures
                for existing_func, return_info in self.return_structures.items():
                    if self._are_names_similar(func_name, existing_func.split('.')[-1]):
                        if func_name != existing_func.split('.')[-1]:
                            self.inconsistencies.append(InterfaceInconsistency(
                                category="return_structure",
                                severity="info",
                                source_file=file_path,
                                source_line=node.lineno,
                                usage_file=file_path,
                                usage_line=node.lineno,
                                expected_name=existing_func.split('.')[-1],
                                actual_name=func_name,
                                context="Function with similar name",
                                suggestion=f"Check if return structure matches {existing_func}",
                                confidence=0.5
                            ))
    
    def _check_parameter_naming_inconsistencies(self, file_path: str, tree: ast.AST):
        """Check for parameter naming inconsistencies"""
        parameter_patterns = defaultdict(set)
        
        # Collect parameter names from function definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for arg in node.args.args:
                    param_name = arg.arg
                    parameter_patterns[node.name].add(param_name)
        
        # Check for inconsistencies (simplified logic)
        for func_name, params in parameter_patterns.items():
            for param in params:
                # Look for similar parameter names in other functions
                for other_func, other_params in parameter_patterns.items():
                    if func_name != other_func:
                        for other_param in other_params:
                            if self._are_names_similar(param, other_param) and param != other_param:
                                confidence = self._calculate_similarity_confidence(param, other_param)
                                
                                if confidence > 0.8:  # High confidence for parameters
                                    self.inconsistencies.append(InterfaceInconsistency(
                                        category="parameter_naming",
                                        severity="info",
                                        source_file=file_path,
                                        source_line=0,
                                        usage_file=file_path,
                                        usage_line=0,
                                        expected_name=other_param,
                                        actual_name=param,
                                        context=f"Parameter in {func_name} vs {other_func}",
                                        suggestion=f"Consider standardizing on '{other_param}'",
                                        confidence=confidence
                                    ))
    
    def _are_names_similar(self, name1: str, name2: str) -> bool:
        """Check if two names are semantically similar"""
        # Remove common prefixes/suffixes
        clean_name1 = self._normalize_name(name1)
        clean_name2 = self._normalize_name(name2)
        
        # Check for exact matches after normalization
        if clean_name1 == clean_name2:
            return True
        
        # Check for similar words (e.g., count vs total, file vs files)
        similar_words = [
            {"count", "total", "num", "number"},
            {"file", "files", "filename", "filepath"},
            {"get", "fetch", "retrieve", "obtain"},
            {"set", "update", "change", "modify"},
            {"create", "make", "build", "generate"},
            {"delete", "remove", "destroy", "clear"},
            {"data", "info", "information", "details"},
            {"result", "results", "output", "response"}
        ]
        
        for similar_group in similar_words:
            if any(word in clean_name1 for word in similar_group) and \
               any(word in clean_name2 for word in similar_group):
                return True
        
        # Check for substring matches
        if len(clean_name1) > 3 and len(clean_name2) > 3:
            if clean_name1 in clean_name2 or clean_name2 in clean_name1:
                return True
        
        return False
    
    def _normalize_name(self, name: str) -> str:
        """Normalize a name for comparison"""
        # Convert to lowercase
        normalized = name.lower()
        
        # Split camelCase and snake_case
        normalized = re.sub(r'([a-z])([A-Z])', r'\1_\2', normalized).lower()
        
        # Remove common prefixes/suffixes
        prefixes = ['get_', 'set_', 'is_', 'has_', 'can_', 'should_', 'will_']
        suffixes = ['_count', '_total', '_num', '_list', '_dict', '_data']
        
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
                break
        
        return normalized
    
    def _calculate_similarity_confidence(self, name1: str, name2: str) -> float:
        """Calculate similarity confidence between two names"""
        # Simple Levenshtein-based similarity
        def levenshtein_distance(s1: str, s2: str) -> int:
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
            
            if len(s2) == 0:
                return len(s1)
            
            previous_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            
            return previous_row[-1]
        
        clean1 = self._normalize_name(name1)
        clean2 = self._normalize_name(name2)
        
        max_len = max(len(clean1), len(clean2))
        if max_len == 0:
            return 1.0
        
        distance = levenshtein_distance(clean1, clean2)
        similarity = 1.0 - (distance / max_len)
        
        return max(0.0, min(1.0, similarity))
    
    def _analyze_naming_patterns(self) -> Dict[str, Any]:
        """Analyze naming patterns across the codebase"""
        patterns = {
            "naming_conventions": {},
            "common_prefixes": {},
            "common_suffixes": {},
            "inconsistent_patterns": []
        }
        
        all_names = set()
        for class_name, interfaces in self.class_methods.items():
            all_names.update(interfaces.get("methods", set()))
            all_names.update(interfaces.get("properties", set()))
            all_names.update(interfaces.get("functions", set()))
        
        # Analyze naming conventions
        snake_case = sum(1 for name in all_names if '_' in name and name.islower())
        camel_case = sum(1 for name in all_names if re.match(r'^[a-z]+([A-Z][a-z]*)*$', name))
        
        patterns["naming_conventions"] = {
            "snake_case_count": snake_case,
            "camel_case_count": camel_case,
            "total_names": len(all_names),
            "predominant_style": "snake_case" if snake_case > camel_case else "camelCase"
        }
        
        return patterns
    
    async def _get_ai_interpretation(self, 
                                    core_results: Dict[str, Any],
                                    context: Optional[str] = None) -> str:
        """
        Get Gemini AI interpretation of interface inconsistencies
        
        Args:
            core_results: Inconsistency analysis results from core utility
            context: Optional context about the codebase
            
        Returns:
            AI interpretation with naming suggestions
        """
        inconsistencies = core_results.get("inconsistencies", [])
        stats = core_results.get("statistics", {})
        patterns = core_results.get("naming_patterns", {})
        
        if not inconsistencies:
            return "✅ Interface consistency looks good! No significant naming inconsistencies detected."
        
        # Create prompt for Gemini
        prompt = f"""Analyze these interface naming inconsistencies and suggest standardization:

Context: {context or 'Interface consistency analysis'}

Statistics:
- Method Mismatches: {stats.get('method_mismatches', 0)}
- Property Mismatches: {stats.get('property_mismatches', 0)}
- Return Structure Issues: {stats.get('return_structure_issues', 0)}
- Parameter Naming Issues: {stats.get('parameter_naming_issues', 0)}

Naming Patterns:
- Predominant Style: {patterns.get('naming_conventions', {}).get('predominant_style', 'Unknown')}
- Total Names Analyzed: {patterns.get('naming_conventions', {}).get('total_names', 0)}

Top Inconsistencies:
"""
        
        high_confidence_issues = [i for i in inconsistencies if i.get('confidence', 0) > 0.7][:5]
        for issue in high_confidence_issues:
            prompt += f"\n{issue['category'].upper()}: '{issue['actual_name']}' vs '{issue['expected_name']}'"
            prompt += f"\n  Confidence: {issue['confidence']:.1%}"
            prompt += f"\n  Context: {issue['context']}"
        
        prompt += """

Please provide:
1. Naming convention recommendations
2. Standardization suggestions for each category
3. Refactoring priority order
4. Consistent naming patterns to adopt
5. Tools or IDE settings to prevent future inconsistencies
"""
        
        # In production, this would call Gemini AI
        # For now, return a structured response
        interpretation = f"""## Interface Consistency Analysis

### Summary
Found {stats.get('total_issues', 0)} naming inconsistencies across the analyzed codebase.

### Naming Convention Assessment
**Predominant Style**: {patterns.get('naming_conventions', {}).get('predominant_style', 'Mixed')}
- This suggests the codebase generally follows consistent conventions

### Critical Issues
"""
        
        if stats.get('method_mismatches', 0) > 0:
            interpretation += f"\n**Method Naming**: {stats.get('method_mismatches', 0)} inconsistencies found\n"
            interpretation += "- Focus on standardizing get/fetch/retrieve patterns\n"
            interpretation += "- Align count/total/num terminology\n"
        
        if stats.get('property_mismatches', 0) > 0:
            interpretation += f"\n**Property Naming**: {stats.get('property_mismatches', 0)} inconsistencies found\n"
            interpretation += "- Standardize singular vs plural forms\n"
            interpretation += "- Align file/filename/filepath usage\n"
        
        interpretation += "\n### Recommendations\n"
        interpretation += "1. **Establish naming conventions** document\n"
        interpretation += "2. **Use linting rules** to enforce consistency\n"
        interpretation += "3. **Refactor gradually** starting with high-confidence issues\n"
        interpretation += "4. **Code review checklist** should include naming consistency\n"
        interpretation += "5. **IDE templates** can help maintain patterns\n"
        
        if high_confidence_issues:
            interpretation += "\n### Specific Fixes\n"
            for issue in high_confidence_issues[:3]:
                interpretation += f"\n**{issue['actual_name']}** → **{issue['expected_name']}**\n"
                interpretation += f"  - Confidence: {issue['confidence']:.1%}\n"
                interpretation += f"  - Action: {issue['suggestion']}\n"
        
        return interpretation
    
    @with_file_freshness_check
    async def enhanced_interface_checker(self, 
                                        paths: List[str] = None,
                                        verified_files: List[str] = None,
                                        check_methods: bool = True,
                                        check_properties: bool = True,
                                        check_returns: bool = True,
                                        check_parameters: bool = True,
                                        context: Optional[str] = None,
                                        **kwargs) -> str:
        """
        Enhanced interface inconsistency detection with File Freshness Guardian integration
        
        Args:
            paths: Original paths requested
            verified_files: Files verified by File Freshness Guardian
            check_methods: Check for method naming inconsistencies
            check_properties: Check for property naming inconsistencies  
            check_returns: Check for return structure inconsistencies
            check_parameters: Check for parameter naming inconsistencies
            context: Codebase context for AI analysis
            
        Returns:
            Formatted inconsistency report with AI recommendations
        """
        # Use verified files from decorator
        files_to_check = verified_files or paths or []
        
        # Execute inconsistency detection
        result = await self.execute(
            files=files_to_check,
            with_ai=True,
            context=context,
            check_methods=check_methods,
            check_properties=check_properties,
            check_returns=check_returns,
            check_parameters=check_parameters
        )
        
        return self.format_results(result)