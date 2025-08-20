"""
Core business logic for Gemini code review service
"""
import asyncio
import logging
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from ..clients.gemini_client import GeminiClient
from ..persistence.base_repositories import SessionRepository, AnalyticsRepository
from ..services.complexity_scorer import ComplexityScorer
from ..services.model_selection_router import ModelSelectionRouter
from ..services.cpu_throttler import CPUThrottler
from ..models.review_request import ReviewRequest
from ..models.context_models import ContextEntry
from ..config import LOGS_DIR

logger = logging.getLogger(__name__)

class ReviewService:
    """Core business logic orchestrator for code reviews"""
    
    def __init__(self, session_repo: SessionRepository, analytics_repo: AnalyticsRepository, 
                 gemini_client: GeminiClient = None, complexity_scorer: ComplexityScorer = None,
                 model_router: ModelSelectionRouter = None, config=None):
        self.logger = logging.getLogger(__name__)
        self.session_repo = session_repo
        self.analytics_repo = analytics_repo
        self.config = config
        self.gemini_client = gemini_client or GeminiClient(config)
        self.complexity_scorer = complexity_scorer or ComplexityScorer()
        self.model_router = model_router or ModelSelectionRouter()
        self.cpu_throttler = CPUThrottler(config) if config else None
        
        # Ensure logs directory exists
        os.makedirs(LOGS_DIR, exist_ok=True)
        
        logger.info("Review service initialized with new model selection router")
    
    def _read_project_context(self, comprehensive: bool = True) -> str:
        """Read project context from CLAUDE.md and other relevant files"""
        context_parts = []
        
        # Try to read CLAUDE.md from project root
        claude_md_paths = ["CLAUDE.md", "../CLAUDE.md", "../../CLAUDE.md"]
        for path in claude_md_paths:
            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        context_parts.append(f"## Project Documentation (CLAUDE.md)\n{content}")
                    break
            except Exception as e:
                logger.debug(f"Could not read {path}: {e}")
        
        # Try to read GEMINI.md for AI context
        gemini_md_paths = ["GEMINI.md", "../GEMINI.md", "../../GEMINI.md"]
        for path in gemini_md_paths:
            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        context_parts.append(f"## AI Review Guidelines (GEMINI.md)\n{content}")
                    break
            except Exception as e:
                logger.debug(f"Could not read {path}: {e}")
        
        # Add basic project info if no documentation found
        if not context_parts:
            context_parts.append("## Project Context\nClaude-Gemini MCP collaborative code review system")
        
        if comprehensive:
            # Try to read README for additional context
            readme_paths = ["README.md", "../README.md", "../../README.md"]
            for path in readme_paths:
                try:
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()[:2000]  # Limit to avoid too much context
                            context_parts.append(f"## README\n{content}")
                        break
                except Exception as e:
                    logger.debug(f"Could not read {path}: {e}")
        
        return "\n\n".join(context_parts)
    
    def _create_review_prompt(self, review_request: Dict, project_context: str) -> str:
        """Create the review prompt for Gemini"""
        
        # Core instructions based on detail level
        detail_instructions = {
            "summary": "Provide a brief, high-level summary",
            "detailed": "Provide detailed analysis with specific recommendations", 
            "comprehensive": "Provide comprehensive analysis covering all aspects"
        }
        
        focus_instructions = {
            "security": "Focus specifically on security vulnerabilities and best practices",
            "performance": "Focus on performance optimization and efficiency",
            "architecture": "Focus on architectural design, patterns, and maintainability",
            "all": "Provide comprehensive review covering security, performance, architecture, and best practices"
        }
        
        detail_level = review_request.get("detail_level", "detailed")
        focus = review_request.get("focus", "all")
        is_plan = review_request.get("is_plan", True)
        content = review_request.get("content", "")
        context = review_request.get("context", "")
        
        content_type = "implementation plan" if is_plan else "code"
        
        prompt = f"""You are a senior software engineer conducting a {detail_level} review of this {content_type}.

{detail_instructions.get(detail_level, detail_instructions["detailed"])}

**Focus Area:** {focus_instructions.get(focus, focus_instructions["all"])}

**Project Context:**
{project_context}

**Additional Context:**
{context or "No additional context provided"}

**{content_type.title()} to Review:**
```
{content}
```

Please provide your review with specific, actionable feedback."""
        
        return prompt
    
    def _format_review_output(self, review: str, task_id: str, content_size: int, 
                            focus: str, model_used: str = "", attempts: int = 1, 
                            input_type: str = "", input_summary: str = "", 
                            is_dialogue: bool = False) -> str:
        """Format review output with condensed summary for better UX"""
        
        # Split review into lines for analysis
        lines = review.split('\n')
        
        # Find key sections and create condensed summary
        key_points = []
        current_section = ""
        
        for line in lines[:20]:  # Analyze first 20 lines for key points
            line_clean = line.strip()
            if line_clean and len(line_clean) > 15:
                # Look for important statements
                if any(keyword in line_clean.lower() for keyword in 
                      ['recommendation', 'issue', 'concern', 'improve', 'fix', 'critical', 'important', 'suggest']):
                    key_points.append(line_clean[:80] + "..." if len(line_clean) > 80 else line_clean)
                
                # Capture section headers
                if line_clean.startswith('#') or line_clean.endswith(':') or line_clean.isupper():
                    current_section = line_clean[:50]
        
        # Create condensed preview
        preview_lines = []
        if key_points:
            preview_lines.extend(key_points[:3])  # Top 3 key points
        elif current_section:
            preview_lines.append(current_section)
        
        preview = "; ".join(preview_lines) if preview_lines else review.split('\n')[0][:100] + "..."
        
        # Format final output with emoji headers and condensed info
        if is_dialogue:
            emoji = "🤝"
            type_label = "Dialogue"
        else:
            emoji = "🔍" 
            type_label = "Review"
        
        formatted_output = f"""🤝 Collaborative Dialogue Complete - {task_id}
📊 {content_size} chars | Focus: {focus} | Input: {input_summary} | Type: {type_label}
🤖 {model_used}
📋 {input_type} ({attempts} attempts)
🔍 Key Points:
   {chr(10).join(f'   {i+1}. {point}' for i, point in enumerate(key_points[:3]))}
📝 Preview: {preview}

--- Full Review ---
{review}

---
**Next Step**: To continue this dialogue, make another `review_output` call with:
- `claude_response`: Your detailed answers to Gemini's questions above
- `task_id`: "{task_id}" (to continue this session)
- `requested_files`: Optional array of file paths if Gemini mentioned specific files to review
- Same `output`, `is_plan`, `focus`, `context` parameters

**Example**:
```
review_output(
    output="your original content",
    claude_response="1. For state management, I'm using React Context with useReducer... 2. For the popup system, I implemented...",
    requested_files=["src/components/AppLayout.tsx", "src/hooks/useCampaignData.ts"],
    task_id="{task_id}",
    is_plan=your_original_is_plan_value,
    focus="your_original_focus"
)
```

**Session Info**: {model_used} model, {attempts} attempts"""
        
        return formatted_output
    
    async def process_review_request(self, request: ReviewRequest) -> str:
        """
        Process a review request with full dialogue support
        
        Returns formatted review output
        """
        # CPU throttling context manager for heavy operation
        if self.cpu_throttler:
            async with self.cpu_throttler.monitor_heavy_operation("review_processing"):
                return await self._process_review_request_internal(request)
        else:
            return await self._process_review_request_internal(request)
    
    async def _process_review_request_internal(self, request: ReviewRequest) -> str:
        """Internal review request processing with CPU yielding"""
        output_type = "plan" if request.is_plan else "code"
        
        # Generate task_id if not provided
        if not request.task_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            task_id = f"{output_type}_{timestamp}"
        else:
            task_id = request.task_id
        
        # Handle file input
        if request.file_path:
            try:
                with open(request.file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"Loaded content from file: {request.file_path}")
                # Update the request with file content
                request.output = content
            except Exception as e:
                return f"Error reading file {request.file_path}: {str(e)}"
        
        # Handle different input modes
        if request.content_summary:
            request.output = request.content_summary
            input_summary = f"summary:{request.detail_level}"
            input_type = "Summary-first review"
        elif request.content_chunks:
            # Combine chunks for now - could be enhanced for chunked processing
            request.output = "\n\n".join([f"## {chunk['section']}\n{chunk['content']}" 
                                for chunk in request.content_chunks])
            input_summary = f"chunked:{len(request.content_chunks)} sections"
            input_type = "Chunked processing"
        else:
            content_size = len(request.output)
            if content_size < 500:
                input_summary = f"direct:{content_size} chars"
            elif content_size < 2000:
                input_summary = f"medium:{content_size} chars"
            else:
                input_summary = f"large:{content_size} chars"
            input_type = f"{output_type.title()} review"
        
        try:
            # Create or get session
            session = self.session_repo.create_session(
                task_id=task_id,
                output_type=output_type,
                focus=request.focus,
                context=request.context or ""
            )
            
            # Use new simplified model selection router
            model_name = self.model_router.select_model(
                tool_name="review_output",
                focus=request.focus,
                detail_level=request.detail_level
            )
            
            # Calculate timeout using complexity scorer (keep this for dynamic timeout calculation)
            timeout = self.complexity_scorer.calculate_dynamic_timeout(request.output, request.is_plan, request.focus, request.detail_level)
            
            # Calculate suggested dialogue rounds based on complexity factors
            suggested_rounds = self.complexity_scorer.calculate_dialogue_rounds(
                output=request.output,
                is_plan=request.is_plan,
                focus=request.focus,
                detail_level=request.detail_level,
                model=model_name,
                user_specified=request.max_dialogue_rounds if request.max_dialogue_rounds != 3 else None  # Only treat as user-specified if not default
            )
            
            # This is guidance for Claude - not a hard limit
            # Claude can exceed this if the dialogue genuinely needs more rounds
            suggested_dialogue_rounds = suggested_rounds
            
            # Create review request
            review_request = {
                "message_type": "PLAN" if request.is_plan else "CODE",
                "content": request.output,
                "is_plan": request.is_plan,
                "focus": request.focus,
                "is_first_review": request.is_first_review,
                "detail_level": request.detail_level,
                "response_style": request.response_style,
                "task_id": task_id,
                "context": request.context or ""
            }
            
            # Get project context
            comprehensive_context = request.detail_level in ["detailed", "comprehensive"]
            project_context = self._read_project_context(comprehensive=comprehensive_context)
            
            # Add analysis context if provided (from full_analysis or other tools)
            if request.analysis_context:
                # Convert dict context to ContextEntry objects for sanitization
                context_entries = []
                for ctx_dict in request.analysis_context[:10]:  # Limit to 10 entries
                    try:
                        # Create a simplified ContextEntry for sanitization
                        from ..models.context_models import ContextType, ContextCategory, ContextPriority
                        entry = ContextEntry(
                            type=ContextType.FINDING,
                            category=ContextCategory.GENERAL,
                            priority=ctx_dict.get('priority', ContextPriority.MEDIUM),
                            title=ctx_dict.get('title', 'Analysis Finding'),
                            content=ctx_dict.get('content', {}),
                            source_tool=ctx_dict.get('source_tool', 'unknown')
                        )
                        context_entries.append(entry)
                    except Exception as e:
                        logger.warning(f"Failed to process context entry: {e}")
                
                if context_entries:
                    sanitized_context = self._sanitize_context_for_prompt(context_entries)
                    project_context = f"{sanitized_context}\n\n{project_context}"
            
            # Yield CPU after file I/O operations
            if self.cpu_throttler:
                await self.cpu_throttler.yield_if_needed()
            
            # Create prompt
            prompt = self._create_review_prompt(review_request, project_context)
            
            # Step 1: Generate core technical analysis
            review_text, final_model_used, attempts = await self.gemini_client.generate_content(
                prompt=prompt,
                model_name=model_name,
                timeout=timeout
            )
            
            # Yield CPU after Gemini API call
            if self.cpu_throttler:
                await self.cpu_throttler.yield_if_needed()
            
            # Step 2: Generate tool recommendations using AI Interpreter pattern
            tool_recommendations = await self._generate_tool_recommendations(
                analysis_text=review_text,
                focus=request.focus,
                detail_level=request.detail_level,
                content_type="plan" if request.is_plan else "code",
                task_id=task_id  # Pass task_id for dialogue history
            )
            
            # Yield CPU after tool recommendation generation
            if self.cpu_throttler:
                await self.cpu_throttler.yield_if_needed()
            
            # Step 3: Combine analysis and recommendations into final response
            final_response = self._combine_analysis_and_recommendations(review_text, tool_recommendations)
            
            # Store dialogue turn
            self.session_repo.add_dialogue_turn(
                task_id=task_id,
                round_number=1,
                model_used=final_model_used,
                attempts=attempts,
                user_input=request.output[:500] + "..." if len(request.output) > 500 else request.output,
                ai_response=final_response[:1000] + "..." if len(final_response) > 1000 else final_response,
                metadata={
                    "model_selected": model_name,
                    "focus": request.focus,
                    "detail_level": request.detail_level,
                    "timeout": timeout,
                    "dialogue_rounds_requested": request.max_dialogue_rounds,
                    "dialogue_rounds_suggested": suggested_rounds,
                    "dialogue_guidance": "soft_limit",  # Indicates Claude can exceed if needed
                    "tool_recommendations_generated": tool_recommendations.get("success", False),
                    "tools_recommended": len(tool_recommendations.get("recommendations", {}).get("tools", []))
                }
            )
            
            # Format output
            formatted_output = self._format_review_output(
                review=final_response,
                task_id=task_id,
                content_size=len(request.output),
                focus=request.focus,
                model_used=final_model_used,
                attempts=attempts,
                input_type=input_type,
                input_summary=input_summary,
                is_dialogue=bool(request.claude_response)
            )
            
            # Generate and save summary if this looks like a completion
            if not request.claude_response and "dialogue complete" in final_response.lower():
                try:
                    summary = await self.gemini_client.generate_summary(
                        f"Summarize this code review session: {final_response[:2000]}"
                    )
                    self.session_repo.save_session_summary(
                        task_id=task_id,
                        polished_summary=summary
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate summary: {e}")
            
            return formatted_output
            
        except Exception as e:
            logger.error(f"Review processing failed: {e}")
            return f"Error processing review: {str(e)}"
    
    def get_session_stats(self) -> Dict:
        """Get session statistics"""
        return self.analytics_repo.get_session_stats()
    
    def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """Clean up old sessions"""  
        return self.analytics_repo.cleanup_old_sessions(days_old)
    
    def _sanitize_context_for_prompt(self, context_entries: List[ContextEntry]) -> str:
        """
        Sanitize context entries to prevent prompt injection.
        
        Args:
            context_entries: List of context entries from other tools
            
        Returns:
            Sanitized context string safe for prompt inclusion
        """
        if not context_entries:
            return ""
        
        sanitized_lines = ["## Context from Previous Analysis:\n"]
        
        # Patterns that could be prompt injection attempts
        dangerous_patterns = [
            "ignore previous", "disregard all", "new instruction", 
            "system:", "assistant:", "user:", "```", "###",
            "forget everything", "override", "bypass"
        ]
        
        for entry in context_entries[:10]:  # Limit to 10 entries max
            # Sanitize title
            title = str(entry.title)
            for pattern in dangerous_patterns:
                title = title.replace(pattern.lower(), "[REDACTED]")
                title = title.replace(pattern.upper(), "[REDACTED]")
            
            sanitized_lines.append(f"### {title}")
            sanitized_lines.append(f"- **Source**: {entry.source_tool}")
            sanitized_lines.append(f"- **Priority**: {entry.priority}")
            
            # Sanitize content
            if entry.content:
                content_str = str(entry.content)
                # Truncate if too long
                if len(content_str) > 500:
                    content_str = content_str[:500] + "...[truncated]"
                
                # Remove dangerous patterns
                for pattern in dangerous_patterns:
                    content_str = content_str.replace(pattern.lower(), "[REDACTED]")
                    content_str = content_str.replace(pattern.upper(), "[REDACTED]")
                
                # Extract key information safely
                if isinstance(entry.content, dict):
                    if 'issues' in entry.content:
                        issues = entry.content.get('issues', [])
                        if issues and isinstance(issues, list):
                            sanitized_lines.append(f"- **Issues Found**: {', '.join(str(i)[:50] for i in issues[:5])}")
                    if 'summary' in entry.content:
                        summary = str(entry.content.get('summary', ''))[:200]
                        for pattern in dangerous_patterns:
                            summary = summary.replace(pattern.lower(), "[REDACTED]")
                        sanitized_lines.append(f"- **Summary**: {summary}")
                else:
                    sanitized_lines.append(f"- **Finding**: {content_str[:200]}")
            
            sanitized_lines.append("")
        
        return "\n".join(sanitized_lines)
    
    def _create_review_prompt(self, review_request: Dict[str, Any], project_context: str) -> str:
        """Create focused technical analysis prompt with structured output format"""
        detail_level = review_request.get('detail_level', 'detailed')
        response_style = review_request.get('response_style', 'detailed')
        
        # Enhanced structure based on detail level and response style
        # response_style overrides detail_level formatting when specified
        if response_style == 'executive':
            response_structure = """## RESPONSE STRUCTURE (Executive):
Please provide a concise executive-style summary:

## Key Findings (Max 3 bullet points)
- Critical Issue: [One sentence description]
- Major Opportunity: [One sentence improvement]
- Risk Assessment: [One sentence risk evaluation]

## Recommended Actions (Max 3)
1. **[Action]** - [Priority: Critical/High/Medium] [Timeline: Days/Weeks]
2. **[Action]** - [Priority: Critical/High/Medium] [Timeline: Days/Weeks]
3. **[Action]** - [Priority: Critical/High/Medium] [Timeline: Days/Weeks]

## Bottom Line
[Single sentence: Should we proceed/stop/modify approach?]

CONSTRAINTS: Maximum 500 words total. Focus on business impact, not technical details."""

        elif response_style == 'concise':
            response_structure = """## RESPONSE STRUCTURE (Concise):
Keep your response focused and brief:

## Main Issues (Max 3)
- Issue 1: [Problem] → [Solution]
- Issue 2: [Problem] → [Solution]  
- Issue 3: [Problem] → [Solution]

## Quick Wins (Max 2)
- [Easy improvement with high impact]
- [Easy improvement with high impact]

## Next Action
[One specific next step]

CONSTRAINTS: Maximum 1000 words. Be direct and actionable."""

        elif detail_level == 'comprehensive' and response_style != 'concise' and response_style != 'executive':
            response_structure = """## RESPONSE STRUCTURE (Comprehensive):
Please structure your response with these mandatory sections:

## Executive Summary
[2-3 sentences capturing the most critical findings and overall assessment]

## Critical Issues (Must Fix)
[List only issues that could cause failures, security vulnerabilities, or major problems]
- Issue 1: [Description] [Severity: High/Critical] [Effort: Low/Medium/High]
- Issue 2: [Description] [Severity: High/Critical] [Effort: Low/Medium/High]

## Recommendations (Should Do)
[Improvements that would enhance quality but aren't critical]
- Recommendation 1: [Description] [Impact: High/Medium] [Effort: Low/Medium/High]
- Recommendation 2: [Description] [Impact: High/Medium] [Effort: Low/Medium/High]

## Technical Deep Dive
### 🔍 Analysis
[Detailed technical analysis with specific code references where applicable]

### 💡 Implementation Guidance
[Specific, actionable steps for implementing recommendations]

### ❓ Questions for Claude
[Specific technical questions to guide the next iteration]"""
        elif detail_level == 'summary':
            response_structure = """## RESPONSE STRUCTURE (Summary):
Please provide a concise response with:

## Quick Assessment
[1-2 sentences on overall quality]

## Key Points
- Most important finding
- Second most important finding
- Third finding (if critical)

## Next Steps
[1-2 concrete actions to take]"""
        else:  # detailed (default)
            response_structure = """## RESPONSE STRUCTURE (Detailed):
Please structure your response as follows:

## Executive Summary
[2-3 sentences with key findings]

## Key Issues & Recommendations
[Prioritized list with severity/impact indicators]
1. **[Issue/Recommendation]** - [Priority: High/Medium/Low]
   - Problem: [Brief description]
   - Solution: [Specific fix or improvement]
   - Effort: [Low/Medium/High]

## Technical Analysis
### 🔍 Analysis
[Your detailed technical analysis and findings]

### 💡 Implementation Notes
[Specific actionable recommendations with examples]

### ❓ Questions for Claude
[Specific questions to guide the next iteration]"""
        
        return f"""You are Gemini, collaborating with Claude Code through a multi-turn dialogue system. Your role is to provide structured technical analysis and actionable recommendations.

## CONTENT TO REVIEW:
**Type**: {'Plan/Implementation Strategy' if review_request['is_plan'] else 'Code Implementation'}
**Focus**: {review_request['focus']}
**Detail Level**: {review_request['detail_level']}

```
{review_request['content']}
```

## PROJECT CONTEXT:
{project_context}

{response_structure}

## ANALYSIS REQUIREMENTS:
- **Specificity**: Reference specific line numbers, function names, or file paths when discussing code
- **Actionability**: Every issue should have a clear solution or next step
- **Prioritization**: Use severity/impact/effort indicators to help prioritize work
- **Context-Aware**: Consider the project context and focus area ({review_request['focus']})
- **Evidence-Based**: Support findings with specific examples from the code

## IMPORTANT:
- Keep the Executive Summary to 2-3 sentences maximum
- Distinguish clearly between critical issues (must fix) and improvements (nice to have)
- Include effort estimates (Low = <1 hour, Medium = 1-4 hours, High = >4 hours)
- For code issues, include the specific location (file:line or function name)

Context: {review_request.get('context', '')}
Task ID: {review_request.get('task_id', 'N/A')}"""
    
    def _read_project_context(self, comprehensive: bool = False) -> str:
        """Read project context from CLAUDE.md and related files"""
        try:
            import os
            context_parts = []
            
            # Read CLAUDE.md if it exists
            claude_md_path = "CLAUDE.md"
            if os.path.exists(claude_md_path):
                with open(claude_md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Get first 2000 chars for context
                    context_parts.append(f"## Project Documentation (CLAUDE.md)\n{content[:2000]}...")
            
            # If comprehensive, also check for README, package files, etc.
            if comprehensive:
                for filename in ["README.md", "package.json", "pyproject.toml", "setup.py"]:
                    if os.path.exists(filename):
                        with open(filename, 'r', encoding='utf-8') as f:
                            content = f.read()[:1000]  # Smaller excerpts for additional files
                            context_parts.append(f"## {filename}\n{content}...")
            
            return "\n\n".join(context_parts) if context_parts else "No specific project context available."
            
        except Exception as e:
            return f"Error reading project context: {str(e)}"
    
    def _extract_questions(self, text: str) -> List[str]:
        """Extract questions with multiple fallback strategies"""
        import re
        
        questions = []
        
        # Strategy 1: Look for "Questions" section
        question_section = re.search(r'### .*Questions.*?\n(.*?)(?=###|\Z)', text, re.DOTALL)
        if question_section:
            lines = question_section.group(1).strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and (line.endswith('?') or line.startswith(('-', '*', '•'))):
                    cleaned = line.strip('- *•').strip()
                    if cleaned:
                        questions.append(cleaned)
        
        # Strategy 2: Fallback - find any line ending with ?
        if not questions:
            self.logger.info("No Questions section found, using fallback extraction")
            all_lines = text.split('\n')
            for line in all_lines:
                line = line.strip()
                if line.endswith('?') and len(line) > 10:  # Min length to avoid noise
                    questions.append(line)
        
        # Strategy 3: Look for numbered questions (1. 2. 3.)
        if not questions:
            numbered_pattern = r'^\d+\.\s+(.+\?)'
            matches = re.findall(numbered_pattern, text, re.MULTILINE)
            questions.extend(matches)
        
        self.logger.info(f"Extracted {len(questions)} questions from analysis")
        return questions[:10]  # Limit to avoid overwhelming the system
    
    def _extract_mentioned_files(self, text: str) -> tuple[List[str], List[str]]:
        """
        Extract and validate file paths with logging.
        Returns: (valid_files, mentioned_but_missing)
        """
        import re
        import os
        
        patterns = [
            r'`([^`]+\.(py|js|ts|jsx|tsx|go|rs|java|cpp|c|h|hpp))`',
            r'file:?\s*([^\s,]+\.(py|js|ts|jsx|tsx|go|rs|java|cpp|c|h|hpp))',
            r'src/[^\s]+\.(py|js|ts|jsx|tsx|go|rs|java|cpp|c|h|hpp)',
            r'"([^"]+\.(py|js|ts|jsx|tsx|go|rs|java|cpp|c|h|hpp))"'
        ]
        
        found_files = set()
        mentioned_but_missing = set()
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                file_path = match[0] if isinstance(match, tuple) else match
                
                if os.path.exists(file_path):
                    found_files.add(file_path)
                else:
                    mentioned_but_missing.add(file_path)
        
        # Log paths that were mentioned but don't exist (potential hallucinations)
        if mentioned_but_missing:
            self.logger.warning(f"Files mentioned but not found: {mentioned_but_missing}")
        
        self.logger.info(f"Found {len(found_files)} valid files, {len(mentioned_but_missing)} missing")
        return list(found_files), list(mentioned_but_missing)
    
    def _map_questions_to_tools_rule_based(self, questions: List[str], 
                                          valid_files: List[str]) -> Dict[str, Any]:
        """Deterministic mapping for common patterns - fast path"""
        import re
        
        question_patterns = {
            r"state management|session|persistence": {
                "tool": "search_code",
                "params": {"query": "SessionRepository|session_store|SQLite", 
                          "context_question": "How is state managed?"},
                "confidence": 0.9
            },
            r"error handling|exception|failure|resilient": {
                "tool": "search_code",
                "params": {"query": "try.*except|raise|error|failed",
                          "context_question": "How are failures handled?"},
                "confidence": 0.85
            },
            r"tool interface|base class|inheritance": {
                "tool": "analyze_code",
                "params": {"analysis_type": "architecture",
                          "question": "Show tool interfaces and inheritance"},
                "confidence": 0.85
            },
            r"performance|bottleneck|slow|optimization": {
                "tool": "performance_profiler",
                "params": {"profile_type": "comprehensive"},
                "confidence": 0.8
            },
            r"security|vulnerability|authentication|authorization": {
                "tool": "check_quality",
                "params": {"check_type": "security"},
                "confidence": 0.9
            },
            r"test coverage|testing|unit test": {
                "tool": "analyze_test_coverage",
                "params": {"mapping_strategy": "convention"},
                "confidence": 0.85
            },
            r"dependencies|imports|coupling": {
                "tool": "map_dependencies",
                "params": {"analysis_depth": "transitive"},
                "confidence": 0.8
            }
        }
        
        mapped_tools = []
        unmapped_questions = []
        
        for question in questions:
            question_lower = question.lower()
            matched = False
            
            for pattern, tool_config in question_patterns.items():
                if re.search(pattern, question_lower):
                    # Add valid file paths if tool needs them
                    params = tool_config["params"].copy()
                    if tool_config["tool"] in ["analyze_code", "check_quality", "map_dependencies"] and valid_files:
                        params["paths"] = valid_files[:3]  # Limit to top 3 files
                    
                    mapped_tools.append({
                        "tool": tool_config["tool"],
                        "parameters": params,
                        "answers_question": question,
                        "mapping_type": "rule_based",
                        "confidence": tool_config["confidence"],
                        "reason": f"Pattern match for: {pattern.split('|')[0]}"
                    })
                    matched = True
                    break
            
            if not matched:
                unmapped_questions.append(question)
        
        self.logger.info(f"Rule-based mapping: {len(mapped_tools)} tools, {len(unmapped_questions)} unmapped")
        
        return {
            "mapped_tools": mapped_tools,
            "unmapped_questions": unmapped_questions
        }
    
    async def _generate_tool_recommendations(self, analysis_text: str, focus: str, 
                                           detail_level: str, content_type: str,
                                           task_id: str = None) -> Dict[str, Any]:
        """Enhanced with hybrid mapping strategy and context awareness"""
        try:
            from ..tools.tool_recommender_ai_interpreter import ToolRecommenderAIInterpreter
            from ..types.recommendation_types import RecommendationContext, ToolRecommendation, RecommendationResult
            
            # Build context object
            context = RecommendationContext(
                analysis_text=analysis_text,
                focus=focus,
                detail_level=detail_level,
                content_type=content_type,
                task_id=task_id
            )
            
            # Collect dialogue history if continuing session
            if task_id and self.session_repo:
                try:
                    context.dialogue_history = self.session_repo.get_recent_dialogue(task_id, limit=3)
                except Exception as e:
                    self.logger.warning(f"Could not retrieve dialogue history: {e}")
            
            # Extract mentioned files with validation
            valid_files, missing_files = self._extract_mentioned_files(analysis_text)
            context.mentioned_files = valid_files
            context.mentioned_but_missing = missing_files
            
            # Extract questions from analysis
            context.all_questions = self._extract_questions(analysis_text)
            
            # HYBRID STRATEGY: Rule-based mapping first (fast path)
            if context.all_questions:
                rule_mapped = self._map_questions_to_tools_rule_based(
                    context.all_questions, 
                    context.mentioned_files
                )
                context.rule_mapped_tools = rule_mapped['mapped_tools']
                context.unmapped_questions = rule_mapped['unmapped_questions']
            
            # Log what was handled by rules
            self.logger.info(f"Hybrid mapping: {len(context.rule_mapped_tools)} rule-based, "
                           f"{len(context.unmapped_questions)} for AI")
            
            # Pass to AI interpreter for flexible mapping of unmapped questions
            tool_recommender = ToolRecommenderAIInterpreter(self.gemini_client)
            ai_recommendations = await tool_recommender.interpret(context)
            
            # Merge rule-based and AI recommendations
            final_recommendations = self._merge_recommendations(
                rule_based=context.rule_mapped_tools,
                ai_based=ai_recommendations
            )
            
            return final_recommendations
            
        except Exception as e:
            self.logger.error(f"Tool recommendation generation failed: {e}")
            # Return fallback with rule-based recommendations if available
            if 'context' in locals() and context.rule_mapped_tools:
                return {
                    "success": True,
                    "recommendations": {
                        "tools": context.rule_mapped_tools,
                        "summary": "Rule-based recommendations only (AI unavailable)",
                        "total_recommendations": len(context.rule_mapped_tools)
                    },
                    "error": f"AI recommendations failed: {str(e)}"
                }
            return {
                "success": False,
                "error": str(e),
                "recommendations": {
                    "tools": [],
                    "summary": "Tool recommendations unavailable due to error",
                    "total_recommendations": 0
                }
            }
    
    def _merge_recommendations(self, rule_based: List[Dict], ai_based: Dict) -> Dict[str, Any]:
        """Merge rule-based and AI recommendations without duplicates"""
        
        merged_tools = rule_based.copy()
        
        # Add AI recommendations if successful
        if ai_based.get("success") and ai_based.get("recommendations", {}).get("tools"):
            ai_tools = ai_based["recommendations"]["tools"]
            
            # Check for duplicates based on tool name
            existing_tools = {t["tool"] for t in merged_tools}
            
            for ai_tool in ai_tools:
                if ai_tool["tool"] not in existing_tools:
                    # Mark as AI-generated
                    ai_tool["mapping_type"] = "ai"
                    merged_tools.append(ai_tool)
        
        # Sort by confidence/priority
        merged_tools.sort(key=lambda x: (-x.get("confidence", 0.5), x.get("priority", 2)))
        
        # Generate summary
        rule_count = len([t for t in merged_tools if t.get("mapping_type") == "rule_based"])
        ai_count = len([t for t in merged_tools if t.get("mapping_type") == "ai"])
        
        summary = f"Hybrid recommendations: {rule_count} rule-based (fast), {ai_count} AI-based (flexible)"
        
        return {
            "success": True,
            "recommendations": {
                "tools": merged_tools,
                "summary": summary,
                "total_recommendations": len(merged_tools)
            },
            "meta": {
                "rule_based_count": rule_count,
                "ai_based_count": ai_count,
                "ai_contribution": ai_based.get("meta", {})
            }
        }
    
    def _combine_analysis_and_recommendations(self, analysis_text: str, tool_recommendations: Dict[str, Any]) -> str:
        """Enhanced with self-documenting executable format"""
        import json
        
        # Start with the core analysis
        combined_response = analysis_text
        
        # Add tool recommendations section if available
        if tool_recommendations.get("success") and tool_recommendations.get("recommendations", {}).get("tools"):
            tools = tool_recommendations["recommendations"]["tools"]
            summary = tool_recommendations["recommendations"].get("summary", "")
            
            combined_response += "\n\n### 🛠️ Suggested Tools (Executable)\n"
            combined_response += f"*{summary}*\n"
            combined_response += "*Copy and run these commands directly:*\n\n"
            
            for i, tool in enumerate(tools, 1):
                # Show mapping type and confidence
                mapping_type = tool.get('mapping_type', 'ai')
                confidence = tool.get('confidence', 0.5)
                mapping_info = f"[{mapping_type} - {confidence:.0%}]"
                
                combined_response += f"**{i}. {tool['tool']}** {mapping_info}\n"
                
                # Show the reason or question being answered
                reason = tool.get('answers_question') or tool.get('reason', '')
                if reason:
                    combined_response += f"Purpose: {reason}\n"
                
                # Create self-documenting executable command
                params_list = []
                for key, value in tool.get("parameters", {}).items():
                    if isinstance(value, list):
                        value_str = json.dumps(value)
                    elif isinstance(value, str):
                        value_str = f'"{value}"'
                    else:
                        value_str = str(value)
                    params_list.append(f'{key}={value_str}')
                
                executable = f"mcp__gemini-review__{tool['tool']}({', '.join(params_list)})"
                
                # Add the "why" as a comment in the executable block
                combined_response += f"```python\n"
                if reason:
                    combined_response += f"# Answers: {reason}\n"
                combined_response += f"{executable}\n"
                combined_response += f"```\n"
                
                if tool.get("expected_insights"):
                    combined_response += f"Expected Result: {tool['expected_insights']}\n"
                
                combined_response += "\n"
            
            # Summary of mapping strategy used
            meta = tool_recommendations.get("meta", {})
            if meta.get("rule_based_count") is not None and meta.get("ai_based_count") is not None:
                rule_count = meta["rule_based_count"]
                ai_count = meta["ai_based_count"]
                combined_response += f"*Mapping: {rule_count} rule-based (fast), {ai_count} AI-based (flexible)*\n"
        
        elif tool_recommendations.get("success") == False:
            # Tool recommendation failed, add a note with any rule-based recommendations
            combined_response += "\n\n### 🛠️ Tool Recommendations\n"
            if tool_recommendations.get("error"):
                combined_response += f"*Note: {tool_recommendations['error']}*\n"
            else:
                combined_response += "*Tool recommendations temporarily unavailable. Consider using `check_quality` or `analyze_code` for additional analysis.*\n"
        
        return combined_response