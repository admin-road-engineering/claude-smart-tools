"""
Executive Synthesizer - Provides consolidated executive-style summaries of tool results
Uses Gemini 2.5 Flash-Lite to synthesize comprehensive analysis into actionable insights
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ExecutiveSynthesizer:
    """
    Synthesizes multi-engine results into executive-style summaries
    Always-on feature that provides consolidated responses using Gemini 2.5 Flash-Lite
    """
    
    def __init__(self, engines: Dict[str, Any]):
        """
        Initialize with engine access for review_output
        
        Args:
            engines: Dictionary of available engines including review_output
        """
        self.engines = engines
        self.review_engine = engines.get('review_output')
        
        # Target word counts for different sections
        self.word_targets = {
            'understand': {'answer': 300, 'summary': 1000, 'total': 1300},
            'investigate': {'answer': 400, 'summary': 1200, 'total': 1600},
            'validate': {'answer': 300, 'summary': 900, 'total': 1200},
            'full_analysis': {'answer': 400, 'summary': 1200, 'total': 1600}
        }
        
        logger.info("Executive Synthesizer initialized")
    
    async def synthesize(self, tool_name: str, raw_results: str, 
                         original_request: Dict[str, Any]) -> str:
        """
        Create executive synthesis of tool results
        
        Args:
            tool_name: Name of the smart tool that generated results
            raw_results: Complete untruncated results from the smart tool
            original_request: Original parameters passed to the smart tool
            
        Returns:
            Executive synthesis with direct answer + summary
        """
        try:
            if not self.review_engine:
                logger.warning("Review engine not available for executive synthesis")
                return raw_results
            
            # Get word targets for this tool
            targets = self.word_targets.get(tool_name, 
                                           {'answer': 300, 'summary': 1000, 'total': 1300})
            
            # Build the synthesis prompt based on tool type
            synthesis_prompt = self._build_synthesis_prompt(
                tool_name, raw_results, original_request, targets
            )
            
            # Call review_output with Gemini 2.5 Flash-Lite (fallback to Flash)
            synthesis_result = await self._call_review_engine(synthesis_prompt)
            
            if synthesis_result and not synthesis_result.startswith("Error"):
                logger.info(f"Executive synthesis successful for {tool_name}")
                return synthesis_result
            else:
                logger.warning(f"Executive synthesis failed, returning raw results")
                return raw_results
                
        except Exception as e:
            logger.error(f"Executive synthesis error: {e}")
            return raw_results
    
    def _build_synthesis_prompt(self, tool_name: str, raw_results: str, 
                                original_request: Dict[str, Any], 
                                targets: Dict[str, int]) -> str:
        """
        Build tool-specific synthesis prompt
        """
        # Extract original question/problem if present
        original_question = (original_request.get('question') or 
                           original_request.get('problem') or 
                           original_request.get('context', ''))
        
        # Base prompt structure
        base_prompt = f"""You are an executive technical advisor providing actionable insights.

## Task: Executive Synthesis of {tool_name.title()} Analysis

### Original Request:
Files analyzed: {original_request.get('files', [])}
{f"Question: {original_question}" if original_question else ""}
{f"Focus: {original_request.get('focus', 'N/A')}" if 'focus' in original_request else ""}
{f"Validation Type: {original_request.get('validation_type', 'N/A')}" if 'validation_type' in original_request else ""}

### Raw Analysis Results:
{raw_results}

### Your Response Format:

## Direct Answer ({targets['answer']} words)
[Directly answer the original question or address the core issue. Be specific and actionable.]

## Executive Summary ({targets['summary']} words)

### Key Findings
[3-5 bullet points of the most important discoveries]

### Technical Insights
[Critical technical details that impact decisions]

### Recommendations
[Prioritized action items with clear next steps]

### Risk Assessment
[Potential issues and mitigation strategies]

IMPORTANT:
- Total response: ~{targets['total']} words
- Focus on actionable insights over technical details
- Prioritize findings by business/project impact
- Make recommendations concrete and implementable
- If a specific question was asked, ensure it is directly answered first
"""
        
        # Add tool-specific guidance
        tool_specific = self._get_tool_specific_guidance(tool_name, original_request)
        
        return base_prompt + "\n\n" + tool_specific
    
    def _get_tool_specific_guidance(self, tool_name: str, 
                                   original_request: Dict[str, Any]) -> str:
        """
        Get tool-specific synthesis guidance
        """
        guidance = {
            'understand': """### Synthesis Focus for Understanding:
- Architecture clarity: How is the system organized?
- Key patterns: What design patterns are used?
- Integration points: How do components interact?
- Documentation gaps: What needs better documentation?
- If a specific question was asked about the code, answer it directly first.""",
            
            'investigate': """### Synthesis Focus for Investigation:
- Root cause: What is causing the problem?
- Impact scope: What systems/components are affected?
- Resolution path: Step-by-step fix approach
- Prevention: How to avoid similar issues
- Performance metrics: Quantify the issue if possible
- Answer the specific problem statement directly.""",
            
            'validate': """### Synthesis Focus for Validation:
- Critical issues: Security/quality problems requiring immediate action
- Compliance status: Standards and best practices adherence
- Technical debt: Areas needing refactoring
- Quality metrics: Coverage, complexity, maintainability scores
- Risk prioritization: Order issues by severity and impact.""",
            
            'full_analysis': """### Synthesis Focus for Comprehensive Analysis:
- System health: Overall status across all dimensions
- Cross-cutting concerns: Issues affecting multiple areas
- Strategic recommendations: Long-term improvements
- Quick wins: Immediate improvements with high impact
- Architecture evolution: Future-proofing suggestions."""
        }
        
        return guidance.get(tool_name, "### Focus: Provide clear, actionable synthesis of the analysis.")
    
    async def _call_review_engine(self, prompt: str) -> str:
        """
        Call review_output engine with appropriate model selection
        """
        try:
            # Use the engine wrapper's execute method instead of direct call
            if hasattr(self.review_engine, 'execute'):
                result = await self.review_engine.execute(
                    output=prompt,
                    is_plan=False,  # This is analysis synthesis, not plan review
                    focus="all",
                    detail_level="comprehensive",
                    response_style="executive"
                )
            else:
                # Direct engine call as fallback
                result = await self.review_engine(
                    output=prompt,
                    is_plan=False,
                    focus="all",
                    detail_level="comprehensive",
                    response_style="executive"
                )
            
            return str(result)
            
        except Exception as e:
            logger.error(f"Review engine call failed: {e}")
            
            # Try simpler fallback call
            try:
                if hasattr(self.review_engine, 'execute'):
                    result = await self.review_engine.execute(
                        output=prompt,
                        is_plan=False
                    )
                else:
                    result = await self.review_engine(
                        output=prompt,
                        is_plan=False
                    )
                return str(result)
            except:
                return f"Error: Executive synthesis failed - {str(e)}"
    
    def should_synthesize(self, tool_name: str) -> bool:
        """
        Determine if synthesis should be applied to this tool
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if synthesis should be applied, False for collaborate tool
        """
        # Never synthesize collaborate tool - it's already a dialogue
        if tool_name == 'collaborate':
            return False
        
        # Always synthesize other tools
        return tool_name in ['understand', 'investigate', 'validate', 'full_analysis']