"""
Collaborate Tool - Smart tool for technical dialogue, reviews, discussions, and clarifying questions
Direct wrapper around review_output functionality from the original gemini-mcp system
"""
from typing import List, Dict, Any, Optional
from .base_smart_tool import BaseSmartTool, SmartToolResult


class CollaborateTool(BaseSmartTool):
    """
    Smart tool for technical collaboration and dialogue
    Provides a simplified interface to the sophisticated review_output system
    """
    
    def get_routing_strategy(self, content: Optional[str] = None, file_path: Optional[str] = None, 
                           discussion_type: str = "review", context: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Determine collaboration approach based on discussion type and content
        """
        engines_to_use = ['review_output']  # Always use review_output as the primary engine
        routing_explanation = []
        
        # Analyze discussion type to determine approach
        if discussion_type == "review":
            routing_explanation.append("Code review mode - comprehensive technical analysis")
            dialogue_mode = False  # Use autonomous review for comprehensive analysis
            
        elif discussion_type == "feedback":
            routing_explanation.append("Feedback mode - structured recommendations and suggestions")
            dialogue_mode = False  # Use autonomous for structured feedback
            
        elif discussion_type == "brainstorm":
            routing_explanation.append("Brainstorming mode - interactive dialogue for ideation")
            dialogue_mode = True  # Use dialogue mode for collaborative brainstorming
            
        elif discussion_type == "clarification":
            routing_explanation.append("Clarification mode - interactive Q&A for understanding")
            dialogue_mode = True  # Use dialogue mode for questions and answers
            
        else:
            routing_explanation.append("General collaboration mode - balanced analysis")
            dialogue_mode = False
        
        # Determine content source and format
        if file_path and not content:
            routing_explanation.append(f"Loading content from file: {file_path}")
            content_source = "file"
        elif content and not file_path:
            routing_explanation.append("Using provided content directly")
            content_source = "direct"
        elif content and file_path:
            routing_explanation.append("Using provided content with file context")
            content_source = "hybrid"
        else:
            routing_explanation.append("No specific content provided - general discussion")
            content_source = "none"
        
        return {
            'engines': engines_to_use,
            'explanation': '; '.join(routing_explanation),
            'dialogue_mode': dialogue_mode,
            'content_source': content_source,
            'discussion_type': discussion_type
        }
    
    async def execute(self, content: Optional[str] = None, file_path: Optional[str] = None,
                     discussion_type: str = "review", context: Optional[str] = None, **kwargs) -> SmartToolResult:
        """
        Execute collaborative dialogue using the review_output engine
        """
        try:
            # If a file_path is provided, try to read project context from its location
            project_context_str = None
            if file_path:
                project_context = await self._get_project_context([file_path])
                if project_context and project_context.get('claude_md_content'):
                    project_context_str = self.context_reader.format_context_for_analysis(project_context)
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Using project-specific CLAUDE.md for collaboration ({len(project_context['claude_md_content'])} chars)")
            
            # Merge project context with any explicitly provided context
            if project_context_str:
                if context:
                    # Combine both contexts
                    context = f"{project_context_str}\n\n=== USER PROVIDED CONTEXT ===\n{context}"
                else:
                    context = project_context_str
            
            routing_strategy = self.get_routing_strategy(
                content=content, file_path=file_path, discussion_type=discussion_type, 
                context=context, **kwargs
            )
            
            # Prepare review_output parameters
            review_params = self._prepare_review_parameters(
                content, file_path, discussion_type, context, routing_strategy
            )
            
            # Execute review_output engine
            review_result = await self.execute_engine('review_output', **review_params)
            
            # Format collaboration result
            collaboration_response = self._format_collaboration_response(
                review_result, discussion_type, routing_strategy
            )
            
            return SmartToolResult(
                tool_name="collaborate",
                success=True,
                result=collaboration_response,
                engines_used=['review_output'],
                routing_decision=routing_strategy['explanation'],
                metadata={
                    "discussion_type": discussion_type,
                    "content_source": routing_strategy['content_source'],
                    "dialogue_mode": routing_strategy['dialogue_mode'],
                    "has_content": bool(content),
                    "has_file_path": bool(file_path),
                    "has_context": bool(context)
                }
            )
            
        except Exception as e:
            return SmartToolResult(
                tool_name="collaborate",
                success=False,
                result=f"Collaboration failed: {str(e)}",
                engines_used=['review_output'],
                routing_decision=routing_strategy['explanation'] if 'routing_strategy' in locals() else "Failed during routing",
                metadata={"error": str(e)}
            )
    
    def _prepare_review_parameters(self, content: Optional[str], file_path: Optional[str], 
                                 discussion_type: str, context: Optional[str], 
                                 routing_strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare parameters for the review_output engine
        """
        params = {}
        
        # Content handling
        if content:
            params['output'] = content
            params['is_plan'] = self._detect_if_plan(content)
        
        if file_path:
            params['file_path'] = file_path
            # If no content provided, review_output will load from file
            if not content:
                params['is_plan'] = self._detect_if_plan_from_filename(file_path)
        
        # Context and dialogue configuration
        if context:
            params['context'] = context
        
        # Dialogue mode configuration
        params['autonomous'] = not routing_strategy['dialogue_mode']
        
        # Discussion type specific configuration
        if discussion_type == "review":
            params['detail_level'] = "comprehensive"
            params['focus'] = "all"
        elif discussion_type == "feedback":
            params['detail_level'] = "detailed" 
            params['focus'] = "all"
        elif discussion_type == "brainstorm":
            params['detail_level'] = "summary"
            params['focus'] = "architecture"
        elif discussion_type == "clarification":
            params['detail_level'] = "detailed"
            params['focus'] = "all"
        
        return params
    
    def _detect_if_plan(self, content: str) -> bool:
        """
        Detect if content is a plan/document vs code
        """
        plan_keywords = ['plan', 'TODO', 'FIXME', 'implementation', 'requirements', 
                        'specification', 'design', 'architecture']
        
        # Simple heuristic: if content has plan keywords and fewer code patterns
        content_lower = content.lower()
        plan_indicators = sum(1 for keyword in plan_keywords if keyword.lower() in content_lower)
        
        # Code patterns
        code_patterns = ['def ', 'function ', 'class ', 'import ', '{', '}', '()', '=>']
        code_indicators = sum(1 for pattern in code_patterns if pattern in content)
        
        # If more plan indicators than code indicators, likely a plan
        return plan_indicators > code_indicators
    
    def _detect_if_plan_from_filename(self, file_path: str) -> bool:
        """
        Detect if file is likely a plan based on filename
        """
        plan_extensions = ['.md', '.txt', '.rst', '.doc']
        plan_keywords = ['plan', 'todo', 'readme', 'spec', 'design', 'requirements']
        
        file_lower = file_path.lower()
        
        # Check extension
        if any(file_lower.endswith(ext) for ext in plan_extensions):
            return True
        
        # Check filename keywords
        if any(keyword in file_lower for keyword in plan_keywords):
            return True
        
        return False
    
    def _format_collaboration_response(self, review_result: Any, discussion_type: str, 
                                     routing_strategy: Dict[str, Any]) -> str:
        """
        Format the collaboration response based on discussion type
        """
        collaboration_sections = []
        
        # Header based on discussion type
        if discussion_type == "review":
            collaboration_sections.append("# 📋 Code Review Results")
        elif discussion_type == "feedback":
            collaboration_sections.append("# 💭 Technical Feedback")
        elif discussion_type == "brainstorm":
            collaboration_sections.append("# 🧠 Brainstorming Session")
        elif discussion_type == "clarification":
            collaboration_sections.append("# ❓ Technical Clarification")
        else:
            collaboration_sections.append("# 💬 Technical Collaboration")
        
        # Add routing context
        collaboration_sections.extend([
            f"**Collaboration Mode**: {discussion_type.title()}",
            f"**Analysis Approach**: {routing_strategy['explanation']}",
            ""
        ])
        
        # Add the actual review/analysis content
        collaboration_sections.extend([
            "## 🤖 AI Analysis",
            str(review_result),
            ""
        ])
        
        # Add discussion type specific guidance
        if discussion_type == "review":
            collaboration_sections.extend([
                "## 📝 Review Summary",
                "- Technical analysis completed above",
                "- Review key recommendations and suggestions", 
                "- Address any critical issues identified",
                "- Consider architectural improvements mentioned",
                ""
            ])
        elif discussion_type == "feedback":
            collaboration_sections.extend([
                "## 🔄 Next Steps",
                "- Review the feedback provided above",
                "- Prioritize suggestions based on impact",
                "- Consider implementation feasibility",
                "- Ask follow-up questions if clarification needed",
                ""
            ])
        elif discussion_type == "brainstorm":
            collaboration_sections.extend([
                "## 💡 Brainstorming Outcomes", 
                "- Ideas and suggestions provided above",
                "- Consider which approaches align with your goals",
                "- Feel free to explore variations or ask for alternatives",
                "- Continue the dialogue to refine concepts",
                ""
            ])
        elif discussion_type == "clarification":
            collaboration_sections.extend([
                "## ✅ Clarification Provided",
                "- Technical explanation provided above",
                "- Ask additional questions if more detail needed", 
                "- Request specific examples if helpful",
                "- Continue dialogue for deeper understanding",
                ""
            ])
        
        # Add collaboration invitation
        if routing_strategy['dialogue_mode']:
            collaboration_sections.extend([
                "## 🗣️ Continue the Dialogue",
                "This is an interactive session. Feel free to:",
                "- Ask follow-up questions",
                "- Request clarification on specific points",
                "- Explore alternative approaches",
                "- Dive deeper into any aspect",
                ""
            ])
        
        return "\n".join(collaboration_sections)


# Additional helper for backwards compatibility with review_output if needed
class ReviewOutputAdapter:
    """
    Adapter to handle review_output calls if the engine interface differs
    """
    
    @staticmethod
    async def call_review_output(engines: Dict[str, Any], **params) -> Any:
        """
        Call review_output engine with proper parameter handling
        """
        if 'review_output' in engines:
            return await engines['review_output'].execute(**params)
        else:
            # Fallback if review_output not available
            return "Review output engine not available. This tool requires the gemini-review system."