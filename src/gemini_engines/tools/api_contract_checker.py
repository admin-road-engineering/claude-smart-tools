"""
API Contract Checker Tool for Gemini MCP System
Validates OpenAPI specifications, compares versions, and identifies breaking changes
Following Tool-as-a-Service pattern with File Freshness Guardian integration
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
import logging
from enum import Enum

from .base_tool import FileAnalysisTool, ToolResult
from ..integration.file_freshness_decorator import with_file_freshness_check

logger = logging.getLogger(__name__)

class ChangeType(Enum):
    BREAKING = "breaking"
    NON_BREAKING = "non_breaking"
    ADDITION = "addition"
    DEPRECATION = "deprecation"

@dataclass
class APIChange:
    """Represents an API change"""
    change_type: ChangeType
    severity: str  # critical, warning, info
    endpoint: str
    method: str
    category: str  # endpoint, parameter, response, schema
    description: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    impact: Optional[str] = None
    suggestion: Optional[str] = None

class APIContractChecker(FileAnalysisTool):
    """
    API contract validation and comparison tool with AI-powered impact analysis
    
    Features:
    - Parse OpenAPI/Swagger specifications
    - Compare API versions for breaking changes
    - Validate schema consistency
    - Check backwards compatibility
    - Provide impact analysis through Gemini AI
    """
    
    # Breaking changes that affect API consumers
    BREAKING_CHANGE_RULES = {
        'endpoint_removed': 'Endpoint removal breaks existing clients',
        'method_removed': 'HTTP method removal breaks existing clients',
        'required_param_added': 'New required parameters break existing clients',
        'param_type_changed': 'Parameter type changes break existing clients',
        'response_structure_changed': 'Response structure changes may break clients',
        'status_code_removed': 'Removing status codes breaks error handling'
    }
    
    def __init__(self):
        super().__init__("APIContractChecker")
        self.changes: List[APIChange] = []
        
    def _core_utility(self, files: List[str], **kwargs) -> Dict[str, Any]:
        """
        Core API contract validation logic
        
        Args:
            files: List of API specification files to validate
            **kwargs: Additional parameters (baseline_spec, compare_mode, etc.)
            
        Returns:
            Dictionary with contract analysis results
        """
        self.changes = []
        results = {
            "total_files": len(files),
            "specs_analyzed": [],
            "changes": [],
            "statistics": {
                "breaking_changes": 0,
                "non_breaking_changes": 0,
                "additions": 0,
                "deprecations": 0,
                "total_changes": 0
            },
            "endpoints": {},
            "schemas": {},
            "compatibility_score": 100
        }
        
        compare_mode = kwargs.get('compare_mode', False)
        baseline_spec = kwargs.get('baseline_spec')
        
        # Parse all specification files
        parsed_specs = {}
        for file_path in files:
            if not self.is_api_spec_file(file_path):
                continue
                
            content = self.read_file_safe(file_path)
            if not content:
                continue
                
            spec = self._parse_api_spec(file_path, content)
            if spec:
                parsed_specs[file_path] = spec
                results["specs_analyzed"].append(file_path)
                
        # If comparing specs, perform comparison
        if compare_mode and baseline_spec and len(parsed_specs) >= 2:
            self._compare_specifications(baseline_spec, parsed_specs, results)
        else:
            # Single spec validation
            for file_path, spec in parsed_specs.items():
                self._validate_single_spec(file_path, spec, results)
                
        # Convert changes to dict format
        for change in self.changes:
            change_dict = {
                "type": change.change_type.value,
                "severity": change.severity,
                "endpoint": change.endpoint,
                "method": change.method,
                "category": change.category,
                "description": change.description,
                "old_value": change.old_value,
                "new_value": change.new_value,
                "impact": change.impact,
                "suggestion": change.suggestion
            }
            results["changes"].append(change_dict)
            
            # Update statistics
            if change.change_type == ChangeType.BREAKING:
                results["statistics"]["breaking_changes"] += 1
            elif change.change_type == ChangeType.NON_BREAKING:
                results["statistics"]["non_breaking_changes"] += 1
            elif change.change_type == ChangeType.ADDITION:
                results["statistics"]["additions"] += 1
            elif change.change_type == ChangeType.DEPRECATION:
                results["statistics"]["deprecations"] += 1
                
        results["statistics"]["total_changes"] = len(self.changes)
        
        # Calculate compatibility score
        breaking_count = results["statistics"]["breaking_changes"]
        if breaking_count > 0:
            results["compatibility_score"] = max(0, 100 - (breaking_count * 20))
        
        return results
    
    def _parse_api_spec(self, file_path: str, content: str) -> Optional[Dict]:
        """Parse API specification file"""
        try:
            if file_path.endswith(('.json', '.jsonc')):
                return json.loads(content)
            elif file_path.endswith(('.yaml', '.yml')):
                try:
                    import yaml
                    return yaml.safe_load(content)
                except ImportError:
                    self.logger.warning("PyYAML not installed, cannot parse YAML specs")
                    return None
            else:
                # Try JSON first, then YAML
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    try:
                        import yaml
                        return yaml.safe_load(content)
                    except:
                        return None
        except Exception as e:
            self.logger.error(f"Failed to parse API spec {file_path}: {e}")
            return None
    
    def _validate_single_spec(self, file_path: str, spec: Dict, results: Dict):
        """Validate a single API specification"""
        # Check for OpenAPI version
        openapi_version = spec.get('openapi', spec.get('swagger'))
        if not openapi_version:
            self.changes.append(APIChange(
                change_type=ChangeType.NON_BREAKING,
                severity="warning",
                endpoint="*",
                method="*",
                category="spec",
                description="Missing OpenAPI/Swagger version",
                suggestion="Add 'openapi' or 'swagger' version field"
            ))
        
        # Validate required fields
        required_fields = ['info', 'paths']
        for field in required_fields:
            if field not in spec:
                self.changes.append(APIChange(
                    change_type=ChangeType.NON_BREAKING,
                    severity="critical",
                    endpoint="*",
                    method="*",
                    category="spec",
                    description=f"Missing required field: {field}",
                    suggestion=f"Add {field} section to specification"
                ))
        
        # Analyze endpoints
        paths = spec.get('paths', {})
        results["endpoints"][file_path] = {}
        
        for path, methods in paths.items():
            results["endpoints"][file_path][path] = list(methods.keys())
            
            for method, operation in methods.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                    self._validate_operation(file_path, path, method, operation)
        
        # Analyze schemas
        schemas = spec.get('components', {}).get('schemas', {}) or spec.get('definitions', {})
        results["schemas"][file_path] = list(schemas.keys())
    
    def _validate_operation(self, file_path: str, path: str, method: str, operation: Dict):
        """Validate individual API operation"""
        # Check for required operation fields
        if 'responses' not in operation:
            self.changes.append(APIChange(
                change_type=ChangeType.NON_BREAKING,
                severity="warning",
                endpoint=path,
                method=method.upper(),
                category="endpoint",
                description="Missing responses definition",
                suggestion="Add responses section to operation"
            ))
        
        # Check for description/summary
        if 'summary' not in operation and 'description' not in operation:
            self.changes.append(APIChange(
                change_type=ChangeType.NON_BREAKING,
                severity="info",
                endpoint=path,
                method=method.upper(),
                category="endpoint",
                description="Missing operation documentation",
                suggestion="Add summary or description to operation"
            ))
        
        # Validate parameters
        parameters = operation.get('parameters', [])
        for param in parameters:
            if 'name' not in param or 'in' not in param:
                self.changes.append(APIChange(
                    change_type=ChangeType.NON_BREAKING,
                    severity="warning",
                    endpoint=path,
                    method=method.upper(),
                    category="parameter",
                    description="Invalid parameter definition",
                    suggestion="Ensure parameters have 'name' and 'in' properties"
                ))
    
    def _compare_specifications(self, baseline_path: str, specs: Dict[str, Dict], results: Dict):
        """Compare API specifications to find changes"""
        if baseline_path not in specs:
            self.logger.error(f"Baseline spec {baseline_path} not found")
            return
        
        baseline_spec = specs[baseline_path]
        
        # Compare with each other spec
        for spec_path, current_spec in specs.items():
            if spec_path == baseline_path:
                continue
                
            self._compare_two_specs(baseline_spec, current_spec, spec_path)
    
    def _compare_two_specs(self, baseline: Dict, current: Dict, current_path: str):
        """Compare two API specifications"""
        baseline_paths = baseline.get('paths', {})
        current_paths = current.get('paths', {})
        
        # Check for removed endpoints
        for path in baseline_paths:
            if path not in current_paths:
                self.changes.append(APIChange(
                    change_type=ChangeType.BREAKING,
                    severity="critical",
                    endpoint=path,
                    method="*",
                    category="endpoint",
                    description=f"Endpoint removed",
                    old_value=path,
                    impact="Breaks existing clients using this endpoint",
                    suggestion="Consider deprecation instead of removal"
                ))
            else:
                # Compare methods for existing endpoints
                self._compare_endpoint_methods(
                    path, baseline_paths[path], current_paths[path]
                )
        
        # Check for added endpoints
        for path in current_paths:
            if path not in baseline_paths:
                self.changes.append(APIChange(
                    change_type=ChangeType.ADDITION,
                    severity="info",
                    endpoint=path,
                    method="*",
                    category="endpoint",
                    description="New endpoint added",
                    new_value=path,
                    impact="No breaking change - addition only"
                ))
        
        # Compare schemas
        self._compare_schemas(
            baseline.get('components', {}).get('schemas', {}),
            current.get('components', {}).get('schemas', {})
        )
    
    def _compare_endpoint_methods(self, path: str, baseline_methods: Dict, current_methods: Dict):
        """Compare methods for a specific endpoint"""
        for method in baseline_methods:
            if method not in current_methods:
                self.changes.append(APIChange(
                    change_type=ChangeType.BREAKING,
                    severity="critical",
                    endpoint=path,
                    method=method.upper(),
                    category="endpoint",
                    description=f"HTTP method {method.upper()} removed",
                    old_value=method,
                    impact="Breaks clients using this method",
                    suggestion="Consider deprecation instead of removal"
                ))
            else:
                # Compare operation details
                self._compare_operations(
                    path, method, baseline_methods[method], current_methods[method]
                )
    
    def _compare_operations(self, path: str, method: str, baseline_op: Dict, current_op: Dict):
        """Compare operation details"""
        # Compare parameters
        baseline_params = baseline_op.get('parameters', [])
        current_params = current_op.get('parameters', [])
        
        # Create parameter maps for easier comparison
        baseline_param_map = {f"{p.get('name', '')}-{p.get('in', '')}": p for p in baseline_params}
        current_param_map = {f"{p.get('name', '')}-{p.get('in', '')}": p for p in current_params}
        
        # Check for removed parameters
        for param_key, param in baseline_param_map.items():
            if param_key not in current_param_map:
                change_type = ChangeType.BREAKING if param.get('required', False) else ChangeType.NON_BREAKING
                severity = "critical" if param.get('required', False) else "warning"
                
                self.changes.append(APIChange(
                    change_type=change_type,
                    severity=severity,
                    endpoint=path,
                    method=method.upper(),
                    category="parameter",
                    description=f"Parameter '{param.get('name')}' removed",
                    old_value=param.get('name'),
                    impact="May break clients if parameter was required",
                    suggestion="Consider deprecation instead of removal"
                ))
        
        # Check for new required parameters
        for param_key, param in current_param_map.items():
            if param_key not in baseline_param_map and param.get('required', False):
                self.changes.append(APIChange(
                    change_type=ChangeType.BREAKING,
                    severity="critical",
                    endpoint=path,
                    method=method.upper(),
                    category="parameter",
                    description=f"New required parameter '{param.get('name')}' added",
                    new_value=param.get('name'),
                    impact="Breaks existing clients",
                    suggestion="Make parameter optional or provide default value"
                ))
        
        # Compare response schemas
        baseline_responses = baseline_op.get('responses', {})
        current_responses = current_op.get('responses', {})
        
        for status_code in baseline_responses:
            if status_code not in current_responses:
                self.changes.append(APIChange(
                    change_type=ChangeType.BREAKING,
                    severity="warning",
                    endpoint=path,
                    method=method.upper(),
                    category="response",
                    description=f"Response status code {status_code} removed",
                    old_value=status_code,
                    impact="May break client error handling",
                    suggestion="Keep status code for backwards compatibility"
                ))
    
    def _compare_schemas(self, baseline_schemas: Dict, current_schemas: Dict):
        """Compare schema definitions"""
        for schema_name in baseline_schemas:
            if schema_name not in current_schemas:
                self.changes.append(APIChange(
                    change_type=ChangeType.BREAKING,
                    severity="critical",
                    endpoint="*",
                    method="*",
                    category="schema",
                    description=f"Schema '{schema_name}' removed",
                    old_value=schema_name,
                    impact="Breaks clients using this schema",
                    suggestion="Keep schema for backwards compatibility"
                ))
    
    async def _get_ai_interpretation(self, 
                                    core_results: Dict[str, Any],
                                    context: Optional[str] = None) -> str:
        """
        Get Gemini AI interpretation of API contract changes
        
        Args:
            core_results: Contract analysis results from core utility
            context: Optional context about the API
            
        Returns:
            AI interpretation with impact analysis
        """
        changes = core_results.get("changes", [])
        stats = core_results.get("statistics", {})
        compatibility_score = core_results.get("compatibility_score", 100)
        
        if not changes:
            return "✅ API contract validation successful! No breaking changes detected."
        
        # Create prompt for Gemini
        prompt = f"""Analyze these API contract changes and provide impact assessment:

