"""
Tool Recommender AI Interpreter - Intelligent Tool Recommendation Engine
Implements Gemini's architectural recommendations using the AI Interpreter pattern
"""
import logging
from typing import Dict, Any, List, Optional
import json

from .ai_interpreter import BaseAIInterpreter
from ..services.tool_registry import tool_registry
from ..clients.gemini_client import GeminiClient
from ..exceptions import ToolingError

logger = logging.getLogger(__name__)


class ToolRecommenderAIInterpreter(BaseAIInterpreter):
    """
    AI Interpreter specialized for tool recommendation
    
    Takes technical analysis results and uses Gemini to intelligently
    recommend specific tools for deeper investigation.
    """
    
    def __init__(self, gemini_client: GeminiClient):
        self.gemini_client = gemini_client
        self.logger = logging.getLogger(__name__)
    
    async def interpret(self, context: Any, additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze technical review results and recommend specific tools for unmapped questions
        
        Args:
            context: RecommendationContext object with all necessary context
            additional_context: Optional additional context for recommendations
                
        Returns:
            Dict with structured tool recommendations
        """
        try:
            # Import here to avoid circular dependency
            from ..types.recommendation_types import RecommendationContext
            
            # Skip AI if all questions were rule-mapped
            if not context.unmapped_questions and context.rule_mapped_tools:
                return {
                    "success": True,
                    "recommendations": {
                        "tools": [],
                        "summary": "All questions handled by rule-based mapping",
                        "ai_contribution": False
                    }
                }
            
            analysis_text = context.analysis_text
            focus = context.focus
            detail_level = context.detail_level
            content_type = context.content_type
            
            # Get relevant tools based on focus area
            focus_areas = self._map_focus_to_areas(focus)
            recommendation_context = tool_registry.get_recommendation_context(focus_areas)
            
            # Create focused recommendation prompt for unmapped questions
            prompt = self._create_recommendation_prompt(
                context=context,
                tools_context=recommendation_context
            )
            
            # Get recommendations from Gemini Flash (fast, cost-effective for recommendations)
            response_text, model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name="flash",  # Use Flash for quick recommendations
                timeout=30  # Short timeout for recommendation step
            )
            
            # Parse and structure the recommendations
            recommendations = self._parse_recommendations(response_text, context)
            
            self.logger.info(f"Generated {len(recommendations.get('tools', []))} AI tool recommendations using {model_used}")
            
            return {
                "success": True,
                "recommendations": recommendations,
                "meta": {
                    "model_used": model_used,
                    "attempts": attempts,
                    "focus_areas": focus_areas,
                    "tools_considered": recommendation_context["total_tools"],
                    "questions_processed": len(context.unmapped_questions),
                    "ai_contribution": True
                }
            }
            
        except Exception as e:
            self.logger.error(f"Tool recommendation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback_recommendations": self._generate_fallback_recommendations(context.focus)
            }
    
    def _map_focus_to_areas(self, focus: str) -> List[str]:
        """Map review focus to tool focus areas"""
        focus_mapping = {
            "security": ["security", "code_quality", "configuration"],
            "performance": ["performance", "bottlenecks", "optimization", "profiling"],
            "architecture": ["architecture", "dependencies", "design_patterns", "code_structure"],
            "all": ["security", "performance", "architecture", "code_quality", "testing"]
        }
        
        return focus_mapping.get(focus, focus_mapping["all"])
    
    def _create_recommendation_prompt(self, context: Any, tools_context: Dict[str, Any]) -> str:
        """Create focused prompt for unmapped questions only"""
        
        tools_json = json.dumps(tools_context["tools"], indent=2)
        
        # Show what was already mapped
        already_mapped_section = ""
        if context.rule_mapped_tools:
            already_mapped_section = f"""
## ALREADY MAPPED (Do not duplicate):
{json.dumps([{"tool": t["tool"], "question": t["answers_question"]} 
            for t in context.rule_mapped_tools], indent=2)}
"""
        
        # Format dialogue history if available
        dialogue_section = ""
        if context.dialogue_history:
            dialogue_section = """
## DIALOGUE HISTORY:
"""
            for exchange in context.dialogue_history[-2:]:  # Last 2 exchanges
                dialogue_section += f"Round {exchange.get('round_number', '?')}: "
                dialogue_section += f"Claude asked about {exchange.get('claude_response', '')[:100]}...\n"
                dialogue_section += f"Gemini responded: {exchange.get('gemini_response', '')[:100]}...\n\n"
        
        return f"""You are analyzing technical content to recommend tools for ONLY the unmapped questions.

## UNMAPPED QUESTIONS REQUIRING TOOLS:
{json.dumps(context.unmapped_questions, indent=2)}

## VALID FILE PATHS IN PROJECT:
{json.dumps(context.mentioned_files, indent=2)}

{already_mapped_section}
{dialogue_section}

## ANALYSIS CONTEXT:
- **Focus**: {context.focus}
- **Detail Level**: {context.detail_level}
- **Content Type**: {context.content_type}

## AVAILABLE TOOLS:
{tools_json}

## TASK:
Recommend tools ONLY for the unmapped questions above. Do not duplicate tools already mapped.
Focus on questions that require deeper, more nuanced analysis.

## CRITICAL REQUIREMENTS:
1. **Use ONLY valid file paths** from the "VALID FILE PATHS" list above
2. **Map questions to tools** - each recommendation should answer a specific question
3. **Build on dialogue** - don't repeat analyses already discussed
4. **Executable parameters** - all parameters must be immediately usable

## RESPONSE FORMAT:
Respond with valid JSON only:

```json
{{
  "recommended_tools": [
    {{
      "tool_name": "exact_tool_name",
      "reason": "Specific insight this provides for the unmapped question",
      "parameters": {{
        "paths": ["actual/valid/path.py"],
        "specific_param": "exact_value"
      }},
      "answers_question": "The specific unmapped question this answers",
      "confidence": 0.7,
      "expected_insights": "What new information this provides beyond rule-based analysis"
    }}
  ],
  "analysis_summary": "How these tools add value beyond rule-based mapping"
}}
```

## IMPORTANT:
- NEVER use placeholder paths like "path/to/file" or "ComprehensiveReviewTool/"
- ALWAYS use actual paths from the valid files list or leave paths empty
- Each tool should answer a specific unmapped question
- Focus on questions that require AI's flexible understanding
- Maximum 3 tools to avoid overwhelming the user"""
    
    def _parse_recommendations(self, response_text: str, context: Any) -> Dict[str, Any]:
        """Parse Gemini's JSON response into structured recommendations"""
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response_text[json_start:json_end]
            parsed = json.loads(json_str)
            
            # Validate structure
            if "recommended_tools" not in parsed:
                raise ValueError("Missing 'recommended_tools' in response")
            
            # Format for consistent output
            formatted_tools = []
            for tool in parsed["recommended_tools"]:
                if not all(key in tool for key in ["tool_name", "reason"]):
                    self.logger.warning(f"Skipping malformed tool recommendation: {tool}")
                    continue
                    
                # Validate paths in parameters
                params = tool.get("parameters", {})
                if "paths" in params and context.mentioned_files:
                    # Filter to only valid paths
                    if isinstance(params["paths"], list):
                        params["paths"] = [p for p in params["paths"] 
                                          if p in context.mentioned_files]
                    if not params["paths"]:
                        # Use mentioned files if no valid paths
                        params["paths"] = context.mentioned_files[:3]
                
                formatted_tools.append({
                    "tool": tool["tool_name"],
                    "reason": tool["reason"],
                    "parameters": params,
                    "answers_question": tool.get("answers_question", ""),
                    "confidence": tool.get("confidence", 0.6),
                    "priority": tool.get("priority", 2),
                    "expected_insights": tool.get("expected_insights", ""),
                    "mapping_type": "ai"
                })
            
            return {
                "tools": formatted_tools,
                "summary": parsed.get("analysis_summary", "AI-recommended tools for deeper analysis"),
                "total_recommendations": len(formatted_tools)
            }
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            self.logger.error(f"Failed to parse recommendation response: {e}")
            self.logger.debug(f"Response text: {response_text[:500]}...")
            
            # Return fallback parsing
            return self._parse_fallback_recommendations(response_text)
    
    def _parse_fallback_recommendations(self, response_text: str) -> Dict[str, Any]:
        """Fallback parsing for non-JSON responses"""
        # Simple keyword-based extraction as fallback
        tool_names = []
        available_tools = list(tool_registry.get_all_tools().keys())
        
        for tool_name in available_tools:
            if tool_name in response_text.lower():
                tool_names.append({
                    "tool": tool_name,
                    "reason": "Mentioned in analysis",
                    "parameters": {},
                    "priority": 2,
                    "expected_insights": "Additional analysis recommended"
                })
        
        return {
            "tools": tool_names[:3],  # Limit to top 3
            "summary": "Fallback tool extraction from response",
            "total_recommendations": len(tool_names),
            "parsing_method": "fallback"
        }
    
    def _generate_fallback_recommendations(self, focus: str) -> Dict[str, Any]:
        """Generate basic recommendations when AI interpretation fails"""
        focus_tool_mapping = {
            "security": ["check_quality"],
            "performance": ["performance_profiler", "check_quality"],
            "architecture": ["analyze_code", "map_dependencies"],
            "all": ["check_quality", "analyze_code"]
        }
        
        suggested_tools = focus_tool_mapping.get(focus, ["check_quality"])
        
        fallback_tools = []
        for tool_name in suggested_tools:
            try:
                tool_meta = tool_registry.get_tool(tool_name)
                fallback_tools.append({
                    "tool": tool_name,
                    "reason": f"Standard recommendation for {focus} analysis",
                    "parameters": {"check_type": focus} if tool_name == "check_quality" else {},
                    "priority": 1,
                    "expected_insights": f"Basic {focus} analysis"
                })
            except KeyError:
                continue
        
        return {
            "tools": fallback_tools,
            "summary": f"Fallback recommendations for {focus} focus",
            "total_recommendations": len(fallback_tools)
        }