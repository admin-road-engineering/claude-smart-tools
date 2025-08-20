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
        Execute comprehensive validation using parallel multi-engine analysis
        """
        import asyncio
        
        try:
            routing_strategy = self.get_routing_strategy(
                files=files, validation_type=validation_type, severity=severity, **kwargs
            )
            engines_used = routing_strategy['engines']
            
            validation_results = {}
            issues_found = []
            total_issues = 0
            
            # Pre-compute file categories for engines
            config_files = self._find_config_files(files)
            source_files = self._detect_source_files(files)
            api_files = self._detect_api_files(files)
            db_files = self._detect_database_files(files)
            quality_focus = self._map_validation_to_quality_focus(validation_type)
            
            # Group engines into parallel execution batches
            # Batch 1: Independent analysis engines (can run in parallel)
            parallel_tasks = []
            
            if 'check_quality' in engines_used:
                parallel_tasks.append(self._run_quality_analysis(files, quality_focus))
            
            if 'config_validator' in engines_used and config_files:
                parallel_tasks.append(self._run_config_validation(config_files))
            
            if 'interface_inconsistency_detector' in engines_used and source_files:
                parallel_tasks.append(self._run_consistency_analysis(source_files))
            
            if 'api_contract_checker' in engines_used and api_files:
                parallel_tasks.append(self._run_api_validation(api_files))
            
            if 'analyze_database' in engines_used and db_files:
                parallel_tasks.append(self._run_database_analysis(db_files))
            
            if 'analyze_test_coverage' in engines_used and source_files:
                parallel_tasks.append(self._run_test_coverage_analysis(source_files))
            
            # Execute independent engines in parallel
            if parallel_tasks:
                parallel_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
                
                # Process parallel results
                for result in parallel_results:
                    if isinstance(result, Exception):
                        # Log error but continue with other results
                        import logging
                        logging.getLogger(__name__).error(f"Parallel validation task failed: {result}")
                    elif isinstance(result, dict):
                        # Merge successful results
                        for category, data in result.items():
                            validation_results[category] = data['result']
                            if 'issues' in data:
                                issues_found.extend(data['issues'])
                                total_issues += len(data['issues'])
            
            # Batch 2: Dependent engines (run after file analysis)
            dependent_tasks = []
            
            if 'performance_profiler' in engines_used:
                dependent_tasks.append(self._run_performance_analysis())
            
            if 'map_dependencies' in engines_used:
                dependent_tasks.append(self._run_dependency_analysis(files))
            
            if 'analyze_code' in engines_used:
                dependent_tasks.append(self._run_architectural_analysis(files))
            
            # Execute dependent engines in parallel
            if dependent_tasks:
                dependent_results = await asyncio.gather(*dependent_tasks, return_exceptions=True)
                
                # Process dependent results
                for result in dependent_results:
                    if isinstance(result, Exception):
                        import logging
                        logging.getLogger(__name__).error(f"Dependent validation task failed: {result}")
                    elif isinstance(result, dict):
                        for category, data in result.items():
                            validation_results[category] = data['result']
                            if 'issues' in data:
                                issues_found.extend(data['issues'])
                                total_issues += len(data['issues'])
            
            # Filter issues by severity
            filtered_issues = self._filter_issues_by_severity(issues_found, severity)
            
            # Perform correlation analysis on validation results
            correlation_data = None
            if len(validation_results) > 1:
                correlation_data = await self.analyze_correlations(validation_results)
            
            # Generate validation report
            validation_report = self._synthesize_validation_report(
                validation_type, validation_results, filtered_issues, total_issues, routing_strategy
            )
            
            # Add correlation report if available
            if correlation_data:
                correlation_report = self.format_correlation_report(correlation_data)
                if correlation_report:
                    validation_report += "\n\n" + correlation_report
            
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
            
            # Extract correlation summary for result
            correlations = None
            conflicts = None
            resolutions = None
            if correlation_data:
                correlations = correlation_data.get('correlations')
                conflicts = correlation_data.get('conflicts')
                resolutions = correlation_data.get('resolutions')
            
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
                    "phases_completed": len(validation_results),
                    "performance_mode": "parallel",
                    "parallel_batches": 2
                },
                correlations=correlations,
                conflicts=conflicts,
                resolutions=resolutions
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
    
    # Parallel execution helper methods
    async def _run_quality_analysis(self, files: List[str], quality_focus: str) -> Dict[str, Any]:
        """Run quality analysis in parallel batch"""
        try:
            result = await self.execute_engine(
                'check_quality',
                paths=files,
                check_type=quality_focus,
                verbose=True
            )
            issues = self._extract_issues_from_result(result, "quality")
            return {'quality': {'result': result, 'issues': issues}}
        except Exception as e:
            return {'quality': {'result': f"Quality analysis failed: {str(e)}", 'issues': []}}
    
    async def _run_config_validation(self, config_files: List[str]) -> Dict[str, Any]:
        """Run config validation in parallel batch"""
        try:
            result = await self.execute_engine(
                'config_validator',
                config_paths=config_files,
                validation_type="security"
            )
            issues = self._extract_issues_from_result(result, "security")
            return {'security_config': {'result': result, 'issues': issues}}
        except Exception as e:
            return {'security_config': {'result': f"Config validation failed: {str(e)}", 'issues': []}}
    
    async def _run_consistency_analysis(self, source_files: List[str]) -> Dict[str, Any]:
        """Run consistency analysis in parallel batch"""
        try:
            result = await self.execute_engine(
                'interface_inconsistency_detector',
                source_paths=source_files,
                pattern_types=["naming", "parameters", "return_types"]
            )
            issues = self._extract_issues_from_result(result, "consistency")
            return {'consistency': {'result': result, 'issues': issues}}
        except Exception as e:
            return {'consistency': {'result': f"Consistency analysis failed: {str(e)}", 'issues': []}}
    
    async def _run_api_validation(self, api_files: List[str]) -> Dict[str, Any]:
        """Run API validation in parallel batch"""
        try:
            result = await self.execute_engine(
                'api_contract_checker',
                spec_paths=api_files,
                comparison_mode="standalone"
            )
            issues = self._extract_issues_from_result(result, "api")
            return {'api_contracts': {'result': result, 'issues': issues}}
        except Exception as e:
            return {'api_contracts': {'result': f"API validation failed: {str(e)}", 'issues': []}}
    
    async def _run_database_analysis(self, db_files: List[str]) -> Dict[str, Any]:
        """Run database analysis in parallel batch"""
        try:
            result = await self.execute_engine(
                'analyze_database',
                schema_paths=db_files,
                analysis_type="optimization"
            )
            issues = self._extract_issues_from_result(result, "database")
            return {'database': {'result': result, 'issues': issues}}
        except Exception as e:
            return {'database': {'result': f"Database analysis failed: {str(e)}", 'issues': []}}
    
    async def _run_test_coverage_analysis(self, source_files: List[str]) -> Dict[str, Any]:
        """Run test coverage analysis in parallel batch"""
        try:
            result = await self.execute_engine(
                'analyze_test_coverage',
                source_paths=source_files
            )
            issues = self._extract_issues_from_result(result, "testing")
            return {'test_coverage': {'result': result, 'issues': issues}}
        except Exception as e:
            return {'test_coverage': {'result': f"Test coverage analysis failed: {str(e)}", 'issues': []}}
    
    async def _run_performance_analysis(self) -> Dict[str, Any]:
        """Run performance analysis in dependent batch"""
        try:
            result = await self.execute_engine(
                'performance_profiler',
                target_operation="validation_analysis"
            )
            issues = self._extract_issues_from_result(result, "performance")
            return {'performance': {'result': result, 'issues': issues}}
        except Exception as e:
            return {'performance': {'result': f"Performance analysis failed: {str(e)}", 'issues': []}}
    
    async def _run_dependency_analysis(self, files: List[str]) -> Dict[str, Any]:
        """Run dependency analysis in dependent batch"""
        try:
            result = await self.execute_engine(
                'map_dependencies',
                project_paths=files,
                analysis_depth="transitive"
            )
            issues = self._extract_issues_from_result(result, "dependencies")
            return {'dependencies': {'result': result, 'issues': issues}}
        except Exception as e:
            return {'dependencies': {'result': f"Dependency analysis failed: {str(e)}", 'issues': []}}
    
    async def _run_architectural_analysis(self, files: List[str]) -> Dict[str, Any]:
        """Run architectural analysis in dependent batch"""
        try:
            result = await self.execute_engine(
                'analyze_code',
                paths=files,
                analysis_type="refactor_prep",
                question="What potential issues exist in this code?"
            )
            issues = self._extract_issues_from_result(result, "architecture")
            return {'architecture': {'result': result, 'issues': issues}}
        except Exception as e:
            return {'architecture': {'result': f"Architectural analysis failed: {str(e)}", 'issues': []}}