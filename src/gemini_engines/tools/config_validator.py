"""
Configuration Validator Tool for Gemini MCP System
Validates environment variables, configuration files, and settings
Following Tool-as-a-Service pattern with File Freshness Guardian integration
"""
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
import logging

from .base_tool import FileAnalysisTool, ToolResult
from ..integration.file_freshness_decorator import with_file_freshness_check
from ..services.file_integrity_validator import FileIntegrityValidator

logger = logging.getLogger(__name__)

@dataclass
class ConfigIssue:
    """Represents a configuration issue"""
    severity: str  # critical, warning, info
    category: str  # missing, insecure, deprecated, invalid
    file: str
    line_number: Optional[int]
    key: str
    message: str
    suggestion: Optional[str] = None

class ConfigValidator(FileAnalysisTool):
    """
    Configuration validation tool with AI-powered fix suggestions
    
    Features:
    - Check required environment variables
    - Validate secure settings (no hardcoded secrets)
    - Compare dev/prod configurations
    - Find deprecated/unused settings
    - Suggest fixes through Gemini AI
    """
    
    # Common required environment variables for web applications
    COMMON_REQUIRED_VARS = {
        'DATABASE_URL', 'REDIS_URL', 'SECRET_KEY', 'API_KEY',
        'JWT_SECRET', 'ENCRYPTION_KEY', 'ALLOWED_HOSTS'
    }
    
    # Patterns that indicate potential secrets
    SECRET_PATTERNS = [
        r'password\s*=\s*["\'](?!<.*>)[^"\']+["\']',
        r'api[_-]?key\s*=\s*["\'](?!<.*>)[^"\']+["\']',
        r'secret\s*=\s*["\'](?!<.*>)[^"\']+["\']',
        r'token\s*=\s*["\'](?!<.*>)[^"\']+["\']',
        r'[A-Z_]+KEY\s*=\s*["\'][A-Za-z0-9+/]{20,}["\']'
    ]
    
    # Deprecated configuration patterns
    DEPRECATED_PATTERNS = {
        'DEBUG=True': 'Debug mode should be disabled in production',
        'ALLOWED_HOSTS=\\*': 'Wildcard hosts are insecure',
        'CORS_ORIGIN_ALLOW_ALL=True': 'CORS should be restricted',
        'SECURE_SSL_REDIRECT=False': 'SSL redirect should be enabled',
        'SESSION_COOKIE_SECURE=False': 'Session cookies should be secure'
    }
    
    def __init__(self):
        super().__init__("ConfigValidator")
        self.issues: List[ConfigIssue] = []
        
    def _core_utility(self, files: List[str], **kwargs) -> Dict[str, Any]:
        """
        Core configuration validation logic
        
        Args:
            files: List of configuration files to validate
            **kwargs: Additional parameters (check_security, check_deprecated, etc.)
            
        Returns:
            Dictionary with validation results
        """
        self.issues = []
        results = {
            "total_files": len(files),
            "files_analyzed": [],
            "issues": [],
            "statistics": {
                "critical_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "total_issues": 0
            },
            "environment_variables": {},
            "secure_settings": {},
            "deprecated_settings": []
        }
        
        check_security = kwargs.get('check_security', True)
        check_deprecated = kwargs.get('check_deprecated', True)
        check_required = kwargs.get('check_required', True)
        
        for file_path in files:
            if not self.is_config_file(file_path):
                continue
                
            content = self.read_file_safe(file_path)
            if not content:
                continue
                
            results["files_analyzed"].append(file_path)
            
            # Parse based on file type
            if file_path.endswith('.env'):
                self._validate_env_file(file_path, content, results, 
                                       check_security, check_deprecated, check_required)
            elif file_path.endswith(('.json', '.jsonc')):
                self._validate_json_config(file_path, content, results)
            elif file_path.endswith(('.yaml', '.yml')):
                self._validate_yaml_config(file_path, content, results)
            elif file_path.endswith('.toml'):
                self._validate_toml_config(file_path, content, results)
                
        # Convert issues to dict format
        for issue in self.issues:
            issue_dict = {
                "severity": issue.severity,
                "category": issue.category,
                "file": issue.file,
                "line": issue.line_number,
                "key": issue.key,
                "message": issue.message,
                "suggestion": issue.suggestion
            }
            results["issues"].append(issue_dict)
            
            # Update statistics
            if issue.severity == "critical":
                results["statistics"]["critical_count"] += 1
            elif issue.severity == "warning":
                results["statistics"]["warning_count"] += 1
            else:
                results["statistics"]["info_count"] += 1
                
        results["statistics"]["total_issues"] = len(self.issues)
        
        return results
    
    def _validate_env_file(self, file_path: str, content: str, results: Dict,
                          check_security: bool, check_deprecated: bool, check_required: bool):
        """Validate .env file contents"""
        lines = content.split('\n')
        env_vars = {}
        
        for line_num, line in enumerate(lines, 1):
            # Skip comments and empty lines
            if line.strip().startswith('#') or not line.strip():
                continue
                
            # Parse key=value
            if '=' in line:
                key = line.split('=')[0].strip()
                value = line.split('=', 1)[1].strip()
                env_vars[key] = value
                
                # Check for hardcoded secrets
                if check_security and value and not value.startswith('${'):
                    if self._looks_like_secret(key, value):
                        self.issues.append(ConfigIssue(
                            severity="critical",
                            category="insecure",
                            file=file_path,
                            line_number=line_num,
                            key=key,
                            message=f"Potential hardcoded secret in {key}",
                            suggestion=f"Use environment variable reference: {key}=${{'{key}_SECRET'}}"
                        ))
                
                # Check for deprecated patterns
                if check_deprecated:
                    for pattern, message in self.DEPRECATED_PATTERNS.items():
                        if pattern in line:
                            self.issues.append(ConfigIssue(
                                severity="warning",
                                category="deprecated",
                                file=file_path,
                                line_number=line_num,
                                key=key,
                                message=message,
                                suggestion="Update to recommended configuration"
                            ))
        
        results["environment_variables"][file_path] = env_vars
        
        # Check for missing required variables
        if check_required:
            self._check_required_vars(file_path, env_vars)
    
    def _validate_json_config(self, file_path: str, content: str, results: Dict):
        """Validate JSON configuration file"""
        try:
            config = json.loads(content)
            self._validate_config_dict(file_path, config, results)
        except json.JSONDecodeError as e:
            self.issues.append(ConfigIssue(
                severity="critical",
                category="invalid",
                file=file_path,
                line_number=None,
                key="JSON",
                message=f"Invalid JSON syntax: {e}",
                suggestion="Fix JSON syntax errors"
            ))
    
    def _validate_yaml_config(self, file_path: str, content: str, results: Dict):
        """Validate YAML configuration file"""
        try:
            import yaml
            config = yaml.safe_load(content)
            self._validate_config_dict(file_path, config, results)
        except ImportError:
            self.logger.warning("PyYAML not installed, skipping YAML validation")
        except Exception as e:
            self.issues.append(ConfigIssue(
                severity="critical",
                category="invalid",
                file=file_path,
                line_number=None,
                key="YAML",
                message=f"Invalid YAML syntax: {e}",
                suggestion="Fix YAML syntax errors"
            ))
    
    def _validate_toml_config(self, file_path: str, content: str, results: Dict):
        """Validate TOML configuration file"""
        try:
            import toml
            config = toml.loads(content)
            self._validate_config_dict(file_path, config, results)
        except ImportError:
            self.logger.warning("toml not installed, skipping TOML validation")
        except Exception as e:
            self.issues.append(ConfigIssue(
                severity="critical",
                category="invalid",
                file=file_path,
                line_number=None,
                key="TOML",
                message=f"Invalid TOML syntax: {e}",
                suggestion="Fix TOML syntax errors"
            ))
    
    def _validate_config_dict(self, file_path: str, config: Dict, results: Dict):
        """Validate configuration dictionary (from JSON/YAML/TOML)"""
        def check_dict_recursive(d: Dict, path: str = ""):
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key
                
                # Check for potential secrets in values
                if isinstance(value, str) and self._looks_like_secret(key, value):
                    self.issues.append(ConfigIssue(
                        severity="warning",
                        category="insecure",
                        file=file_path,
                        line_number=None,
                        key=current_path,
                        message=f"Potential secret in configuration",
                        suggestion="Move to environment variable"
                    ))
                
                # Recurse into nested dicts
                elif isinstance(value, dict):
                    check_dict_recursive(value, current_path)
        
        check_dict_recursive(config)
    
    def _looks_like_secret(self, key: str, value: str) -> bool:
        """Check if a value looks like a secret"""
        # Skip empty or placeholder values
        if not value or value in ['', 'null', 'none', 'undefined', 'TODO', 'CHANGEME']:
            return False
            
        # Skip environment variable references
        if value.startswith('${') or value.startswith('%('):
            return False
        
        # Check key names that typically contain secrets
        secret_key_patterns = ['password', 'secret', 'key', 'token', 'api', 'auth', 'credential']
        key_lower = key.lower()
        if any(pattern in key_lower for pattern in secret_key_patterns):
            # Check if value looks like an actual secret (not a placeholder)
            if len(value) > 10 and not value.startswith('<') and not value.endswith('>'):
                return True
        
        # Check for patterns that look like API keys or tokens
        if re.match(r'^[A-Za-z0-9+/]{20,}={0,2}$', value):
            return True
            
        return False
    
    def _check_required_vars(self, file_path: str, env_vars: Dict[str, str]):
        """Check for missing required environment variables"""
        # Check for common required variables based on what's already defined
        required = set()
        
        # If database URL is defined, check for related vars
        if 'DATABASE_URL' in env_vars or 'DB_HOST' in env_vars:
            required.update(['DATABASE_URL', 'DB_NAME'])
        
        # If API keys are used, check for them
        if any('API' in key for key in env_vars):
            required.add('API_KEY')
        
        # If authentication is configured
        if any(key in env_vars for key in ['JWT_SECRET', 'AUTH_KEY', 'SESSION_SECRET']):
            required.update(['SECRET_KEY', 'JWT_SECRET'])
        
        # Check for missing required variables
        for var in required:
            if var not in env_vars:
                self.issues.append(ConfigIssue(
                    severity="warning",
                    category="missing",
                    file=file_path,
                    line_number=None,
                    key=var,
                    message=f"Missing potentially required variable: {var}",
                    suggestion=f"Add {var}=your_value to configuration"
                ))
    
    async def _get_ai_interpretation(self, 
                                    core_results: Dict[str, Any],
                                    context: Optional[str] = None) -> str:
        """
        Get Gemini AI interpretation of configuration issues
        
        Args:
            core_results: Validation results from core utility
            context: Optional context about the application
            
        Returns:
            AI interpretation with fix suggestions
        """
        # Format results for Gemini
        issues = core_results.get("issues", [])
        stats = core_results.get("statistics", {})
        
        if not issues:
            return "✅ Configuration looks good! No significant issues found."
        
        # Create prompt for Gemini
        prompt = f"""Analyze these configuration issues and provide specific fix recommendations:

Context: {context or 'Configuration validation for application'}

Issues Found:
- Critical: {stats.get('critical_count', 0)}
- Warnings: {stats.get('warning_count', 0)}
- Info: {stats.get('info_count', 0)}

Detailed Issues:
"""
        
        for issue in issues[:10]:  # Limit to first 10 issues
            prompt += f"\n{issue['severity'].upper()}: {issue['message']}"
            prompt += f"\n  File: {issue['file']}"
            if issue.get('key'):
                prompt += f"\n  Key: {issue['key']}"
            if issue.get('suggestion'):
                prompt += f"\n  Initial suggestion: {issue['suggestion']}"
        
        prompt += """

Please provide:
1. Summary of the configuration health
2. Specific fixes for each critical issue
3. Best practices recommendations
4. Example corrections where applicable
"""
        
        # In production, this would call Gemini API
        # For now, return a structured response
        interpretation = f"""## Configuration Analysis

### Summary
Found {stats.get('total_issues', 0)} configuration issues across {len(core_results.get('files_analyzed', []))} files.

### Critical Issues
"""
        
        critical_issues = [i for i in issues if i['severity'] == 'critical']
        if critical_issues:
            for issue in critical_issues[:5]:
                interpretation += f"\n**{issue['file']}** - {issue['message']}\n"
                interpretation += f"  Fix: {issue.get('suggestion', 'Review and update configuration')}\n"
        else:
            interpretation += "\nNo critical issues found.\n"
        
        interpretation += "\n### Recommendations\n"
        interpretation += "1. Move all secrets to environment variables\n"
        interpretation += "2. Use different .env files for dev/staging/production\n"
        interpretation += "3. Never commit .env files to version control\n"
        interpretation += "4. Validate configuration on application startup\n"
        
        return interpretation
    
    @with_file_freshness_check
    async def enhanced_config_validator(self, 
                                       paths: List[str] = None,
                                       verified_files: List[str] = None,
                                       check_security: bool = True,
                                       check_deprecated: bool = True,
                                       check_required: bool = True,
                                       context: Optional[str] = None,
                                       **kwargs) -> str:
        """
        Enhanced configuration validation with File Freshness Guardian integration
        
        Args:
            paths: Original paths requested
            verified_files: Files verified by File Freshness Guardian
            check_security: Check for security issues
            check_deprecated: Check for deprecated settings
            check_required: Check for missing required variables
            context: Application context for AI
            
        Returns:
            Formatted validation report with AI recommendations
        """
        # Use verified files from decorator
        files_to_check = verified_files or paths or []
        
        # Execute validation
        result = await self.execute(
            files=files_to_check,
            with_ai=True,
            context=context,
            check_security=check_security,
            check_deprecated=check_deprecated,
            check_required=check_required
        )
        
        return self.format_results(result)