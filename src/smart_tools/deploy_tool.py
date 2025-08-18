"""
Deploy Tool - Smart tool for pre-deployment validation and readiness checks
Routes to config_validator + api_contract_checker for deployment safety
"""
from typing import List, Dict, Any, Optional
from .base_smart_tool import BaseSmartTool, SmartToolResult
from .executive_synthesizer import ExecutiveSynthesizer


class DeployTool(BaseSmartTool):
    """
    Smart tool for pre-deployment validation and readiness assessment
    Intelligently routes to configuration and API contract validation engines
    """
    
    def __init__(self, engines: Dict[str, Any]):
        super().__init__(engines)
        self.executive_synthesizer = ExecutiveSynthesizer(engines)
    
    def get_routing_strategy(self, files: List[str], deployment_stage: str = "production", 
                           validation_level: str = "comprehensive", **kwargs) -> Dict[str, Any]:
        """
        Determine which engines to use for deployment validation
        """
        engines_to_use = []
        routing_explanation = []
        
        # Always validate configuration for deployment
        engines_to_use.append('config_validator')
        routing_explanation.append(f"Configuration validation enabled for {deployment_stage} deployment")
        
        # API contract validation for service deployments
        api_files = self._detect_api_files(files)
        if api_files:
            engines_to_use.append('api_contract_checker')
            routing_explanation.append(f"API contract validation enabled for {len(api_files)} API specifications")
        
        # Security validation for production deployments
        if deployment_stage in ['production', 'staging']:
            engines_to_use.append('check_quality')
            routing_explanation.append(f"Security quality checks enabled for {deployment_stage} deployment")
        
        # Performance validation for production
        if deployment_stage == 'production' and validation_level == 'comprehensive':
            engines_to_use.append('performance_profiler')
            routing_explanation.append("Performance profiling enabled for production deployment")
        
        # Database validation for schema changes
        db_files = self._detect_database_files(files)
        if db_files:
            engines_to_use.append('analyze_database')
            routing_explanation.append(f"Database validation enabled for {len(db_files)} database files")
        
        return {
            'engines': engines_to_use,
            'explanation': '; '.join(routing_explanation),
            'deployment_stage': deployment_stage,
            'validation_scope': self._determine_validation_scope(deployment_stage, validation_level)
        }
    
    def _detect_api_files(self, files: List[str]) -> List[str]:
        """Detect API specification files"""
        api_extensions = ['.json', '.yaml', '.yml']
        api_keywords = ['api', 'swagger', 'openapi', 'spec', 'schema']
        
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
        db_keywords = ['schema', 'migration', 'model', 'database', 'ddl']
        
        db_files = []
        for file_path in files:
            file_lower = file_path.lower()
            if (any(file_lower.endswith(ext) for ext in db_extensions) or 
                any(keyword in file_lower for keyword in db_keywords)):
                db_files.append(file_path)
        
        return db_files
    
    def _determine_validation_scope(self, deployment_stage: str, validation_level: str) -> str:
        """Determine the scope of deployment validation"""
        scope_elements = []
        
        if deployment_stage == 'production':
            scope_elements.append("production-grade security")
        elif deployment_stage == 'staging':
            scope_elements.append("staging environment compatibility")
        else:
            scope_elements.append("development deployment safety")
        
        if validation_level == 'comprehensive':
            scope_elements.append("comprehensive validation")
        elif validation_level == 'essential':
            scope_elements.append("essential checks only")
        else:
            scope_elements.append("standard validation")
        
        scope_elements.extend(["configuration integrity", "API contract compliance"])
        
        return f"{deployment_stage} deployment with {', '.join(scope_elements)}"
    
    async def execute(self, files: List[str], deployment_stage: str = "production", 
                     validation_level: str = "comprehensive", environment: str = None, **kwargs) -> SmartToolResult:
        """
        Execute deployment validation using coordinated multi-engine analysis
        """
        try:
            routing_strategy = self.get_routing_strategy(
                files=files, deployment_stage=deployment_stage, 
                validation_level=validation_level, **kwargs
            )
            engines_used = routing_strategy['engines']
            
            deployment_results = {}
            validation_issues = []
            critical_blockers = []
            
            # Phase 1: Configuration Validation - Critical for all deployments
            if 'config_validator' in engines_used:
                config_files = self._find_config_files(files)
                if config_files:
                    config_result = await self.execute_engine(
                        'config_validator',
                        config_paths=config_files,
                        validation_type="all"  # Comprehensive config validation
                    )
                    deployment_results['configuration'] = config_result
                    config_issues = self._extract_deployment_issues(config_result, "configuration", deployment_stage)
                    validation_issues.extend(config_issues)
                    critical_blockers.extend([issue for issue in config_issues if issue.get('severity') == 'critical'])
            
            # Phase 2: API Contract Validation - Ensure API compatibility
            if 'api_contract_checker' in engines_used:
                api_files = self._detect_api_files(files)
                if api_files:
                    api_result = await self.execute_engine(
                        'api_contract_checker',
                        spec_paths=api_files,
                        comparison_mode="breaking_changes"
                    )
                    deployment_results['api_contracts'] = api_result
                    api_issues = self._extract_deployment_issues(api_result, "api_contracts", deployment_stage)
                    validation_issues.extend(api_issues)
                    critical_blockers.extend([issue for issue in api_issues if issue.get('severity') == 'critical'])
            
            # Phase 3: Security Quality Validation - Critical for production
            if 'check_quality' in engines_used:
                security_result = await self.execute_engine(
                    'check_quality',
                    paths=files,
                    check_type="security",
                    verbose=True
                )
                deployment_results['security'] = security_result
                security_issues = self._extract_deployment_issues(security_result, "security", deployment_stage)
                validation_issues.extend(security_issues)
                critical_blockers.extend([issue for issue in security_issues if issue.get('severity') == 'critical'])
            
            # Phase 4: Performance Validation - For production deployments
            if 'performance_profiler' in engines_used:
                perf_result = await self.execute_engine(
                    'performance_profiler',
                    target_operation="deployment_readiness",
                    profile_type="comprehensive"
                )
                deployment_results['performance'] = perf_result
                perf_issues = self._extract_deployment_issues(perf_result, "performance", deployment_stage)
                validation_issues.extend(perf_issues)
            
            # Phase 5: Database Validation - For schema/migration deployments
            if 'analyze_database' in engines_used:
                db_files = self._detect_database_files(files)
                if db_files:
                    db_result = await self.execute_engine(
                        'analyze_database',
                        schema_paths=db_files,
                        analysis_type="schema"
                    )
                    deployment_results['database'] = db_result
                    db_issues = self._extract_deployment_issues(db_result, "database", deployment_stage)
                    validation_issues.extend(db_issues)
                    critical_blockers.extend([issue for issue in db_issues if issue.get('severity') == 'critical'])
            
            # Determine deployment readiness
            deployment_ready = len(critical_blockers) == 0
            
            # Generate deployment readiness report
            deployment_report = self._synthesize_deployment_report(
                deployment_stage, deployment_ready, deployment_results, 
                validation_issues, critical_blockers, routing_strategy
            )
            
            # Apply executive synthesis for deployment decision guidance
            if self.executive_synthesizer.should_synthesize(self.tool_name):
                original_request = {
                    'files': files,
                    'deployment_stage': deployment_stage,
                    'validation_level': validation_level,
                    'environment': environment,
                    **kwargs
                }
                deployment_report = await self.executive_synthesizer.synthesize(
                    tool_name=self.tool_name,
                    raw_results=deployment_report,
                    original_request=original_request
                )
            
            return SmartToolResult(
                tool_name="deploy",
                success=deployment_ready,
                result=deployment_report,
                engines_used=engines_used,
                routing_decision=routing_strategy['explanation'],
                metadata={
                    "files_analyzed": len(files),
                    "deployment_stage": deployment_stage,
                    "validation_level": validation_level,
                    "deployment_ready": deployment_ready,
                    "total_issues": len(validation_issues),
                    "critical_blockers": len(critical_blockers),
                    "phases_completed": len(deployment_results)
                }
            )
            
        except Exception as e:
            return SmartToolResult(
                tool_name="deploy",
                success=False,
                result=f"Deployment validation failed: {str(e)}",
                engines_used=engines_used if 'engines_used' in locals() else [],
                routing_decision=routing_strategy['explanation'] if 'routing_strategy' in locals() else "Failed during routing",
                metadata={"error": str(e)}
            )
    
    def _find_config_files(self, files: List[str]) -> List[str]:
        """Find configuration files in the file list"""
        config_patterns = ['.env', 'config.', 'settings.', '.json', '.yaml', '.yml', '.toml', '.ini', 'docker', 'k8s', 'helm']
        config_files = []
        
        for file_path in files:
            file_lower = file_path.lower()
            if any(pattern in file_lower for pattern in config_patterns):
                config_files.append(file_path)
        
        return config_files
    
    def _extract_deployment_issues(self, result: str, category: str, deployment_stage: str) -> List[Dict[str, Any]]:
        """Extract deployment-blocking issues from engine results"""
        issues = []
        result_lower = str(result).lower()
        
        # Critical deployment blockers
        critical_keywords = ['critical', 'error', 'fail', 'security', 'vulnerability', 'breaking']
        if any(keyword in result_lower for keyword in critical_keywords):
            severity = 'critical' if deployment_stage == 'production' else 'high'
            issues.append({
                'category': category,
                'severity': severity,
                'description': f"{category.title()} validation identified potential deployment blocker",
                'deployment_impact': 'Blocks deployment until resolved'
            })
        
        # Warning-level issues
        warning_keywords = ['warning', 'deprecated', 'recommendation', 'improvement']
        if any(keyword in result_lower for keyword in warning_keywords):
            issues.append({
                'category': category,
                'severity': 'medium',
                'description': f"{category.title()} validation found deployment concerns",
                'deployment_impact': 'Should be addressed before deployment'
            })
        
        return issues
    
    def _synthesize_deployment_report(self, deployment_stage: str, deployment_ready: bool,
                                    deployment_results: Dict[str, Any], validation_issues: List[Dict[str, Any]],
                                    critical_blockers: List[Dict[str, Any]], routing_strategy: Dict[str, Any]) -> str:
        """Synthesize deployment validation results into actionable report"""
        
        # Deployment status header
        status_emoji = "✅" if deployment_ready else "🚨"
        status_text = "READY FOR DEPLOYMENT" if deployment_ready else "DEPLOYMENT BLOCKED"
        
        report_sections = [
            f"# {status_emoji} Deployment Validation Results",
            f"**Status**: {status_text}",
            f"**Target Stage**: {deployment_stage.title()}",
            f"**Validation Scope**: {routing_strategy['validation_scope']}",
            ""
        ]
        
        # Executive Summary
        report_sections.extend([
            "## 📊 Deployment Readiness Summary",
            f"- **Deployment Ready**: {'Yes' if deployment_ready else 'No'}",
            f"- **Critical Blockers**: {len(critical_blockers)}",
            f"- **Total Issues**: {len(validation_issues)}",
            f"- **Validation Phases**: {len(deployment_results)}",
            ""
        ])
        
        # Critical Blockers (if any)
        if critical_blockers:
            report_sections.extend([
                "## 🚨 Critical Deployment Blockers",
                "**Must be resolved before deployment:**",
                ""
            ])
            for i, blocker in enumerate(critical_blockers, 1):
                report_sections.append(f"{i}. **{blocker['category'].title()}**: {blocker['description']}")
                report_sections.append(f"   - Impact: {blocker['deployment_impact']}")
                report_sections.append("")
        
        # Validation Results by Category
        if 'configuration' in deployment_results:
            report_sections.extend([
                "## ⚙️ Configuration Validation",
                str(deployment_results['configuration']),
                ""
            ])
        
        if 'api_contracts' in deployment_results:
            report_sections.extend([
                "## 🔌 API Contract Validation",
                str(deployment_results['api_contracts']),
                ""
            ])
        
        if 'security' in deployment_results:
            report_sections.extend([
                "## 🔒 Security Validation",
                str(deployment_results['security']),
                ""
            ])
        
        if 'performance' in deployment_results:
            report_sections.extend([
                "## ⚡ Performance Validation",
                str(deployment_results['performance']),
                ""
            ])
        
        if 'database' in deployment_results:
            report_sections.extend([
                "## 🗃️ Database Validation",
                str(deployment_results['database']),
                ""
            ])
        
        # Deployment Recommendations
        if deployment_ready:
            report_sections.extend([
                "## 🚀 Deployment Recommendations",
                f"✅ **Ready for {deployment_stage} deployment**",
                "- All critical validations passed",
                "- No deployment blockers detected",
                "- Proceed with deployment following standard procedures",
                ""
            ])
        else:
            report_sections.extend([
                "## ⚠️ Required Actions Before Deployment",
                f"❌ **Not ready for {deployment_stage} deployment**",
                f"- Resolve {len(critical_blockers)} critical blocker(s)",
                f"- Address {len(validation_issues) - len(critical_blockers)} additional issue(s)",
                "- Re-run deployment validation after fixes",
                ""
            ])
        
        # Next Steps
        report_sections.extend([
            "## 🎯 Next Steps",
            "1. **Review Validation Results**: Address any issues identified above",
            "2. **Fix Critical Blockers**: Resolve deployment-blocking issues first",
            "3. **Re-validate**: Run deployment validation again after fixes",
            "4. **Monitor Deployment**: Track deployment success and rollback if needed",
            ""
        ])
        
        return "\n".join(report_sections)