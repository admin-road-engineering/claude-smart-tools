"""
Propose Tests Tool - Smart tool for test coverage analysis and test generation
Routes to analyze_code + analyze_test_coverage + search_code to identify untested areas
"""
from typing import List, Dict, Any, Optional
from .base_smart_tool import BaseSmartTool, SmartToolResult
from .executive_synthesizer import ExecutiveSynthesizer


class ProposeTestsTool(BaseSmartTool):
    """
    Smart tool for analyzing test coverage gaps and proposing test improvements
    Intelligently routes to multiple engines to identify untested code and generate test suggestions
    """
    
    def __init__(self, engines: Dict[str, Any]):
        super().__init__(engines)
        self.executive_synthesizer = ExecutiveSynthesizer(engines)
    
    def get_routing_strategy(self, files: List[str], test_type: str = "all", 
                           coverage_threshold: float = 0.8, **kwargs) -> Dict[str, Any]:
        """
        Determine which engines to use for test analysis and proposal
        """
        engines_to_use = []
        routing_explanation = []
        
        # Always start with test coverage analysis to identify gaps
        engines_to_use.append('analyze_test_coverage')
        routing_explanation.append("Starting with test coverage analysis to identify untested code")
        
        # Add code analysis to understand structure and complexity
        engines_to_use.append('analyze_code')
        routing_explanation.append("Adding code analysis to understand structure and identify high-priority test targets")
        
        # Add search capabilities to find existing test patterns
        engines_to_use.append('search_code')
        routing_explanation.append("Adding code search to identify existing test patterns and conventions")
        
        # Add quality analysis to prioritize based on code complexity
        engines_to_use.append('check_quality')
        routing_explanation.append("Adding quality analysis to prioritize testing based on code complexity and risk")
        
        return {
            'engines': engines_to_use,
            'explanation': '; '.join(routing_explanation),
            'test_focus': self._determine_test_focus(test_type),
            'coverage_target': coverage_threshold
        }
    
    def _determine_test_focus(self, test_type: str) -> str:
        """Determine the focus area for test generation"""
        focus_mapping = {
            'unit': 'individual functions and methods',
            'integration': 'component interactions and workflows',
            'security': 'authentication, authorization, and input validation',
            'performance': 'load testing and performance edge cases',
            'all': 'comprehensive coverage across all test types'
        }
        return focus_mapping.get(test_type, 'comprehensive coverage across all test types')
    
    async def execute(self, files: List[str], test_type: str = "all", 
                     coverage_threshold: float = 0.8, priority: str = "high", **kwargs) -> SmartToolResult:
        """
        Execute test analysis and proposal generation
        """
        try:
            routing_strategy = self.get_routing_strategy(
                files=files, test_type=test_type, coverage_threshold=coverage_threshold, **kwargs
            )
            engines_used = routing_strategy['engines']
            
            analysis_results = {}
            test_proposals = []
            
            # Phase 1: Test Coverage Analysis - Identify gaps
            if 'analyze_test_coverage' in engines_used:
                source_files = self._filter_source_files(files)
                if source_files:
                    coverage_result = await self.execute_engine(
                        'analyze_test_coverage',
                        source_paths=source_files
                    )
                    analysis_results['coverage'] = coverage_result
                    
                    # Extract coverage gaps for test proposals
                    coverage_gaps = self._extract_coverage_gaps(coverage_result)
                    test_proposals.extend(coverage_gaps)
            
            # Phase 2: Code Structure Analysis - Understand complexity and risk
            if 'analyze_code' in engines_used:
                code_result = await self.execute_engine(
                    'analyze_code',
                    paths=files,
                    analysis_type='refactor_prep',
                    question="What functions and methods need testing? Identify complex areas requiring comprehensive test coverage."
                )
                analysis_results['code_structure'] = code_result
                
                # Extract high-priority test targets
                priority_targets = self._extract_priority_targets(code_result, priority)
                test_proposals.extend(priority_targets)
            
            # Phase 3: Existing Test Pattern Analysis - Learn from current tests
            if 'search_code' in engines_used:
                test_patterns_result = await self.execute_engine(
                    'search_code',
                    query='test describe it expect assert mock',
                    paths=files,
                    context_question="Find existing test files and patterns to understand testing conventions",
                    output_format='text'
                )
                analysis_results['test_patterns'] = test_patterns_result
                
                # Extract testing conventions and frameworks
                test_conventions = self._extract_test_conventions(test_patterns_result)
                analysis_results['conventions'] = test_conventions
            
            # Phase 4: Quality-Based Prioritization - Focus on complex/risky code
            if 'check_quality' in engines_used:
                quality_result = await self.execute_engine(
                    'check_quality',
                    paths=files,
                    check_type='all',
                    verbose=True
                )
                analysis_results['quality'] = quality_result
                
                # Prioritize based on quality issues
                quality_priorities = self._extract_quality_priorities(quality_result)
                test_proposals.extend(quality_priorities)
            
            # Synthesize and prioritize test proposals
            test_report = self._synthesize_test_proposals(
                test_type, test_proposals, analysis_results, routing_strategy, coverage_threshold
            )
            
            # Apply executive synthesis for actionable test generation guidance
            if self.executive_synthesizer.should_synthesize(self.tool_name):
                original_request = {
                    'files': files,
                    'test_type': test_type,
                    'coverage_threshold': coverage_threshold,
                    'priority': priority,
                    **kwargs
                }
                test_report = await self.executive_synthesizer.synthesize(
                    tool_name=self.tool_name,
                    raw_results=test_report,
                    original_request=original_request
                )
            
            return SmartToolResult(
                tool_name="propose_tests",
                success=True,
                result=test_report,
                engines_used=engines_used,
                routing_decision=routing_strategy['explanation'],
                metadata={
                    "files_analyzed": len(files),
                    "test_type": test_type,
                    "coverage_threshold": coverage_threshold,
                    "priority": priority,
                    "test_proposals": len(test_proposals),
                    "phases_completed": len(analysis_results)
                }
            )
            
        except Exception as e:
            return SmartToolResult(
                tool_name="propose_tests",
                success=False,
                result=f"Test proposal generation failed: {str(e)}",
                engines_used=engines_used if 'engines_used' in locals() else [],
                routing_decision=routing_strategy['explanation'] if 'routing_strategy' in locals() else "Failed during routing",
                metadata={"error": str(e)}
            )
    
    def _filter_source_files(self, files: List[str]) -> List[str]:
        """Filter to source code files (not test files)"""
        source_extensions = ['.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.cs', '.go', '.rs', '.rb']
        test_indicators = ['test', 'spec', '__test__', '.test.', '.spec.']
        
        source_files = []
        for file_path in files:
            # Include if it's a source file but not a test file
            is_source = any(file_path.lower().endswith(ext) for ext in source_extensions)
            is_test = any(indicator in file_path.lower() for indicator in test_indicators)
            
            if is_source and not is_test:
                source_files.append(file_path)
        
        return source_files
    
    def _extract_coverage_gaps(self, coverage_result: str) -> List[Dict[str, Any]]:
        """Extract coverage gaps from test coverage analysis"""
        gaps = []
        
        # Simple heuristic to identify coverage gaps
        # In production, this would parse actual coverage reports
        result_lower = str(coverage_result).lower()
        
        if 'untested' in result_lower or 'not covered' in result_lower:
            gaps.append({
                'type': 'coverage_gap',
                'priority': 'high',
                'description': 'Untested code paths identified by coverage analysis',
                'source': 'analyze_test_coverage'
            })
        
        if 'low coverage' in result_lower or 'insufficient' in result_lower:
            gaps.append({
                'type': 'low_coverage',
                'priority': 'medium',
                'description': 'Areas with insufficient test coverage requiring additional tests',
                'source': 'analyze_test_coverage'
            })
        
        return gaps
    
    def _extract_priority_targets(self, code_result: str, priority: str) -> List[Dict[str, Any]]:
        """Extract high-priority test targets from code analysis"""
        targets = []
        result_lower = str(code_result).lower()
        
        # Identify complex functions needing tests
        if 'complex' in result_lower or 'cyclomatic' in result_lower:
            targets.append({
                'type': 'complex_function',
                'priority': 'high',
                'description': 'Complex functions with high cyclomatic complexity requiring comprehensive tests',
                'source': 'analyze_code'
            })
        
        # Identify critical business logic
        if any(keyword in result_lower for keyword in ['critical', 'important', 'core', 'business']):
            targets.append({
                'type': 'critical_logic',
                'priority': 'high',
                'description': 'Critical business logic requiring thorough testing',
                'source': 'analyze_code'
            })
        
        # Identify error-prone areas
        if any(keyword in result_lower for keyword in ['error', 'exception', 'edge case']):
            targets.append({
                'type': 'error_handling',
                'priority': 'medium',
                'description': 'Error handling and edge cases requiring validation tests',
                'source': 'analyze_code'
            })
        
        return targets
    
    def _extract_test_conventions(self, test_patterns_result: str) -> Dict[str, str]:
        """Extract testing conventions and framework information"""
        result_lower = str(test_patterns_result).lower()
        conventions = {}
        
        # Detect testing frameworks
        if 'jest' in result_lower or 'describe(' in result_lower:
            conventions['framework'] = 'Jest (JavaScript)'
        elif 'pytest' in result_lower or 'def test_' in result_lower:
            conventions['framework'] = 'pytest (Python)'
        elif 'mocha' in result_lower or 'chai' in result_lower:
            conventions['framework'] = 'Mocha/Chai (JavaScript)'
        elif 'unittest' in result_lower:
            conventions['framework'] = 'unittest (Python)'
        else:
            conventions['framework'] = 'Unknown or multiple frameworks detected'
        
        # Detect naming patterns
        if 'test_' in result_lower:
            conventions['naming'] = 'test_ prefix pattern'
        elif '.test.' in result_lower:
            conventions['naming'] = '.test. suffix pattern'
        elif '.spec.' in result_lower:
            conventions['naming'] = '.spec. suffix pattern'
        else:
            conventions['naming'] = 'Mixed or custom naming patterns'
        
        return conventions
    
    def _extract_quality_priorities(self, quality_result: str) -> List[Dict[str, Any]]:
        """Extract test priorities based on quality analysis"""
        priorities = []
        result_lower = str(quality_result).lower()
        
        # Security-related test needs
        if any(keyword in result_lower for keyword in ['security', 'vulnerability', 'injection']):
            priorities.append({
                'type': 'security_tests',
                'priority': 'high',
                'description': 'Security vulnerabilities requiring validation and penetration tests',
                'source': 'check_quality'
            })
        
        # Performance-related test needs
        if any(keyword in result_lower for keyword in ['performance', 'slow', 'bottleneck']):
            priorities.append({
                'type': 'performance_tests',
                'priority': 'medium',
                'description': 'Performance issues requiring load and stress testing',
                'source': 'check_quality'
            })
        
        return priorities
    
    def _synthesize_test_proposals(self, test_type: str, proposals: List[Dict[str, Any]], 
                                 analysis_results: Dict[str, Any], routing_strategy: Dict[str, Any],
                                 coverage_threshold: float) -> str:
        """Synthesize test proposals into actionable recommendations with response size management"""
        
        # Group proposals by priority and type
        high_priority = [p for p in proposals if p.get('priority') == 'high']
        medium_priority = [p for p in proposals if p.get('priority') == 'medium']
        
        report_sections = [
            "# 🧪 Test Coverage Analysis & Proposals",
            f"**Test Type Focus**: {test_type.title()}",
            f"**Coverage Target**: {coverage_threshold * 100}%",
            f"**Test Focus**: {routing_strategy['test_focus']}",
            ""
        ]
        
        # Executive Summary
        report_sections.extend([
            "## 📊 Analysis Summary",
            f"- **Total Proposals**: {len(proposals)}",
            f"- **High Priority**: {len(high_priority)}",
            f"- **Medium Priority**: {len(medium_priority)}",
            f"- **Analysis Phases**: {len(analysis_results)}",
            ""
        ])
        
        # High Priority Test Proposals
        if high_priority:
            report_sections.extend([
                "## 🚨 High Priority Test Needs",
                "**Immediate Action Required**",
                ""
            ])
            for i, proposal in enumerate(high_priority, 1):
                report_sections.append(f"{i}. **{proposal['type'].replace('_', ' ').title()}**")
                report_sections.append(f"   - {proposal['description']}")
                report_sections.append(f"   - Source: {proposal['source']}")
                report_sections.append("")
        
        # Medium Priority Test Proposals
        if medium_priority:
            report_sections.extend([
                "## ⚡ Medium Priority Test Opportunities",
                "**Plan for Next Sprint**",
                ""
            ])
            for i, proposal in enumerate(medium_priority, 1):
                report_sections.append(f"{i}. **{proposal['type'].replace('_', ' ').title()}**")
                report_sections.append(f"   - {proposal['description']}")
                report_sections.append(f"   - Source: {proposal['source']}")
                report_sections.append("")
        
        # Testing Framework & Conventions
        if 'conventions' in analysis_results:
            conventions = analysis_results['conventions']
            report_sections.extend([
                "## 🔧 Testing Framework & Conventions",
                f"- **Framework**: {conventions.get('framework', 'Not detected')}",
                f"- **Naming Pattern**: {conventions.get('naming', 'Not detected')}",
                f"- **Recommendation**: Follow existing conventions for consistency",
                ""
            ])
        
        # Truncated Analysis Results - Include only summaries to stay within token limits
        report_sections.extend([
            "## 📋 Analysis Results Summary",
            "**Note**: Detailed analysis results truncated to stay within response limits.",
            "**Recommendation**: Run individual tools for complete analysis details.",
            ""
        ])
        
        # Summarize each analysis phase
        for phase_name, phase_result in analysis_results.items():
            if phase_name != 'conventions':  # Already handled above
                result_str = str(phase_result)
                # Get first 200 characters as summary
                summary = result_str[:200] + "..." if len(result_str) > 200 else result_str
                report_sections.extend([
                    f"### {phase_name.replace('_', ' ').title()}",
                    summary,
                    ""
                ])
        
        # Actionable Next Steps
        report_sections.extend([
            "## 🎯 Recommended Next Steps",
            f"1. **Address High Priority Items**: Focus on {len(high_priority)} critical test gaps",
            f"2. **Establish Testing Standards**: Use identified framework and naming conventions",
            f"3. **Set Coverage Goals**: Target {coverage_threshold * 100}% coverage incrementally",
            f"4. **Implement CI/CD Integration**: Add automated test coverage reporting",
            f"5. **Regular Coverage Reviews**: Schedule periodic test coverage analysis",
            ""
        ])
        
        # Simple check: if too big, save to file
        full_report = "\n".join(report_sections)
        
        if len(full_report) > 60000:  # ~15k tokens
            import os
            import time
            
            os.makedirs("smart_tool_results", exist_ok=True)
            filename = f"smart_tool_results/propose_tests_{int(time.time())}.md"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(full_report)
            
            # Return short summary instead
            return f"""# 🧪 Test Proposals Summary

## 📊 Quick Stats
- **High Priority Items**: {len(high_priority)}
- **Medium Priority Items**: {len(medium_priority)}
- **Analysis Phases**: {len(analysis_results)}

## 🚨 Top 3 Priority Actions
1. {high_priority[0]['description'] if high_priority else 'N/A'}
2. {high_priority[1]['description'] if len(high_priority) > 1 else 'N/A'}
3. {high_priority[2]['description'] if len(high_priority) > 2 else 'N/A'}

## 📁 Complete Analysis
Full detailed analysis saved to: `{filename}`

## 🎯 Next Steps
- Review the complete analysis file for all details
- Focus on high priority items first
- Use the detailed recommendations in the file
"""
        
        return full_report  # Normal case
