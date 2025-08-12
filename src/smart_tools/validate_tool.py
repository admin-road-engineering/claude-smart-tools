"""
Validate Tool - Smart tool for quality assurance, security, performance, standards, and consistency checking
Routes to check_quality + config_validator + interface_inconsistency_detector based on validation type
"""
from typing import List, Dict, Any, Optional
from .base_smart_tool import BaseSmartTool, SmartToolResult
from .executive_synthesizer import ExecutiveSynthesizer


class ValidateTool(BaseSmartTool):
    """
    Smart tool for comprehensive validation and quality assurance
    Intelligently routes to multiple engines based on validation requirements
    """
    
    def __init__(self, engines: Dict[str, Any]):
        super().__init__(engines)
        self.executive_synthesizer = ExecutiveSynthesizer(engines)
    
    def get_routing_strategy(self, files: List[str], validation_type: str = "all", 
                           severity: str = "medium", **kwargs) -> Dict[str, Any]:
        """
        Determine which engines to use based on validation type and requirements
        """
        engines_to_use = []
        routing_explanation = []
        
        # Security validation
        if validation_type in ['security', 'all']:
            engines_to_use.extend(['check_quality', 'config_validator'])
            routing_explanation.append("Security validation enabled - adding quality checks and config validation")
        
        # Performance validation
        if validation_type in ['performance', 'all']:
            engines_to_use.extend(['check_quality', 'performance_profiler'])
            routing_explanation.append("Performance validation enabled - adding quality checks and profiling")
        
        # Quality/standards validation
        if validation_type in ['quality', 'all']:
            engines_to_use.extend(['check_quality', 'interface_inconsistency_detector'])
            routing_explanation.append("Quality validation enabled - adding comprehensive quality checks and consistency analysis")
        
        # Consistency validation
        if validation_type in ['consistency', 'all']:
            engines_to_use.extend(['interface_inconsistency_detector', 'analyze_code'])
            routing_explanation.append("Consistency validation enabled - adding interface analysis and architectural review")
        
        # API contract validation for relevant files
        api_files = self._detect_api_files(files)
        if api_files:
            engines_to_use.append('api_contract_checker')
            routing_explanation.append(f"API specifications detected - adding contract validation for {len(api_files)} files")
        
        # Database validation for relevant files
        db_files = self._detect_database_files(files)
        if db_files:
            engines_to_use.append('analyze_database')
            routing_explanation.append(f"Database files detected - adding schema validation for {len(db_files)} files")
        
        # Test coverage validation for source code
        source_files = self._detect_source_files(files)
        if source_files:
            engines_to_use.append('analyze_test_coverage')
            routing_explanation.append(f"Source code detected - adding test coverage analysis for {len(source_files)} files")
        
        # Dependency analysis for multi-file projects
        if len(files) > 1 or validation_type == 'all':
            engines_to_use.append('map_dependencies')
            routing_explanation.append("Multi-file validation - adding dependency analysis for coupling and circular dependency checks")
        
        # Remove duplicates while preserving order
        engines_to_use = list(dict.fromkeys(engines_to_use))
        
        return {
            'engines': engines_to_use,
            'explanation': '; '.join(routing_explanation),
            'validation_scope': self._determine_validation_scope(validation_type, engines_to_use),
            'severity_filter': severity
        }
    
    def _detect_api_files(self, files: List[str]) -> List[str]:
        """Detect API specification files"""
        api_extensions = ['.json', '.yaml', '.yml']
        api_keywords = ['api', 'swagger', 'openapi', 'spec']
        
        api_files = []
        for file_path in files:
            file_lower = file_path.lower()
            if (any(file_lower.endswith(ext) for ext in api_extensions) and 
                any(keyword in file_lower for keyword in api_keywords)):
                api_files.append(file_path)
        
        return api_files
    
    def _detect_database_files(self, files: List[str]) -> List[str]:
        """Detect database-related files"""
        db_extensions = ['.sql', '.db', '.sqlite', '.sqlite3']
        db_keywords = ['schema', 'migration', 'model', 'database']
        
        db_files = []
        for file_path in files:
            file_lower = file_path.lower()
            if (any(file_lower.endswith(ext) for ext in db_extensions) or 
                any(keyword in file_lower for keyword in db_keywords)):
                db_files.append(file_path)
        
        return db_files
    
    def _detect_source_files(self, files: List[str]) -> List[str]:
        """Detect source code files"""
        source_extensions = ['.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.cs', '.go', '.rs', '.rb']
        
        source_files = []
        for file_path in files:
            if any(file_path.lower().endswith(ext) for ext in source_extensions):
                source_files.append(file_path)
        
        return source_files
    
    def _determine_validation_scope(self, validation_type: str, engines: List[str]) -> str:
        """Determine the overall validation scope"""
        scope_elements = []
        
        if 'check_quality' in engines:
            scope_elements.append("code quality")
        if 'config_validator' in engines:
            scope_elements.append("security configuration")
        if 'interface_inconsistency_detector' in engines:
            scope_elements.append("interface consistency")
        if 'performance_profiler' in engines:
            scope_elements.append("performance profiling")
        if 'api_contract_checker' in engines:
            scope_elements.append("API contracts")
        if 'analyze_database' in engines:
            scope_elements.append("database schemas")
        if 'analyze_test_coverage' in engines:
            scope_elements.append("test coverage")
        if 'map_dependencies' in engines:
            scope_elements.append("dependency analysis")
        if 'analyze_code' in engines:
            scope_elements.append("architectural review")
        
        return f"{validation_type} validation covering: {', '.join(scope_elements)}"
    
    async def execute(self, files: List[str], validation_type: str = "all", 
                     severity: str = "medium", **kwargs) -> SmartToolResult:
        """
        Execute comprehensive validation using coordinated multi-engine analysis
        """
        try:
            routing_strategy = self.get_routing_strategy(
                files=files, validation_type=validation_type, severity=severity, **kwargs
            )
            engines_used = routing_strategy['engines']
            
            validation_results = {}
            issues_found = []
            total_issues = 0
            
            # Phase 1: Core Quality Analysis
            if 'check_quality' in engines_used:
                quality_focus = self._map_validation_to_quality_focus(validation_type)
                quality_result = await self.execute_engine(
                    'check_quality',
                    paths=files,
                    check_type=quality_focus,
                    verbose=True
                )
                validation_results['quality'] = quality_result
                quality_issues = self._extract_issues_from_result(quality_result, "quality")
                issues_found.extend(quality_issues)
                total_issues += len(quality_issues)
            
            # Phase 2: Security Configuration Validation
            if 'config_validator' in engines_used:
                config_files = self._find_config_files(files)
                if config_files:
                    config_result = await self.execute_engine(
                        'config_validator',
                        config_paths=config_files,
                        validation_type="security"
                    )
                    validation_results['security_config'] = config_result
                    config_issues = self._extract_issues_from_result(config_result, "security")
                    issues_found.extend(config_issues)
                    total_issues += len(config_issues)
            
            # Phase 3: Interface Consistency Analysis
            if 'interface_inconsistency_detector' in engines_used:
                source_files = self._detect_source_files(files)
                if source_files:
                    consistency_result = await self.execute_engine(
                        'interface_inconsistency_detector',
                        source_paths=source_files,
                        pattern_types=["naming", "parameters", "return_types"]
                    )
                    validation_results['consistency'] = consistency_result
                    consistency_issues = self._extract_issues_from_result(consistency_result, "consistency")
                    issues_found.extend(consistency_issues)
                    total_issues += len(consistency_issues)
            
            # Phase 4: Performance Validation
            if 'performance_profiler' in engines_used:
                perf_result = await self.execute_engine(
                    'performance_profiler',
                    target_operation="validation_analysis"
                )
                validation_results['performance'] = perf_result
                perf_issues = self._extract_issues_from_result(perf_result, "performance")
                issues_found.extend(perf_issues)
                total_issues += len(perf_issues)
            
            # Phase 5: API Contract Validation
            if 'api_contract_checker' in engines_used:
                api_files = self._detect_api_files(files)
                if api_files:
                    api_result = await self.execute_engine(
                        'api_contract_checker',
                        spec_paths=api_files,
                        comparison_mode="standalone"
                    )
                    validation_results['api_contracts'] = api_result
                    api_issues = self._extract_issues_from_result(api_result, "api")
                    issues_found.extend(api_issues)
                    total_issues += len(api_issues)
            
            # Phase 6: Database Schema Validation
            if 'analyze_database' in engines_used:
                db_files = self._detect_database_files(files)
                if db_files:
                    db_result = await self.execute_engine(
                        'analyze_database',
                        schema_paths=db_files,
                        analysis_type="optimization"
                    )
                    validation_results['database'] = db_result
                    db_issues = self._extract_issues_from_result(db_result, "database")
                    issues_found.extend(db_issues)
                    total_issues += len(db_issues)
            
            # Phase 7: Test Coverage Validation
            if 'analyze_test_coverage' in engines_used:
                source_files = self._detect_source_files(files)
                if source_files:
                    test_result = await self.execute_engine(
                        'analyze_test_coverage',
                        source_paths=source_files
                    )
                    validation_results['test_coverage'] = test_result
                    test_issues = self._extract_issues_from_result(test_result, "testing")
                    issues_found.extend(test_issues)
                    total_issues += len(test_issues)
            
            # Phase 8: Dependency Analysis
            if 'map_dependencies' in engines_used:
                dep_result = await self.execute_engine(
                    'map_dependencies',
                    project_paths=files,
                    analysis_depth="transitive"
                )
                validation_results['dependencies'] = dep_result
                dep_issues = self._extract_issues_from_result(dep_result, "dependencies")
                issues_found.extend(dep_issues)
                total_issues += len(dep_issues)
            
            # Phase 9: Architectural Review
            if 'analyze_code' in engines_used:
                arch_result = await self.execute_engine(
                    'analyze_code',
                    paths=files,
                    analysis_type="refactor_prep",
                    question="What potential issues exist in this code?"
                )
                validation_results['architecture'] = arch_result
                arch_issues = self._extract_issues_from_result(arch_result, "architecture")
                issues_found.extend(arch_issues)
                total_issues += len(arch_issues)
            
            # Filter issues by severity
            filtered_issues = self._filter_issues_by_severity(issues_found, severity)
            
            # Generate validation report
            validation_report = self._synthesize_validation_report(
                validation_type, validation_results, filtered_issues, total_issues, routing_strategy
            )
            
            # Apply executive synthesis for better consolidated response
            if self.executive_synthesizer.should_synthesize(self.tool_name):
                original_request = {
                    'files': files,
                    'validation_type': validation_type,
                    'severity': severity,
                    **kwargs
                }
                validation_report = await self.executive_synthesizer.synthesize(
                    tool_name=self.tool_name,
                    raw_results=validation_report,
                    original_request=original_request
                )
            
            # Determine overall success (no critical issues)
            critical_issues = [issue for issue in filtered_issues if issue.get('severity') == 'high']
            validation_success = len(critical_issues) == 0
            
            return SmartToolResult(
                tool_name="validate",
                success=validation_success,
                result=validation_report,
                engines_used=engines_used,
                routing_decision=routing_strategy['explanation'],
                metadata={
                    "files_analyzed": len(files),
                    "validation_type": validation_type,
                    "severity_filter": severity,
                    "total_issues": total_issues,
                    "filtered_issues": len(filtered_issues),
                    "critical_issues": len(critical_issues),
                    "phases_completed": len(validation_results)
                }
            )
            
        except Exception as e:
            return SmartToolResult(
                tool_name="validate",
                success=False,
                result=f"Validation failed: {str(e)}",
                engines_used=engines_used if 'engines_used' in locals() else [],
                routing_decision=routing_strategy['explanation'] if 'routing_strategy' in locals() else "Failed during routing",
                metadata={"error": str(e)}
            )
    
    def _find_config_files(self, files: List[str]) -> List[str]:
        """Find configuration files in the file list"""
        config_patterns = ['.env', 'config.', 'settings.', '.json', '.yaml', '.yml', '.toml', '.ini']
        config_files = []
        
        for file_path in files:
            file_lower = file_path.lower()
            if any(pattern in file_lower for pattern in config_patterns):
                config_files.append(file_path)
        
        return config_files
    
    def _map_validation_to_quality_focus(self, validation_type: str) -> str:
        """Map validation type to quality check focus"""
        mapping = {
            'security': 'security',
            'performance': 'performance', 
            'quality': 'all',
            'consistency': 'all',
            'all': 'all'
        }
        return mapping.get(validation_type, 'all')
    
    def _extract_issues_from_result(self, result: str, category: str) -> List[Dict[str, Any]]:
        """Extract issues from engine results - simplified heuristic approach"""
        issues = []
        
        # Simple heuristic to detect issues in text results
        result_lower = str(result).lower()
        issue_keywords = ['error', 'warning', 'issue', 'problem', 'vulnerability', 'security', 'deprecated']
        
        if any(keyword in result_lower for keyword in issue_keywords):
            # Count rough number of issues based on keyword frequency
            issue_count = sum(result_lower.count(keyword) for keyword in issue_keywords[:3])  # Top 3 keywords
            
            for i in range(min(issue_count, 5)):  # Max 5 issues per category
                severity = self._determine_issue_severity(result_lower, category)
                issues.append({
                    'category': category,
                    'severity': severity,
                    'description': f"{category.title()} issue detected in analysis",
                    'source': 'automated_detection'
                })
        
        return issues
    
    def _determine_issue_severity(self, result_text: str, category: str) -> str:
        """Determine issue severity based on keywords and category"""
        high_severity_keywords = ['critical', 'security', 'vulnerability', 'error', 'fail']
        medium_severity_keywords = ['warning', 'deprecated', 'performance']
        
        if any(keyword in result_text for keyword in high_severity_keywords):
            return 'high'
        elif any(keyword in result_text for keyword in medium_severity_keywords):
            return 'medium'
        else:
            return 'low'
    
    def _filter_issues_by_severity(self, issues: List[Dict[str, Any]], min_severity: str) -> List[Dict[str, Any]]:
        """Filter issues based on minimum severity level"""
        severity_order = {'low': 1, 'medium': 2, 'high': 3}
        min_level = severity_order.get(min_severity, 2)
        
        return [issue for issue in issues if severity_order.get(issue.get('severity', 'low'), 1) >= min_level]
    
    def _synthesize_validation_report(self, validation_type: str, validation_results: Dict[str, Any], 
                                    issues: List[Dict[str, Any]], total_issues: int, 
                                    routing_strategy: Dict[str, Any]) -> str:
        """Synthesize validation results into a comprehensive report"""
        
        # Count issues by category and severity
        issues_by_category = {}
        issues_by_severity = {'high': 0, 'medium': 0, 'low': 0}
        
        for issue in issues:
            category = issue.get('category', 'general')
            severity = issue.get('severity', 'low')
            
            issues_by_category[category] = issues_by_category.get(category, 0) + 1
            issues_by_severity[severity] += 1
        
        # Build report sections
        report_sections = [
            "# 🔍 Validation Results",
            f"**Validation Type**: {validation_type.title()}",
            f"**Validation Scope**: {routing_strategy['validation_scope']}",
            f"**Severity Filter**: {routing_strategy['severity_filter']}",
            "",
            "## 📊 Validation Summary",
            f"- **Total Issues Found**: {total_issues}",
            f"- **Issues After Filtering**: {len(issues)}",
            f"- **Critical (High)**: {issues_by_severity['high']}",
            f"- **Moderate (Medium)**: {issues_by_severity['medium']}",
            f"- **Minor (Low)**: {issues_by_severity['low']}",
            ""
        ]
        
        # Add category breakdown
        if issues_by_category:
            report_sections.extend([
                "## 📋 Issues by Category",
                *[f"- **{category.title()}**: {count} issues" for category, count in issues_by_category.items()],
                ""
            ])
        
        # Add detailed analysis sections
        if 'quality' in validation_results:
            report_sections.extend([
                "## 🔍 Quality Analysis",
                str(validation_results['quality']),
                ""
            ])
        
        if 'security_config' in validation_results:
            report_sections.extend([
                "## 🔒 Security Configuration",
                str(validation_results['security_config']),
                ""
            ])
        
        if 'consistency' in validation_results:
            report_sections.extend([
                "## 📏 Interface Consistency",
                str(validation_results['consistency']),
                ""
            ])
        
        if 'performance' in validation_results:
            report_sections.extend([
                "## ⚡ Performance Analysis",
                str(validation_results['performance']),
                ""
            ])
        
        if 'api_contracts' in validation_results:
            report_sections.extend([
                "## 🔌 API Contract Validation",
                str(validation_results['api_contracts']),
                ""
            ])
        
        if 'database' in validation_results:
            report_sections.extend([
                "## 🗃️ Database Schema Validation",
                str(validation_results['database']),
                ""
            ])
        
        if 'test_coverage' in validation_results:
            report_sections.extend([
                "## 🧪 Test Coverage Analysis",
                str(validation_results['test_coverage']),
                ""
            ])
        
        if 'dependencies' in validation_results:
            report_sections.extend([
                "## 🔗 Dependency Analysis",
                str(validation_results['dependencies']),
                ""
            ])
        
        if 'architecture' in validation_results:
            report_sections.extend([
                "## 🏗️ Architectural Review",
                str(validation_results['architecture']),
                ""
            ])
        
        # Add validation conclusions
        if issues_by_severity['high'] > 0:
            report_sections.extend([
                "## ⚠️ Critical Issues Detected",
                f"Found {issues_by_severity['high']} critical issues that require immediate attention.",
                "**Recommendation**: Address critical issues before deployment.",
                ""
            ])
        elif issues_by_severity['medium'] > 0:
            report_sections.extend([
                "## ⚡ Moderate Issues Detected", 
                f"Found {issues_by_severity['medium']} moderate issues that should be addressed.",
                "**Recommendation**: Plan to resolve moderate issues in next iteration.",
                ""
            ])
        else:
            report_sections.extend([
                "## ✅ Validation Passed",
                "No critical or moderate issues detected in the specified scope.",
                "**Recommendation**: Continue with current quality standards.",
                ""
            ])
        
        return "\n".join(report_sections)