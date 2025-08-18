"""
Full Analysis Tool - Enhanced comprehensive orchestration tool for complex scenarios
Coordinates multiple smart tools for better analysis coverage and synthesis
"""
from typing import List, Dict, Any, Optional
from .base_smart_tool import BaseSmartTool, SmartToolResult
from .executive_synthesizer import ExecutiveSynthesizer


class FullAnalysisTool(BaseSmartTool):
    """
    Smart tool for comprehensive multi-faceted analysis
    Orchestrates other smart tools and specialized engines based on focus area
    """
    
    def __init__(self, engines: Dict[str, Any], smart_tools: Optional[Dict[str, Any]] = None):
        """
        Initialize with both engines and other smart tools for coordination
        """
        super().__init__(engines)
        self.smart_tools = smart_tools or {}
        self.executive_synthesizer = ExecutiveSynthesizer(engines)
    
    def get_routing_strategy(self, files: List[str], focus: str = "all", autonomous: bool = False,
                           context: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Determine comprehensive analysis strategy based on focus and requirements
        """
        smart_tools_to_use = []
        engines_to_use = []
        routing_explanation = []
        
        # Autonomous vs Dialogue mode
        analysis_mode = "autonomous" if autonomous else "dialogue"
        routing_explanation.append(f"Running in {analysis_mode} mode")
        
        # Focus-based routing
        if focus in ["all", "architecture"]:
            smart_tools_to_use.append("understand")
            routing_explanation.append("Adding understand tool for architectural comprehension")
        
        if focus in ["all", "quality"]:
            smart_tools_to_use.append("validate")
            routing_explanation.append("Adding validate tool for quality assurance")
        
        if focus in ["all", "security"]:
            smart_tools_to_use.append("validate")  # Validate handles security
            engines_to_use.extend(["check_quality", "config_validator"])
            routing_explanation.append("Adding security-focused validation and analysis")
        
        if focus in ["all", "performance"]:
            smart_tools_to_use.append("validate")  # Validate handles performance
            engines_to_use.extend(["performance_profiler", "analyze_logs"])
            routing_explanation.append("Adding performance analysis and profiling")
        
        # Always add dependency and test coverage analysis for comprehensive review
        if focus == "all":
            engines_to_use.extend(["map_dependencies", "analyze_test_coverage"])
            routing_explanation.append("Adding dependency mapping and test coverage analysis")
        
        # Context-based additional analysis
        if context and any(keyword in context.lower() for keyword in ["problem", "issue", "bug", "error"]):
            smart_tools_to_use.append("investigate")
            routing_explanation.append("Context indicates issues - adding investigation")
        
        # Always add the core full_analysis engine from original system
        engines_to_use.append("full_analysis")
        routing_explanation.append("Including original full_analysis engine for comprehensive baseline")
        
        # Remove duplicates
        smart_tools_to_use = list(dict.fromkeys(smart_tools_to_use))
        engines_to_use = list(dict.fromkeys(engines_to_use))
        
        return {
            'smart_tools': smart_tools_to_use,
            'engines': engines_to_use,
            'explanation': '; '.join(routing_explanation),
            'analysis_mode': analysis_mode,
            'focus_area': focus,
            'coordination_strategy': self._determine_coordination_strategy(smart_tools_to_use, engines_to_use)
        }
    
    def _determine_coordination_strategy(self, smart_tools: List[str], engines: List[str]) -> str:
        """Determine how to coordinate multiple analysis phases"""
        if len(smart_tools) > 1:
            return "multi_smart_tool_coordination"
        elif len(smart_tools) == 1 and len(engines) > 1:
            return "smart_tool_plus_engines"
        elif len(engines) > 1:
            return "multi_engine_coordination"
        else:
            return "single_tool_analysis"
    
    async def execute(self, files: List[str], focus: str = "all", autonomous: bool = False,
                     context: Optional[str] = None, **kwargs) -> SmartToolResult:
        """
        Execute comprehensive analysis using coordinated smart tools and engines
        """
        try:
            routing_strategy = self.get_routing_strategy(
                files=files, focus=focus, autonomous=autonomous, context=context, **kwargs
            )
            
            analysis_results = {}
            total_engines_used = []
            
            # Phase 1: Smart Tools Coordination
            for smart_tool_name in routing_strategy['smart_tools']:
                if smart_tool_name in self.smart_tools:
                    tool_result = await self._execute_smart_tool(smart_tool_name, files, focus, context, **kwargs)
                    analysis_results[f"smart_tool_{smart_tool_name}"] = tool_result
                    if hasattr(tool_result, 'engines_used'):
                        total_engines_used.extend(tool_result.engines_used)
            
            # Phase 2: Direct Engine Execution
            for engine_name in routing_strategy['engines']:
                if engine_name == "full_analysis":
                    # Use original full_analysis with our parameters
                    engine_result = await self.execute_engine(
                        'full_analysis',
                        files=files,
                        focus=focus,
                        autonomous=autonomous,
                        context=context
                    )
                    analysis_results['original_full_analysis'] = engine_result
                    total_engines_used.append(engine_name)
                
                elif engine_name == "check_quality":
                    quality_focus = "security" if focus == "security" else "performance" if focus == "performance" else "all"
                    quality_result = await self.execute_engine(
                        'check_quality',
                        paths=files,
                        check_type=quality_focus,
                        verbose=True
                    )
                    analysis_results['quality_analysis'] = quality_result
                    total_engines_used.append(engine_name)
                
                elif engine_name == "config_validator":
                    config_result = await self.execute_engine(
                        'config_validator',
                        config_paths=files,
                        validation_type="security"
                    )
                    analysis_results['config_validation'] = config_result
                    total_engines_used.append(engine_name)
                
                elif engine_name == "performance_profiler":
                    perf_result = await self.execute_engine(
                        'performance_profiler',
                        target_operation="comprehensive_analysis"
                    )
                    analysis_results['performance_profiling'] = perf_result
                    total_engines_used.append(engine_name)
                
                elif engine_name == "analyze_logs":
                    log_result = await self.execute_engine(
                        'analyze_logs',
                        log_paths=files,
                        focus="all"
                    )
                    analysis_results['log_analysis'] = log_result
                    total_engines_used.append(engine_name)
                
                elif engine_name == "map_dependencies":
                    dep_result = await self.execute_engine(
                        'map_dependencies',
                        project_paths=files,
                        analysis_depth="full"
                    )
                    analysis_results['dependency_mapping'] = dep_result
                    total_engines_used.append(engine_name)
                
                elif engine_name == "analyze_test_coverage":
                    test_result = await self.execute_engine(
                        'analyze_test_coverage',
                        source_paths=files
                    )
                    analysis_results['test_coverage'] = test_result
                    total_engines_used.append(engine_name)
            
            # Phase 3: Correlation Analysis
            correlation_data = None
            if len(analysis_results) > 1:
                # Extract raw results from smart tool results
                raw_results = {}
                for key, result in analysis_results.items():
                    if hasattr(result, 'result'):
                        raw_results[key] = result.result
                    else:
                        raw_results[key] = result
                
                correlation_data = await self.analyze_correlations(raw_results)
            
            # Phase 4: Synthesis and Coordination
            comprehensive_report = self._synthesize_comprehensive_analysis(
                analysis_results, routing_strategy, files, focus, autonomous
            )
            
            # Add correlation insights to report
            if correlation_data:
                correlation_report = self.format_correlation_report(correlation_data)
                if correlation_report:
                    # Insert correlation analysis before recommendations
                    report_lines = comprehensive_report.split('\n')
                    insert_idx = next((i for i, line in enumerate(report_lines) 
                                     if '## 📋 Comprehensive Recommendations' in line), len(report_lines))
                    report_lines.insert(insert_idx, correlation_report)
                    comprehensive_report = '\n'.join(report_lines)
            
            # Apply executive synthesis for better consolidated response
            if self.executive_synthesizer.should_synthesize(self.tool_name):
                original_request = {
                    'files': files,
                    'focus': focus,
                    'autonomous': autonomous,
                    'context': context,
                    **kwargs
                }
                comprehensive_report = await self.executive_synthesizer.synthesize(
                    tool_name=self.tool_name,
                    raw_results=comprehensive_report,
                    original_request=original_request
                )
            
            # Remove duplicates from engines used
            total_engines_used = list(dict.fromkeys(total_engines_used))
            
            # Extract correlation details for result
            correlations = None
            conflicts = None  
            resolutions = None
            if correlation_data:
                correlations = correlation_data.get('correlations')
                conflicts = correlation_data.get('conflicts')
                resolutions = correlation_data.get('resolutions')
            
            return SmartToolResult(
                tool_name="full_analysis",
                success=True,
                result=comprehensive_report,
                engines_used=total_engines_used,
                routing_decision=routing_strategy['explanation'],
                metadata={
                    "files_analyzed": len(files),
                    "focus_area": focus,
                    "analysis_mode": routing_strategy['analysis_mode'],
                    "coordination_strategy": routing_strategy['coordination_strategy'],
                    "smart_tools_used": len(routing_strategy['smart_tools']),
                    "engines_used": len(routing_strategy['engines']),
                    "analysis_phases": len(analysis_results),
                    "autonomous_mode": autonomous
                },
                correlations=correlations,
                conflicts=conflicts,
                resolutions=resolutions
            )
            
        except Exception as e:
            return SmartToolResult(
                tool_name="full_analysis",
                success=False,
                result=f"Comprehensive analysis failed: {str(e)}",
                engines_used=total_engines_used if 'total_engines_used' in locals() else [],
                routing_decision=routing_strategy['explanation'] if 'routing_strategy' in locals() else "Failed during routing",
                metadata={"error": str(e)}
            )
    
    async def _execute_smart_tool(self, tool_name: str, files: List[str], focus: str, 
                                 context: Optional[str], **kwargs) -> SmartToolResult:
        """Execute a smart tool with appropriate parameters"""
        tool = self.smart_tools.get(tool_name)
        if not tool:
            return SmartToolResult(
                tool_name=tool_name,
                success=False,
                result=f"Smart tool {tool_name} not available",
                engines_used=[],
                routing_decision="Tool not found"
            )
        
        try:
            if tool_name == "understand":
                return await tool.execute(files=files, focus="architecture", question=context)
            elif tool_name == "validate":
                validation_type = focus if focus in ["security", "performance", "quality"] else "all"
                return await tool.execute(files=files, validation_type=validation_type)
            elif tool_name == "investigate":
                return await tool.execute(files=files, problem=context or "General analysis", focus="root_cause")
            else:
                return await tool.execute(files=files, **kwargs)
                
        except Exception as e:
            return SmartToolResult(
                tool_name=tool_name,
                success=False,
                result=f"Smart tool execution failed: {str(e)}",
                engines_used=[],
                routing_decision="Execution error"
            )
    
    def _synthesize_comprehensive_analysis(self, analysis_results: Dict[str, Any], 
                                         routing_strategy: Dict[str, Any], files: List[str],
                                         focus: str, autonomous: bool) -> str:
        """
        Synthesize all analysis results into a comprehensive report
        """
        synthesis_sections = []
        
        # Header
        mode = "Autonomous" if autonomous else "Dialogue"
        synthesis_sections.extend([
            f"# 🚀 Comprehensive Analysis Results ({mode} Mode)",
            f"**Focus Area**: {focus.title()}",
            f"**Files Analyzed**: {len(files)}",
            f"**Coordination Strategy**: {routing_strategy['coordination_strategy']}",
            f"**Analysis Approach**: {routing_strategy['explanation']}",
            ""
        ])
        
        # Executive Summary
        synthesis_sections.extend([
            "## 📊 Executive Summary",
            f"Completed comprehensive {focus} analysis using {len(analysis_results)} specialized analysis phases.",
            f"Analysis coordinated {len(routing_strategy['smart_tools'])} smart tools and {len(routing_strategy['engines'])} specialized engines.",
            ""
        ])
        
        # Smart Tools Results
        smart_tool_results = {k: v for k, v in analysis_results.items() if k.startswith('smart_tool_')}
        if smart_tool_results:
            synthesis_sections.extend([
                "## 🧠 Smart Tools Analysis",
                ""
            ])
            
            for tool_key, result in smart_tool_results.items():
                tool_name = tool_key.replace('smart_tool_', '').title()
                synthesis_sections.extend([
                    f"### {tool_name} Tool Results",
                    f"**Success**: {'✅' if result.success else '❌'}",
                    f"**Engines Used**: {', '.join(result.engines_used) if result.engines_used else 'None'}",
                    "",
                    str(result.result),
                    ""
                ])
        
        # Engine Results
        engine_results = {k: v for k, v in analysis_results.items() if not k.startswith('smart_tool_')}
        if engine_results:
            synthesis_sections.extend([
                "## ⚙️ Specialized Engine Analysis",
                ""
            ])
            
            for engine_key, result in engine_results.items():
                engine_name = engine_key.replace('_', ' ').title()
                synthesis_sections.extend([
                    f"### {engine_name}",
                    str(result),
                    ""
                ])
        
        # Cross-Analysis Insights
        synthesis_sections.extend([
            "## 🔍 Cross-Analysis Insights",
            self._generate_cross_analysis_insights(analysis_results, focus),
            ""
        ])
        
        # Recommendations
        synthesis_sections.extend([
            "## 📋 Comprehensive Recommendations",
            self._generate_comprehensive_recommendations(analysis_results, focus, autonomous),
            ""
        ])
        
        # Next Steps
        if not autonomous:
            synthesis_sections.extend([
                "## 🗣️ Continue Analysis",
                "This comprehensive analysis provides a foundation. You can:",
                "- Ask for deeper investigation of specific findings",
                "- Request focused analysis on particular areas",
                "- Explore specific recommendations in detail",
                "- Run additional validation or investigation",
                ""
            ])
        
        return "\n".join(synthesis_sections)
    
    def _generate_cross_analysis_insights(self, results: Dict[str, Any], focus: str) -> str:
        """Generate insights by looking across all analysis results"""
        insights = []
        
        # Count successful vs failed analyses
        successes = sum(1 for r in results.values() if hasattr(r, 'success') and r.success)
        total = len(results)
        
        insights.append(f"- **Analysis Coverage**: {successes}/{total} analysis phases completed successfully")
        
        # Look for common themes based on focus
        if focus == "security":
            insights.extend([
                "- Security analysis combines configuration validation, quality checks, and smart validation",
                "- Cross-reference security findings across different analysis layers",
                "- Prioritize critical security issues identified by multiple tools"
            ])
        elif focus == "performance":
            insights.extend([
                "- Performance analysis includes profiling, quality metrics, and dependency analysis", 
                "- Look for performance bottlenecks identified by multiple analysis methods",
                "- Consider architectural changes suggested by different tools"
            ])
        elif focus == "architecture":
            insights.extend([
                "- Architectural analysis combines understanding, validation, and dependency mapping",
                "- Review consistency between different architectural perspectives",
                "- Consider refactoring suggestions from multiple analysis angles"
            ])
        else:
            insights.extend([
                "- Comprehensive analysis provides multiple perspectives on the same codebase",
                "- Look for patterns and issues identified by multiple analysis methods",
                "- Consider the intersection of different analysis findings for priority"
            ])
        
        return "\n".join(insights)
    
    def _generate_comprehensive_recommendations(self, results: Dict[str, Any], focus: str, autonomous: bool) -> str:
        """Generate comprehensive recommendations based on all results"""
        recommendations = []
        
        if autonomous:
            recommendations.extend([
                "**Immediate Actions:**",
                "1. Review all critical issues identified across analysis phases",
                "2. Prioritize fixes based on security and performance impact",
                "3. Address architectural concerns highlighted by multiple tools",
                "",
                "**Strategic Improvements:**",
                "1. Implement suggested architectural enhancements",
                "2. Improve test coverage in areas identified by analysis",
                "3. Establish monitoring for performance metrics identified",
                "",
                "**Quality Assurance:**",
                "1. Set up automated validation for identified quality issues",
                "2. Create documentation for architectural decisions",
                "3. Implement security best practices from configuration analysis"
            ])
        else:
            recommendations.extend([
                "**Interactive Next Steps:**",
                "1. Discuss specific findings that need clarification",
                "2. Dive deeper into areas that show potential issues",
                "3. Explore implementation strategies for suggested improvements",
                "",
                "**Collaboration Opportunities:**",
                "1. Use collaborate tool to review specific code sections",
                "2. Use investigate tool to explore any concerning findings",
                "3. Use validate tool to check fixes and improvements",
                "",
                "**Continuous Analysis:**",
                "1. Re-run analysis after implementing changes",
                "2. Focus future analysis on areas of highest concern",
                "3. Track progress on recommendations over time"
            ])
        
        return "\n".join(recommendations)