Context: {context or 'API specification analysis'}

Compatibility Score: {compatibility_score}%

Change Statistics:
- Breaking Changes: {stats.get('breaking_changes', 0)}
- Non-Breaking Changes: {stats.get('non_breaking_changes', 0)}
- Additions: {stats.get('additions', 0)}
- Deprecations: {stats.get('deprecations', 0)}

Critical Changes:
"""
        
        breaking_changes = [c for c in changes if c['type'] == 'breaking'][:5]
        for change in breaking_changes:
            prompt += f"\n{change['description']}"
            prompt += f"\n  Endpoint: {change['endpoint']} {change['method']}"
            prompt += f"\n  Impact: {change.get('impact', 'Unknown')}"
        
        prompt += """

Please provide:
1. Overall API health assessment
2. Migration guidance for breaking changes
3. Risk assessment for each critical change
4. Recommended rollback strategy if needed
5. Communication plan for API consumers
"""
        
        # In production, this would call Gemini API
        # For now, return a structured response
        interpretation = f"""## API Contract Analysis

### Compatibility Assessment
**Score: {compatibility_score}%** - """
        
        if compatibility_score >= 90:
            interpretation += "Excellent compatibility"
        elif compatibility_score >= 70:
            interpretation += "Good compatibility with minor issues"
        elif compatibility_score >= 50:
            interpretation += "Moderate compatibility concerns"
        else:
            interpretation += "Significant compatibility issues"
        
        interpretation += f"\n\n### Impact Summary\n"
        interpretation += f"- **{stats.get('breaking_changes', 0)} breaking changes** require immediate attention\n"
        interpretation += f"- **{stats.get('additions', 0)} new features** enhance functionality\n"
        interpretation += f"- **{stats.get('non_breaking_changes', 0)} minor changes** need monitoring\n"
        
        if breaking_changes:
            interpretation += "\n### Critical Issues\n"
            for change in breaking_changes[:3]:
                interpretation += f"\n**{change['endpoint']} {change['method']}**\n"
                interpretation += f"- Issue: {change['description']}\n"
                interpretation += f"- Impact: {change.get('impact', 'Requires client updates')}\n"
                interpretation += f"- Action: {change.get('suggestion', 'Review and plan migration')}\n"
        
        interpretation += "\n### Recommendations\n"
        interpretation += "1. **Version your API** to allow gradual migration\n"
        interpretation += "2. **Deprecate before removing** endpoints and parameters\n"
        interpretation += "3. **Document all changes** in changelog\n"
        interpretation += "4. **Notify API consumers** before deploying breaking changes\n"
        interpretation += "5. **Test backwards compatibility** thoroughly\n"
        
        return interpretation
    
    @with_file_freshness_check
    async def enhanced_contract_checker(self, 
                                       paths: List[str] = None,
                                       verified_files: List[str] = None,
                                       baseline_spec: Optional[str] = None,
                                       compare_mode: bool = False,
                                       context: Optional[str] = None,
                                       **kwargs) -> str:
        """
        Enhanced API contract validation with File Freshness Guardian integration
        
        Args:
            paths: Original paths requested
            verified_files: Files verified by File Freshness Guardian
            baseline_spec: Baseline specification for comparison
            compare_mode: Whether to compare specifications
            context: API context for AI analysis
            
        Returns:
            Formatted contract analysis report with AI recommendations
        """
        # Use verified files from decorator
        files_to_check = verified_files or paths or []
        
        # Execute contract checking
        result = await self.execute(
            files=files_to_check,
            with_ai=True,
            context=context,
            baseline_spec=baseline_spec,
            compare_mode=compare_mode
        )
        
        return self.format_results(result)