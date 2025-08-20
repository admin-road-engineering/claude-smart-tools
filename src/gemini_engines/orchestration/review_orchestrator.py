"""
Review orchestration service that coordinates all components of comprehensive review.
Uses dependency injection pattern for clean separation of concerns and testability.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..tools.interfaces import (
    ISessionManager, IToolExecutor, IIntentParser, IToolSelector, IResultSynthesizer,
    IAnalysisTool, AnalysisResult, ToolStatus
)
from ..services.file_integrity_validator import FileIntegrityValidator
from ..services.file_content_provider import FileContentProvider

logger = logging.getLogger(__name__)


class ReviewOrchestrator:
    """
    Main orchestrator for comprehensive review system.
    
    Coordinates all services using dependency injection pattern:
    - SessionManager: Handles persistence and state
    - ToolExecutor: Manages parallel tool execution
    - IntentParser: Interprets user responses
    - ToolSelector: Determines appropriate tools
    - ResultSynthesizer: Creates comprehensive reports
    
    This design follows Single Responsibility Principle and enables easy testing.
    """
    
    # Directory expansion constants
    MAX_EXPAND_DEPTH = 3
    MAX_EXPAND_FILES = 100
    IGNORED_DIRS = {
        '__pycache__', '.git', 'node_modules', '.venv', 
        'venv', 'env', '.env', 'dist', 'build', '.pytest_cache',
        '.mypy_cache', '.coverage', 'htmlcov'
    }
    IGNORED_FILE_EXTENSIONS = ('.pyc', '.pyo', '.so', '.dll', '.dylib', '.pyd')
    
    def __init__(self,
                 session_manager: ISessionManager,
                 tool_executor: IToolExecutor,
                 intent_parser: IIntentParser,
                 tool_selector: IToolSelector,
                 result_synthesizer: IResultSynthesizer,
                 available_tools: Dict[str, IAnalysisTool],
                 file_validator: FileIntegrityValidator = None):
        """
        Initialize ReviewOrchestrator with injected dependencies.
        
        Args:
            session_manager: Session persistence service
            tool_executor: Tool execution service
            intent_parser: User intent parsing service
            tool_selector: Tool selection service
            result_synthesizer: Report synthesis service
            available_tools: Dictionary mapping tool names to tool instances
            file_validator: File freshness validation service (optional)
        """
        self.session_manager = session_manager
        self.tool_executor = tool_executor
        self.intent_parser = intent_parser
        self.tool_selector = tool_selector
        self.result_synthesizer = result_synthesizer
        self.available_tools = available_tools
        
        # File freshness validation
        self.file_validator = file_validator or FileIntegrityValidator(
            content_provider=FileContentProvider(),
            enable_filtering=True
        )
        
        # Orchestrator configuration
        self.max_dialogue_rounds = 15
        self.min_tools_for_synthesis = 1
        
        # Track orchestration metrics
        self.metrics = {
            'sessions_created': 0,
            'total_dialogue_rounds': 0,
            'tools_executed': 0,
            'synthesis_generated': 0,
            'failed_orchestrations': 0
        }
        
        logger.info(f"ReviewOrchestrator initialized with {len(available_tools)} tools")
    
    async def execute_autonomous_review(self,
                                       file_paths: List[str],
                                       context: Optional[str] = None,
                                       focus: str = "all") -> str:
        """
        Execute a comprehensive review autonomously without dialogue.
        Automatically runs priority tools and synthesizes results.
        
        Args:
            file_paths: Files to be analyzed
            context: Additional context for the review
            focus: Focus area (security, performance, architecture, etc.)
            
        Returns:
            Comprehensive review report as formatted string
        """
        try:
            # Generate task ID for this autonomous review
            task_id = f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"Starting autonomous review {task_id} for {len(file_paths)} files with focus '{focus}'")
            
            # Create session
            session_data = await self.session_manager.create_session(
                task_id=task_id,
                review_type="autonomous_comprehensive_review",
                focus=focus,
                context=context or ""
            )
            
            # ALWAYS start with analyze_code to understand the codebase
            initial_analysis_tool = 'analyze_code'
            initial_results = {}
            
            if initial_analysis_tool in self.available_tools:
                logger.info(f"Starting with {initial_analysis_tool} to understand codebase structure")
                
                # Execute analyze_code first
                initial_context = {
                    'session_id': task_id,
                    'round_number': 1,
                    'focus': focus,
                    'autonomous': True,
                    'with_ai': True
                }
                
                initial_tool = self.available_tools[initial_analysis_tool]
                initial_results = await self.tool_executor.execute_tool_batch(
                    [initial_tool], file_paths, initial_context
                )
                
                # Save initial analysis results
                await self.session_manager.save_tool_results(task_id, 1, initial_results)
                
                # Use the initial analysis to inform tool selection
                # Parse analyze_code output to determine which tools are most relevant
                if initial_results and initial_analysis_tool in initial_results:
                    analysis_result = initial_results[initial_analysis_tool]
                    if analysis_result.is_success and analysis_result.output:
                        # Use Gemini to analyze the code structure and recommend tools
                        logger.info("Initial analysis complete, using AI to determine next tools")
                        
                        # Get AI-driven tool recommendations based on the initial analysis
                        ai_recommended_tools = await self._get_ai_tool_recommendations(
                            initial_analysis=analysis_result.output,
                            file_paths=file_paths,
                            focus=focus,
                            context=context
                        )
                        
                        if ai_recommended_tools:
                            logger.info(f"AI recommended tools: {ai_recommended_tools}")
                            # Override the mechanical selection with AI recommendations
                            tools_to_run = ai_recommended_tools
                            # Skip the standard selector since we have AI recommendations
                            skip_standard_selection = True
                        else:
                            skip_standard_selection = False
                else:
                    skip_standard_selection = False
            
            # Use AI recommendations if available, otherwise fall back to mechanical selection
            if 'skip_standard_selection' in locals() and skip_standard_selection and 'tools_to_run' in locals():
                # We already have AI-recommended tools
                pass
            else:
                # Determine additional tools based on file analysis
                priority_tools = self.tool_selector.determine_priority_tools(file_paths, focus)
                
                # Remove analyze_code if it's in the list (we already ran it)
                if initial_analysis_tool in priority_tools:
                    priority_tools.remove(initial_analysis_tool)
                
                # Don't limit - run all relevant tools that the selector determined
                tools_to_run = priority_tools
                
                if not tools_to_run:
                    # Fallback to default tools if none selected
                    tools_to_run = ['config_validator', 'dependency_mapper']
            
            logger.info(f"Based on initial analysis, will execute: {tools_to_run}")
            
            # Execute additional tools
            tool_instances = [self.available_tools[name] for name in tools_to_run if name in self.available_tools]
            
            if not tool_instances and initial_analysis_tool not in self.available_tools:
                return "## ❌ No tools available for autonomous review\n\nPlease ensure tools are properly configured."
            
            # Execute additional tools (round 2)
            execution_context = {
                'session_id': task_id,
                'round_number': 2,  # This is round 2 after initial analysis
                'focus': focus,
                'autonomous': True,
                'with_ai': True  # Enable AI for comprehensive review
            }
            
            additional_results = {}
            if tool_instances:
                additional_results = await self.tool_executor.execute_tool_batch(
                    tool_instances, file_paths, execution_context
                )
                
                # Save additional results
                await self.session_manager.save_tool_results(task_id, 2, additional_results)
            
            # Combine all results
            all_results = {}
            if initial_analysis_tool in self.available_tools and initial_results:
                all_results.update(initial_results)
            all_results.update(additional_results)
            
            # Use AI to determine if follow-up tools are needed based on findings (Round 3+)
            follow_up_tools = await self._get_ai_follow_up_recommendations(
                current_results=all_results,
                file_paths=file_paths,
                focus=focus,
                context=context
            )
            
            # Execute follow-up tools if any were identified
            if follow_up_tools:
                logger.info(f"Running follow-up tools based on findings: {follow_up_tools}")
                follow_up_instances = [self.available_tools[name] for name in follow_up_tools if name in self.available_tools]
                
                if follow_up_instances:
                    follow_up_context = {
                        'session_id': task_id,
                        'round_number': 3,
                        'focus': focus,
                        'autonomous': True,
                        'with_ai': True,
                        'is_follow_up': True
                    }
                    
                    follow_up_results = await self.tool_executor.execute_tool_batch(
                        follow_up_instances, file_paths, follow_up_context
                    )
                    
                    # Save follow-up results
                    await self.session_manager.save_tool_results(task_id, 3, follow_up_results)
                    
                    # Add to all results
                    all_results.update(follow_up_results)
            
            # Track metrics
            self.metrics['tools_executed'] += len(all_results)
            
            # Filter for successful results
            successful_results = {}
            for tool_name, result in all_results.items():
                if result.is_success:
                    successful_results[tool_name] = result
            
            if not successful_results:
                return "## ⚠️ Autonomous Review - No Successful Results\n\nAll analysis tools failed to execute. Please check the logs for details."
            
            # Generate comprehensive synthesis
            synthesis = await self.result_synthesizer.synthesize_report(
                tool_results=successful_results,
                context=context,
                focus=focus
            )
            
            self.metrics['synthesis_generated'] += 1
            
            # Format final report
            report = f"""## 🤖 Autonomous Comprehensive Review Complete

**Files Analyzed**: {len(file_paths)} files
**Focus Area**: {focus}
**Initial Analysis**: {'✅' if initial_analysis_tool in all_results else '❌'} analyze_code
**Additional Tools Executed**: {', '.join([k for k in all_results.keys() if k != initial_analysis_tool]) if len(all_results) > 1 else 'None'}
**Total Tools**: {len(all_results)}

---

{synthesis}

---

**Session ID**: {task_id}
**Execution Time**: {datetime.now().isoformat()}
"""
            
            logger.info(f"Autonomous review {task_id} completed successfully")
            return report
            
        except Exception as e:
            self.metrics['failed_orchestrations'] += 1
            logger.error(f"Autonomous review failed: {e}")
            return f"## ❌ Autonomous Review Failed\n\nError: {str(e)}\n\nPlease check the logs for details."
    
    async def start_comprehensive_review(self,
                                       task_id: str,
                                       file_paths: List[str],
                                       context: Optional[str] = None,
                                       focus: str = "all") -> Dict[str, Any]:
        """
        Start a new comprehensive review session with proactive analysis.
        
        Unlike autonomous mode, this runs initial analysis and engages user with findings.
        
        Args:
            task_id: Unique identifier for this review session
            file_paths: Files to be analyzed
            context: Additional context for the review
            focus: Focus area (security, performance, architecture, etc.)
            
        Returns:
            Initial session state with analysis findings and engagement questions
        """
        try:
            self.metrics['sessions_created'] += 1
            logger.info(f"Starting proactive comprehensive review {task_id} for {len(file_paths)} files with focus '{focus}'")
            
            # Create new session
            session_data = await self.session_manager.create_session(
                task_id=task_id,
                review_type="comprehensive_review",
                focus=focus,
                context=context or ""
            )
            
            # PROACTIVE APPROACH: Run full analysis immediately, then engage in dialogue about findings
            logger.info(f"Running comprehensive analysis for dialogue engagement")
            
            # Execute analyze_code first to understand the codebase
            initial_analysis_tool = 'analyze_code'
            all_results = {}
            
            if initial_analysis_tool in self.available_tools:
                logger.info(f"Running initial {initial_analysis_tool} to understand codebase structure")
                
                # Execute analyze_code first
                initial_context = {
                    'session_id': task_id,
                    'round_number': 1,
                    'focus': focus,
                    'autonomous': False,  # This is dialogue mode
                    'with_ai': True,
                    'is_initial_analysis': True
                }
                
                initial_tool = self.available_tools[initial_analysis_tool]
                try:
                    initial_results = await self.tool_executor.execute_tool_batch(
                        [initial_tool], file_paths, initial_context
                    )
                    
                    # Save initial analysis results
                    await self.session_manager.save_tool_results(task_id, 1, initial_results)
                    all_results.update(initial_results)
                    logger.info(f"Initial analysis completed: {list(initial_results.keys())}")
                    
                    # Now run additional priority tools automatically (like autonomous mode)
                    if initial_analysis_tool in initial_results and initial_results[initial_analysis_tool].is_success:
                        # Use the initial analysis to inform tool selection
                        analysis_result = initial_results[initial_analysis_tool]
                        
                        # Get AI-driven tool recommendations and run them automatically
                        try:
                            ai_tool_names = await self._get_ai_tool_recommendations(
                                analysis_result.output, file_paths, focus, context
                            )
                            
                            # Run the recommended tools automatically (no limit for comprehensive dialogue)
                            tool_instances = [self.available_tools[name] for name in ai_tool_names if name in self.available_tools]
                            
                            if tool_instances:
                                logger.info(f"Auto-executing priority tools for dialogue: {[tool.name for tool in tool_instances]}")
                                
                                execution_context = {
                                    'session_id': task_id,
                                    'round_number': 2,
                                    'focus': focus,
                                    'autonomous': False,  # This is dialogue mode  
                                    'with_ai': True,
                                    'auto_executed': True
                                }
                                
                                additional_results = await self.tool_executor.execute_tool_batch(
                                    tool_instances, file_paths, execution_context
                                )
                                
                                # Save additional results
                                await self.session_manager.save_tool_results(task_id, 2, additional_results)
                                all_results.update(additional_results)
                                logger.info(f"Auto-executed {len(additional_results)} additional tools")
                                
                        except Exception as auto_exec_error:
                            logger.error(f"Auto tool execution failed: {auto_exec_error}")
                            # Continue with just initial analysis
                    
                except Exception as analysis_error:
                    logger.error(f"Initial analysis failed: {analysis_error}")
                    # Continue with empty results if analysis fails
            
            # Get AI-driven tool recommendations based on files and focus
            tool_recommendations = []
            try:
                # Extract initial analysis for recommendations
                initial_analysis_output = None
                if initial_results and initial_analysis_tool in initial_results:
                    analysis_result = initial_results[initial_analysis_tool]
                    if analysis_result.is_success:
                        initial_analysis_output = analysis_result.output
                
                ai_tool_names = await self._get_ai_tool_recommendations(
                    initial_analysis_output, file_paths, focus, context
                )
                # Convert AI tool names to proper recommendation format
                tool_recommendations = []
                for tool_name in ai_tool_names:
                    rationale = self._get_ai_tool_rationale(tool_name, focus, initial_analysis_output)
                    tool_recommendations.append({
                        'tool_name': tool_name,
                        'rationale': rationale,
                        'estimated_time': self._get_tool_time_estimate(tool_name)
                    })
            except Exception as rec_error:
                logger.error(f"AI tool recommendations failed: {rec_error}")
                # Fallback to rule-based recommendations
                priority_tools = self.tool_selector.determine_priority_tools(file_paths, focus)
                tool_recommendations = self.tool_selector.get_tool_recommendations(
                    file_paths, focus, max_tools=3
                )
            
            # Generate proactive message based on actual tool execution results
            if all_results:
                # We have actual tool results - generate comprehensive dialogue starter
                successful_results = {name: result for name, result in all_results.items() if result.is_success}
                
                if successful_results:
                    initial_message = await self._generate_results_based_dialogue(
                        successful_results, focus, file_paths, context
                    )
                else:
                    initial_message = self._generate_fallback_initial_message(
                        tool_recommendations, focus, file_paths
                    )
            else:
                # Fallback if no tools were executed successfully
                initial_message = self._generate_fallback_initial_message(
                    tool_recommendations, focus, file_paths
                )
            
            # Prepare enriched initial state
            successful_tools = [name for name, result in all_results.items() if result.is_success]
            current_round = 2 if len(all_results) > 1 else (1 if all_results else 0)
            
            initial_state = {
                'session_id': task_id,
                'status': 'active',
                'current_round': current_round,
                'file_paths': file_paths,
                'focus': focus,
                'context': context,
                'tools_executed': successful_tools,
                'total_tools_run': len(all_results),
                'has_results_to_discuss': bool(successful_tools),
                'next_action': 'dialogue_engagement',
                'message': initial_message
            }
            
            logger.info(f"Proactive comprehensive review {task_id} started successfully with {'analysis' if initial_results else 'recommendations'}")
            return initial_state
            
        except Exception as e:
            self.metrics['failed_orchestrations'] += 1
            logger.error(f"Failed to start comprehensive review {task_id}: {e}")
            raise
    
    async def continue_review_dialogue(self,
                                     task_id: str,
                                     user_response: str,
                                     claude_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Continue an existing review dialogue based on user input.
        
        Args:
            task_id: Session identifier
            user_response: User's response/instruction
            claude_context: Additional context from Claude
            
        Returns:
            Updated session state with next action
        """
        try:
            # Get session state
            session = await self.session_manager.get_session(task_id)
            if not session:
                raise ValueError(f"Session {task_id} not found")
            
            current_round = session.get('total_rounds', 0) + 1
            self.metrics['total_dialogue_rounds'] += 1
            
            # Parse user intent
            intent = await self.intent_parser.parse_user_intent(user_response)
            logger.info(f"Parsed intent for round {current_round}: {intent.action if intent else 'unknown'}")
            
            # Handle the intent
            response = await self._handle_user_intent(
                task_id=task_id,
                session=session,
                round_number=current_round,
                intent=intent,
                user_response=user_response,
                claude_context=claude_context
            )
            
            # Save dialogue turn
            await self.session_manager.add_dialogue_turn(
                task_id=task_id,
                round_number=current_round,
                user_input=user_response,
                ai_response=response.get('message', 'No response generated'),
                metadata={
                    'intent': intent.model_dump() if intent and hasattr(intent, 'model_dump') else str(intent),
                    'action_taken': response.get('action_taken'),
                    'tools_executed': response.get('tools_executed', [])
                }
            )
            
            # Update response with session info
            response.update({
                'session_id': task_id,
                'current_round': current_round,
                'max_rounds': self.max_dialogue_rounds
            })
            
            return response
            
        except Exception as e:
            self.metrics['failed_orchestrations'] += 1
            logger.error(f"Failed to continue dialogue for session {task_id}: {e}")
            raise
    
    async def _handle_user_intent(self,
                                task_id: str,
                                session: Dict[str, Any],
                                round_number: int,
                                intent,  # IntentResult object
                                user_response: str,
                                claude_context: Optional[str]) -> Dict[str, Any]:
        """Handle different user intents and route to appropriate actions"""
        
        action = intent.action if intent else 'unknown'
        
        if action == 'run_tool':
            return await self._handle_run_tool_intent(task_id, session, intent, round_number)
        
        elif action == 'synthesize':
            return await self._handle_synthesize_intent(task_id, session, round_number)
        
        elif action == 'retry_failed':
            return await self._handle_retry_failed_intent(task_id, session, round_number)
        
        elif action == 'specify_files':
            return await self._handle_specify_files_intent(task_id, session, intent, round_number)
        
        elif action == 'explain':
            return await self._handle_explain_intent(task_id, session, intent, round_number)
        
        elif action == 'help':
            return await self._handle_help_intent(task_id, session, round_number)
        
        elif action == 'end_session':
            return await self._handle_end_session_intent(task_id, session, round_number)
        
        elif action == 'continue':
            return await self._handle_continue_intent(task_id, session, round_number)
        
        elif action == 'continue_dialogue':
            return await self._handle_continue_dialogue_intent(task_id, session, intent, user_response, round_number)
        
        else:
            return await self._handle_unknown_intent(task_id, session, intent, user_response, round_number)
    
    async def _handle_run_tool_intent(self, task_id: str, session: Dict[str, Any], 
                                    intent, round_number: int) -> Dict[str, Any]:
        """Handle request to run specific tools"""
        
        # Extract tool selection from intent
        requested_tool = intent.tool_name if intent else None
        requested_files = intent.files if intent else []
        requested_dirs = intent.directories if intent else []
        
        # Determine tools to run
        if requested_tool and requested_tool in self.available_tools:
            tools_to_run = [requested_tool]
        else:
            # Fall back to priority tool selection
            all_files = requested_files + [f for d in requested_dirs for f in self._expand_directory(d)]
            if not all_files:
                # Use original session files if no new files specified
                all_files = session.get('file_paths', [])
            
            tools_to_run = self.tool_selector.determine_priority_tools(
                all_files, 
                session.get('focus', 'all')
            )  # No limit - run all relevant tools
        
        # Execute selected tools
        tool_instances = [self.available_tools[name] for name in tools_to_run if name in self.available_tools]
        if not tool_instances:
            return {
                'status': 'error',
                'message': f"No valid tools found to execute. Available tools: {list(self.available_tools.keys())}",
                'next_action': 'clarify_tools'
            }
        
        # Run tools
        execution_context = {
            'session_id': task_id,
            'round_number': round_number,
            'focus': session.get('focus', 'all'),
            'dry_run': False  # IntentResult doesn't have dry_run attribute
        }
        
        file_paths = requested_files or session.get('file_paths', [])
        results = await self.tool_executor.execute_tool_batch(
            tool_instances, file_paths, execution_context
        )
        
        # Save results
        await self.session_manager.save_tool_results(task_id, round_number, results)
        
        # Track metrics
        self.metrics['tools_executed'] += len(results)
        
        # Analyze results
        successful_tools = [name for name, result in results.items() if result.is_success]
        failed_tools = [name for name, result in results.items() if result.is_failure]
        
        # Generate response
        message = self._generate_tool_execution_summary(results, successful_tools, failed_tools)
        
        next_action = 'continue_dialogue'
        if failed_tools:
            next_action = 'handle_failures'
        elif len(successful_tools) >= self.min_tools_for_synthesis:
            next_action = 'ready_for_synthesis'
        
        return {
            'status': 'success',
            'action_taken': 'tool_execution',
            'tools_executed': tools_to_run,
            'successful_tools': successful_tools,
            'failed_tools': failed_tools,
            'results_summary': message,
            'message': message,
            'next_action': next_action
        }
    
    async def _handle_synthesize_intent(self, task_id: str, session: Dict[str, Any], 
                                      round_number: int) -> Dict[str, Any]:
        """Handle request to synthesize final report"""
        
        # Get all tool results from session
        all_results = await self.session_manager.get_tool_results(task_id)
        
        # Flatten results from all rounds
        consolidated_results = {}
        for round_results in all_results.values():
            consolidated_results.update(round_results)
        
        if not consolidated_results:
            return {
                'status': 'error',
                'message': 'No tool results available for synthesis. Please run some analysis tools first.',
                'next_action': 'run_tools'
            }
        
        # Generate comprehensive synthesis
        synthesis_report = await self.result_synthesizer.synthesize_report(
            tool_results=consolidated_results,
            context=session.get('context'),
            focus=session.get('focus', 'all')
        )
        
        self.metrics['synthesis_generated'] += 1
        
        return {
            'status': 'success',
            'action_taken': 'synthesis',
            'synthesis_report': synthesis_report,
            'message': f"## 📋 Comprehensive Review Complete\n\n{synthesis_report}",
            'next_action': 'session_complete',
            'tools_analyzed': list(consolidated_results.keys()),
            'total_tools': len(consolidated_results)
        }
    
    async def _handle_retry_failed_intent(self, task_id: str, session: Dict[str, Any], 
                                        round_number: int) -> Dict[str, Any]:
        """Handle request to retry failed tools"""
        
        failed_tool_names = await self.session_manager.get_failed_tools(task_id)
        if not failed_tool_names:
            return {
                'status': 'info',
                'message': 'No failed tools to retry.',
                'next_action': 'continue_dialogue'
            }
        
        # Get tool instances for failed tools
        failed_tools = [self.available_tools[name] for name in failed_tool_names 
                       if name in self.available_tools]
        
        if not failed_tools:
            return {
                'status': 'error',
                'message': f'Failed tools no longer available: {failed_tool_names}',
                'next_action': 'continue_dialogue'
            }
        
        # Retry execution
        execution_context = {
            'session_id': task_id,
            'round_number': round_number,
            'focus': session.get('focus', 'all'),
            'retry_attempt': True
        }
        
        retry_results = await self.tool_executor.retry_failed_tools(
            failed_tools, 
            session.get('file_paths', []), 
            execution_context
        )
        
        # Save retry results
        await self.session_manager.save_tool_results(task_id, round_number, retry_results)
        
        # Clear successfully retried tools from failed list
        successful_retries = [name for name, result in retry_results.items() if result.is_success]
        if successful_retries:
            await self.session_manager.clear_failed_tools(task_id, successful_retries)
        
        # Generate response
        message = f"## 🔄 Retry Results\n\n"
        if successful_retries:
            message += f"**✅ Successfully retried:** {', '.join(successful_retries)}\n\n"
        
        still_failed = [name for name, result in retry_results.items() if result.is_failure]
        if still_failed:
            message += f"**❌ Still failing:** {', '.join(still_failed)}\n\n"
        
        return {
            'status': 'success',
            'action_taken': 'retry_failed',
            'retried_tools': list(retry_results.keys()),
            'successful_retries': successful_retries,
            'still_failed': still_failed,
            'message': message,
            'next_action': 'continue_dialogue' if still_failed else 'ready_for_synthesis'
        }
    
    async def _handle_specify_files_intent(self, task_id: str, session: Dict[str, Any],
                                         intent, round_number: int) -> Dict[str, Any]:
        """Handle request to specify different files"""
        
        new_files = intent.files if intent else []
        new_dirs = intent.directories if intent else []
        
        # Expand directories
        all_files = new_files + [f for d in new_dirs for f in self._expand_directory(d)]
        
        if not all_files:
            return {
                'status': 'error',
                'message': 'No valid files specified. Please provide file paths.',
                'next_action': 'clarify_files'
            }
        
        # Update session with new files (this would require extending session manager)
        # For now, we'll include it in the response for the next tool execution
        
        # Re-analyze tool selection for new files
        new_priority_tools = self.tool_selector.determine_priority_tools(
            all_files, session.get('focus', 'all')
        )
        new_recommendations = self.tool_selector.get_tool_recommendations(
            all_files, session.get('focus', 'all'), max_tools=5
        )
        
        message = f"## 📁 Files Updated\n\n"
        message += f"**New file set:** {', '.join(all_files[:10])}{'...' if len(all_files) > 10 else ''}\n\n"
        message += f"**Recommended tools for these files:**\n"
        for rec in new_recommendations[:3]:
            message += f"- **{rec['tool_name']}**: {rec['rationale']}\n"
        
        return {
            'status': 'success',
            'action_taken': 'specify_files',
            'new_files': all_files,
            'updated_tool_recommendations': new_recommendations,
            'priority_tools': new_priority_tools,
            'message': message,
            'next_action': 'tool_execution'
        }
    
    async def _handle_explain_intent(self, task_id: str, session: Dict[str, Any],
                                   intent: Dict[str, Any], round_number: int) -> Dict[str, Any]:
        """Handle request for explanations"""
        
        # Get recent tool results for context
        recent_results = await self.session_manager.get_tool_results(task_id)
        
        explanation = "## 🤔 Comprehensive Review Explanation\n\n"
        explanation += "This review system orchestrates multiple analysis tools to provide comprehensive code insights:\n\n"
        
        # Explain available tools
        explanation += "**Available Tools:**\n"
        for tool_name in self.available_tools:
            explanation += f"- **{tool_name}**: Specialized analysis capabilities\n"
        
        if recent_results:
            explanation += f"\n**Recent Analysis:** {len(recent_results)} rounds completed with various tools.\n"
        
        explanation += "\n**Available Actions:**\n"
        explanation += "- `run [tool_name]` - Execute specific analysis tool\n"
        explanation += "- `synthesize` - Generate comprehensive final report\n"
        explanation += "- `retry` - Retry any failed tools\n"
        explanation += "- `files=['path1', 'path2']` - Specify different files to analyze\n"
        
        return {
            'status': 'success',
            'action_taken': 'explain',
            'message': explanation,
            'next_action': 'continue_dialogue'
        }
    
    async def _handle_help_intent(self, task_id: str, session: Dict[str, Any], 
                                round_number: int) -> Dict[str, Any]:
        """Handle help requests"""
        
        help_message = "## 🆘 Comprehensive Review Help\n\n"
        help_message += "**Commands you can use:**\n\n"
        help_message += "- **`run config`** - Run configuration validator\n"
        help_message += "- **`run security`** - Run security analysis\n"
        help_message += "- **`run dependencies`** - Analyze dependencies\n"
        help_message += "- **`synthesize`** - Generate final comprehensive report\n"
        help_message += "- **`retry`** - Retry any failed tools\n"
        help_message += "- **`files=['src/main.py']`** - Specify different files\n"
        help_message += "- **`help`** - Show this help message\n"
        help_message += "- **`done`** - End the review session\n\n"
        
        # Show session status
        failed_tools = await self.session_manager.get_failed_tools(task_id)
        if failed_tools:
            help_message += f"**⚠️ Failed tools available for retry:** {', '.join(failed_tools)}\n\n"
        
        help_message += "**Current Session:**\n"
        help_message += f"- **Focus:** {session.get('focus', 'all')}\n"
        help_message += f"- **Files:** {len(session.get('file_paths', []))} files to analyze\n"
        help_message += f"- **Round:** {session.get('total_rounds', 0)}/{self.max_dialogue_rounds}\n"
        
        return {
            'status': 'success',
            'action_taken': 'help',
            'message': help_message,
            'next_action': 'continue_dialogue'
        }
    
    async def _handle_end_session_intent(self, task_id: str, session: Dict[str, Any], 
                                       round_number: int) -> Dict[str, Any]:
        """Handle session termination"""
        
        # Generate final summary
        all_results = await self.session_manager.get_tool_results(task_id)
        total_tools_run = sum(len(round_results) for round_results in all_results.values())
        
        final_message = "## 🏁 Review Session Complete\n\n"
        final_message += f"**Session Summary:**\n"
        final_message += f"- **Total Rounds:** {round_number}\n"
        final_message += f"- **Tools Executed:** {total_tools_run}\n"
        final_message += f"- **Focus Area:** {session.get('focus', 'all')}\n\n"
        
        if total_tools_run > 0:
            final_message += "**💡 Tip:** Use `synthesize` to generate a comprehensive final report from all analysis results.\n"
        else:
            final_message += "**Note:** No analysis tools were executed in this session.\n"
        
        return {
            'status': 'session_ended',
            'action_taken': 'end_session',
            'session_summary': {
                'total_rounds': round_number,
                'tools_executed': total_tools_run,
                'focus': session.get('focus', 'all')
            },
            'message': final_message,
            'next_action': 'session_complete'
        }
    
    async def _handle_continue_intent(self, task_id: str, session: Dict[str, Any], 
                                    round_number: int) -> Dict[str, Any]:
        """Handle continue/proceed requests"""
        
        # Analyze current session state to determine best next action
        failed_tools = await self.session_manager.get_failed_tools(task_id)
        all_results = await self.session_manager.get_tool_results(task_id)
        total_successful_tools = sum(
            len([r for r in round_results.values() if r.is_success])
            for round_results in all_results.values()
        )
        
        if failed_tools:
            suggestion = "retry failed tools"
            next_action = "retry_failed"
        elif total_successful_tools >= self.min_tools_for_synthesis:
            suggestion = "generate synthesis report"
            next_action = "synthesize"
        else:
            suggestion = "run more analysis tools"
            next_action = "run_tools"
        
        message = f"## ⏭️ Ready to Continue\n\n"
        message += f"**Suggested next step:** {suggestion}\n\n"
        
        if failed_tools:
            message += f"**Failed tools to retry:** {', '.join(failed_tools)}\n"
        
        message += f"**Tools completed so far:** {total_successful_tools}\n"
        message += f"**Session progress:** Round {round_number}/{self.max_dialogue_rounds}\n"
        
        return {
            'status': 'ready_to_continue',
            'action_taken': 'continue',
            'suggested_action': suggestion,
            'failed_tools': failed_tools,
            'successful_tools_count': total_successful_tools,
            'message': message,
            'next_action': next_action
        }
    
    async def _handle_continue_dialogue_intent(self, task_id: str, session: Dict[str, Any],
                                              intent: Dict[str, Any], user_response: str,
                                              round_number: int) -> Dict[str, Any]:
        """
        Handle technical response continuation with AI follow-up.
        
        Generates contextual follow-up using Gemini based on the user's technical response
        and current session context.
        """
        try:
            # Extract technical topics from intent
            extracted_entities = intent.extracted_entities if intent else {}
            detected_topics = extracted_entities.get('detected_topics', []) if extracted_entities else []
            reasoning = extracted_entities.get('reasoning', '') if extracted_entities else ''
            
            # Get session context for continuity
            session_context = {
                'focus': session.get('focus', 'all'),
                'files_analyzed': session.get('file_paths', []),
                'previous_findings': await self._get_recent_findings_summary(task_id),
                'detected_topics': detected_topics,
                'round_number': round_number,
                'parsing_method': intent.parsing_method if intent else 'unknown'
            }
            
            # Generate contextual follow-up using Gemini
            follow_up_analysis = await self._generate_contextual_follow_up(
                user_technical_response=user_response,
                session_context=session_context
            )
            
            logger.info(f"Generated technical dialogue follow-up for session {task_id}, topics: {detected_topics}")
            
            return {
                'status': 'success',
                'action_taken': 'continue_dialogue',
                'technical_topics_detected': detected_topics,
                'parsing_reasoning': reasoning,
                'follow_up_analysis': follow_up_analysis,
                'message': follow_up_analysis,
                'next_action': 'continue_dialogue',
                'session_continuity': True,
                'round_info': f"Technical dialogue round {round_number}"
            }
            
        except Exception as e:
            logger.error(f"Failed to handle continue_dialogue intent for session {task_id}: {e}")
            
            # Graceful fallback
            return {
                'status': 'partial_success',
                'action_taken': 'continue_dialogue_fallback',
                'message': f"""## 🤔 Thank you for that detailed technical analysis!

I appreciate your insights about the code review findings. Let me process your analysis and provide specific recommendations for next steps.

**Your response included**: {', '.join(detected_topics) if detected_topics else 'technical discussion'}

**Next Actions**:
- Use `run analyze_code` to examine current file structure
- Use `run check_quality` for comprehensive validation  
- Use `synthesize` when ready for final recommendations

**Current Session**: Round {round_number}, Focus: {session.get('focus', 'all')}
""",
                'next_action': 'continue_dialogue',
                'error': str(e)
            }
    
    async def _get_recent_findings_summary(self, task_id: str) -> str:
        """Get a brief summary of recent findings for context"""
        try:
            # Get recent tool results from session
            all_results = await self.session_manager.get_tool_results(task_id)
            
            if not all_results:
                return "No previous analysis available"
            
            # Get the most recent round's results
            latest_round = max(all_results.keys()) if all_results else 0
            recent_results = all_results.get(latest_round, {})
            
            if not recent_results:
                return "No recent tool results"
            
            # Create brief summary
            summaries = []
            for tool_name, result in recent_results.items():
                if hasattr(result, 'is_success') and result.is_success:
                    # Extract brief summary from result
                    if hasattr(result, 'output') and isinstance(result.output, dict):
                        summary = result.output.get('summary', result.output.get('analysis', ''))[:100]
                        if summary:
                            summaries.append(f"{tool_name}: {summary}")
                    elif hasattr(result, 'output') and isinstance(result.output, str):
                        summary = result.output[:100]
                        summaries.append(f"{tool_name}: {summary}")
            
            if summaries:
                return "; ".join(summaries[:3])  # Limit to 3 most recent
            else:
                return "Recent analysis completed but no detailed findings available"
                
        except Exception as e:
            logger.error(f"Failed to get recent findings summary: {e}")
            return "Unable to retrieve recent findings"
    
    async def _generate_contextual_follow_up(self, user_technical_response: str,
                                           session_context: Dict[str, Any]) -> str:
        """Generate intelligent follow-up using Gemini with full context"""
        
        context_prompt = f"""You are continuing a technical dialogue with Claude about code analysis and review.

## Session Context:
- **Focus Area**: {session_context['focus']}
- **Files Being Analyzed**: {len(session_context['files_analyzed'])} files
- **Round**: {session_context['round_number']}
- **Detected Topics**: {', '.join(session_context['detected_topics'])}
- **Parsing Method**: {session_context['parsing_method']}

## Previous Findings Summary:
{session_context.get('previous_findings', 'No previous analysis available')}

## Claude's Technical Response:
{user_technical_response}

## Your Task:
Provide a thoughtful, technical follow-up response that:
1. **Acknowledges** Claude's specific technical points and insights
2. **Builds on** the analysis with additional technical considerations
3. **Asks specific follow-up questions** to deepen the investigation  
4. **Suggests concrete next steps** for resolution or further analysis

Keep the response:
- **Technical and substantive** (this is a technical dialogue)
- **Focused on actionable insights** rather than general commentary
- **Specific to the code analysis context** 
- **Formatted in markdown** for readability
- **Under 500 words** for optimal dialogue flow

If Claude mentioned specific functions, files, or errors, reference them directly in your response.
"""
        
        try:
            follow_up, model_used, attempts = await self.result_synthesizer.gemini_client.generate_content(
                context_prompt,
                model_name='flash'  # Use flash for responsive dialogue
            )
            
            logger.info(f"Generated contextual follow-up using {model_used} model in {attempts} attempts")
            return follow_up
            
        except Exception as e:
            logger.error(f"Failed to generate contextual follow-up: {e}")
            
            # Fallback response when Gemini is unavailable
            topics_text = ', '.join(session_context['detected_topics']) if session_context['detected_topics'] else 'your technical analysis'
            
            return f"""## 🔍 Thank you for that detailed technical insight!

I appreciate your analysis regarding {topics_text}. Your technical perspective helps deepen our understanding of the codebase.

**Based on your response, let me suggest some focused next steps:**

• **Deep Dive Analysis**: Use `run analyze_code` to examine the specific components you mentioned
• **Quality Assessment**: Use `run check_quality` with security focus if you identified potential security concerns  
• **Dependency Review**: Use `run dependency_mapper` if architectural issues were discussed
• **Synthesis**: Use `synthesize` when ready to consolidate all findings into actionable recommendations

**Current Session Progress**: 
- Round {session_context['round_number']} of technical dialogue
- Focus: {session_context['focus']}
- Files under review: {len(session_context['files_analyzed'])}

Would you like to proceed with any of these analysis tools, or do you have additional technical questions about the findings?
"""
    
    async def _handle_unknown_intent(self, task_id: str, session: Dict[str, Any], 
                                   intent: Dict[str, Any], user_response: str, 
                                   round_number: int) -> Dict[str, Any]:
        """Handle unrecognized intents"""
        
        message = f"## ❓ Intent Not Recognized\n\n"
        message += f"I didn't understand: `{user_response[:100]}{'...' if len(user_response) > 100 else ''}`\n\n"
        message += f"**Suggested actions:**\n"
        message += f"- Type `help` for available commands\n"
        message += f"- Type `run [tool_name]` to execute analysis\n"
        message += f"- Type `synthesize` for comprehensive report\n"
        message += f"- Type `done` to end session\n\n"
        
        # Include intent parsing debug info
        if intent and intent.confidence > 0:
            message += f"**Debug:** Detected action '{intent.action}' "
            message += f"with {intent.confidence:.1%} confidence\n"
        
        return {
            'status': 'clarification_needed',
            'action_taken': 'unknown_intent',
            'original_input': user_response,
            'parsed_intent': intent.model_dump() if intent and hasattr(intent, 'model_dump') else str(intent),
            'message': message,
            'next_action': 'clarify_intent'
        }
    
    def _generate_initial_message(self, tool_recommendations: List[Dict], 
                                file_complexity: Dict[str, Any]) -> str:
        """Generate initial message for new review session"""
        
        message = "## 🚀 Comprehensive Review Started\n\n"
        message += f"**File Analysis:**\n"
        message += f"- **Total files:** {file_complexity['total_files']}\n"
        message += f"- **File types:** {file_complexity['file_diversity']} different extensions\n"
        message += f"- **Complexity score:** {file_complexity['complexity_score']:.1f}/10.0\n\n"
        
        message += f"**🛠️ Recommended Tools (Top 3):**\n"
        for i, rec in enumerate(tool_recommendations[:3], 1):
            message += f"{i}. **{rec['tool_name']}** - {rec['rationale']} ({rec['estimated_time']})\n"
        
        message += f"\n**Next Steps:**\n"
        message += f"- Type `run [tool_name]` to execute specific analysis\n"
        message += f"- Type `run config` for configuration validation\n"
        message += f"- Type `help` for all available commands\n"
        
        return message
    
    def _generate_tool_execution_summary(self, results: Dict[str, AnalysisResult],
                                       successful_tools: List[str],
                                       failed_tools: List[str]) -> str:
        """Generate summary of tool execution results"""
        
        message = f"## 🔧 Tool Execution Complete\n\n"
        
        if successful_tools:
            message += f"**✅ Successful ({len(successful_tools)}):**\n"
            for tool_name in successful_tools:
                result = results[tool_name]
                message += f"- **{tool_name}** ({result.execution_time_seconds:.1f}s)\n"
            message += "\n"
        
        if failed_tools:
            message += f"**❌ Failed ({len(failed_tools)}):**\n"
            for tool_name in failed_tools:
                result = results[tool_name]
                error_msg = result.error_message or "Unknown error"
                message += f"- **{tool_name}**: {error_msg[:100]}{'...' if len(error_msg) > 100 else ''}\n"
            message += "\n"
        
        # Suggest next actions
        message += f"**Next Actions:**\n"
        if failed_tools:
            message += f"- Type `retry` to retry failed tools\n"
        if len(successful_tools) >= self.min_tools_for_synthesis:
            message += f"- Type `synthesize` to generate comprehensive report\n"
        message += f"- Type `run [tool_name]` to run additional analysis\n"
        message += f"- Type `help` for more options\n"
        
        return message
    
    async def _generate_results_based_dialogue(self,
                                             successful_results: Dict[str, 'AnalysisResult'],
                                             focus: str,
                                             file_paths: List[str],
                                             context: Optional[str] = None) -> str:
        """
        Generate rich dialogue based on actual tool execution results.
        This provides the same quality of feedback as autonomous mode.
        """
        try:
            # Extract key findings from each tool result
            findings_by_tool = {}
            for tool_name, result in successful_results.items():
                if result.is_success and result.output:
                    # Extract meaningful content from result
                    if isinstance(result.output, str):
                        findings_by_tool[tool_name] = result.output[:1500]
                    elif isinstance(result.output, dict):
                        findings_by_tool[tool_name] = str(result.output.get('analysis', result.output))[:1500]
                    else:
                        findings_by_tool[tool_name] = str(result.output)[:1500]
            
            # Build comprehensive findings summary
            findings_summary = ""
            for tool_name, findings in findings_by_tool.items():
                findings_summary += f"\n### {tool_name} Results:\n{findings}\n"
            
            # Create rich dialogue prompt for Gemini
            dialogue_prompt = f"""You are engaging in a comprehensive code review dialogue with Claude Code.
Multiple analysis tools have been executed and produced specific findings.

## Tool Execution Results:
{findings_summary}

## Review Context:
- **Files Analyzed**: {len(file_paths)} files
- **Focus Area**: {focus}
- **Tools Executed**: {', '.join(successful_results.keys())}
{f'- **Additional Context**: {context}' if context else ''}

## Your Task:
Based on the actual tool results, create a rich, detailed dialogue response that:

1. **Synthesizes the key findings** from all tools (3-5 specific observations with file references)
2. **Identifies critical issues** that need immediate attention (if any)
3. **Highlights interesting patterns** discovered across the analysis
4. **Asks specific technical questions** based on the actual findings
5. **Recommends concrete next steps** with tool suggestions

Make it highly specific to the actual findings, not generic. Reference specific files, patterns, or issues found.

Format in markdown with:
- ## 🔍 Multi-Tool Analysis Complete
- ### Key Findings (with specific details from results)
- ### Critical Issues (if any)
- ### Technical Questions for Discussion
- ### Recommended Next Steps

Keep it detailed but under 600 words."""

            # Get AI synthesis response
            ai_response, model_used, attempts = await self.result_synthesizer.gemini_client.generate_content(
                dialogue_prompt,
                model_name='flash'  # Use flash for quality dialogue
            )
            
            logger.info(f"Generated rich results-based dialogue using {model_used} model in {attempts} attempts")
            return ai_response
            
        except Exception as e:
            logger.error(f"Failed to generate results-based dialogue: {e}")
            # Fallback to structured summary of results
            return self._generate_fallback_results_summary(successful_results, focus, file_paths)
    
    def _generate_fallback_results_summary(self,
                                          successful_results: Dict[str, 'AnalysisResult'],
                                          focus: str,
                                          file_paths: List[str]) -> str:
        """Generate fallback summary when AI synthesis fails"""
        
        message = f"## 🔍 Multi-Tool Analysis Complete\n\n"
        message += f"**Files Analyzed**: {len(file_paths)}\n"
        message += f"**Focus Area**: {focus}\n"
        message += f"**Tools Executed**: {len(successful_results)}\n\n"
        
        message += "### Analysis Results:\n\n"
        for tool_name, result in successful_results.items():
            message += f"**{tool_name}** ✅\n"
            if result.execution_time_seconds:
                message += f"- Completed in {result.execution_time_seconds:.1f}s\n"
            message += "- Analysis available for review\n\n"
        
        message += "### Next Steps:\n"
        message += "- Review the findings from each tool\n"
        message += "- Ask specific questions about areas of concern\n"
        message += "- Request deeper analysis on specific findings\n"
        message += "- Type `synthesize` for a comprehensive report\n\n"
        
        return message

    async def _generate_proactive_initial_message(self, 
                                                analysis_result: AnalysisResult,
                                                tool_recommendations: List[Dict],
                                                focus: str,
                                                file_paths: List[str]) -> str:
        """Generate proactive initial message using Gemini to analyze findings and engage user"""
        
        try:
            # Extract analysis output for AI processing
            analysis_output = ""
            if hasattr(analysis_result, 'output') and analysis_result.output:
                if isinstance(analysis_result.output, str):
                    analysis_output = analysis_result.output[:2000]  # First 2000 chars
                elif isinstance(analysis_result.output, dict):
                    analysis_output = str(analysis_result.output.get('analysis', analysis_result.output))[:2000]
                else:
                    analysis_output = str(analysis_result.output)[:2000]
            
            # Create engagement prompt for Gemini
            engagement_prompt = f"""You are starting a comprehensive code review dialogue with Claude Code.

## Initial Analysis Results:
{analysis_output}

## Review Context:
- **Files**: {len(file_paths)} files being analyzed
- **Focus**: {focus}
- **Tool Recommendations**: {[rec.get('tool_name', 'unknown') for rec in tool_recommendations[:3]]}

## Your Task:
Based on the initial analysis, create an engaging, technical dialogue starter that:

1. **Summarizes the key architectural/technical findings** from the analysis (2-3 bullet points)
2. **Identifies 2-3 specific areas that warrant deeper investigation** 
3. **Asks thoughtful follow-up questions** to guide the conversation
4. **Suggests specific next tools** based on the findings

Make it conversational but technically substantive. Focus on actionable insights rather than generic observations.

Format in markdown with:
- ## 🔍 Initial Code Analysis Complete
- Brief findings summary
- Specific technical questions for Claude
- Tool recommendations with rationale

Keep under 400 words for optimal dialogue flow."""

            # Get AI engagement response
            ai_response, model_used, attempts = await self.result_synthesizer.gemini_client.generate_content(
                engagement_prompt,
                model_name='flash'  # Use flash for responsive dialogue
            )
            
            logger.info(f"Generated proactive initial message using {model_used} model in {attempts} attempts")
            return ai_response
            
        except Exception as e:
            logger.error(f"Failed to generate proactive initial message: {e}")
            # Fallback to structured message based on analysis
            return self._generate_fallback_initial_message(tool_recommendations, focus, file_paths, analysis_result)
    
    def _generate_fallback_initial_message(self, 
                                         tool_recommendations: List[Dict],
                                         focus: str,
                                         file_paths: List[str],
                                         analysis_result: AnalysisResult = None) -> str:
        """Generate fallback initial message when AI generation fails"""
        
        message = f"## 🔍 Code Review Session Started\n\n"
        
        if analysis_result and analysis_result.is_success:
            message += f"**Initial Analysis Complete** ✅\n"
            message += f"I've analyzed your {len(file_paths)} files with focus on **{focus}**.\n\n"
            
            # Try to extract key points from analysis
            if hasattr(analysis_result, 'output') and analysis_result.output:
                message += f"**Key Findings:**\n"
                message += f"- Analysis completed successfully in {analysis_result.execution_time_seconds:.1f}s\n"
                message += f"- Focus area: {focus.title()} analysis\n"
                message += f"- Ready for deeper investigation\n\n"
        else:
            message += f"**Analysis Setup** 📋\n"
            message += f"Ready to analyze {len(file_paths)} files with focus on **{focus}**.\n\n"
        
        # Add specific questions based on focus
        if focus == "architecture":
            message += f"**Let's explore your architecture:**\n"
            message += f"• What are the main design patterns or architectural concerns?\n"
            message += f"• Are there dependency relationships you'd like me to examine?\n"
            message += f"• Should we look at interface consistency across modules?\n\n"
        elif focus == "security":
            message += f"**Security Review Focus:**\n"
            message += f"• What types of security vulnerabilities concern you most?\n" 
            message += f"• Should I examine configuration files for security issues?\n"
            message += f"• Are there authentication/authorization patterns to review?\n\n"
        else:
            message += f"**Technical Discussion:**\n"
            message += f"• What specific aspects of the code concern you?\n"
            message += f"• Are there particular patterns or implementations to examine?\n"
            message += f"• What would be most valuable for this review?\n\n"
        
        # Add tool recommendations with rationale
        if tool_recommendations:
            message += f"**🛠️ Recommended Next Steps:**\n"
            for i, rec in enumerate(tool_recommendations[:3], 1):
                # Handle both dict and string formats
                if isinstance(rec, dict):
                    tool_name = rec.get('tool_name', 'unknown')
                    rationale = rec.get('rationale', 'Recommended analysis')
                elif isinstance(rec, str):
                    tool_name = rec
                    rationale = f'Recommended tool for {focus} analysis'
                else:
                    tool_name = str(rec)
                    rationale = 'Recommended analysis'
                
                message += f"{i}. `{tool_name}` - {rationale}\n"
            message += f"\n"
        
        message += f"**How to continue:**\n"
        message += f"• Share your specific concerns or questions\n"
        message += f"• Ask me to run any of the recommended tools\n"
        message += f"• Type `help` for all available commands"
        
        return message
    
    async def _generate_results_based_dialogue(self, 
                                             successful_results: Dict[str, Any],
                                             focus: str,
                                             file_paths: List[str],
                                             context: Optional[str]) -> str:
        """Generate engaging dialogue starter based on actual tool execution results"""
        
        try:
            # Prepare comprehensive analysis summary for Gemini
            analysis_summaries = []
            tools_executed = []
            
            for tool_name, result in successful_results.items():
                tools_executed.append(tool_name)
                
                # Extract meaningful summary from each tool result
                if hasattr(result, 'output') and result.output:
                    if isinstance(result.output, str):
                        summary = result.output[:1500]  # First 1500 chars
                    elif isinstance(result.output, dict):
                        summary = str(result.output.get('analysis', result.output))[:1500]
                    else:
                        summary = str(result.output)[:1500]
                    
                    analysis_summaries.append(f"**{tool_name}**:\n{summary}")
            
            # Create comprehensive dialogue prompt for Gemini
            dialogue_prompt = f"""You are starting a comprehensive code review dialogue with Claude Code after running multiple analysis tools.

## Analysis Results Summary:
{chr(10).join(analysis_summaries)}

## Review Context:
- **Files**: {len(file_paths)} files analyzed
- **Focus**: {focus}
- **Tools Executed**: {', '.join(tools_executed)}
- **Context**: {context or 'General code review'}

## Your Task:
Create an engaging, technical dialogue starter that:

1. **Synthesizes key findings** across all tool results (3-4 main points)
2. **Identifies patterns and insights** that emerge from the combined analysis
3. **Highlights specific areas of concern or interest** that warrant discussion
4. **Asks targeted follow-up questions** to deepen the investigation
5. **Suggests areas for further exploration** based on the findings

Make it conversational yet technically substantive. Focus on:
- **Cross-tool insights** (what patterns emerge across multiple analyses?)
- **Priority issues** (what needs immediate attention?)
- **Architecture implications** (how do findings affect overall design?)
- **Actionable next steps** (what should we investigate further?)

Format in markdown with:
- ## 🔍 Multi-Tool Analysis Complete
- Key findings synthesis (bullet points)
- Specific technical questions for Claude
- Areas for deeper exploration

Keep under 500 words for optimal dialogue flow. Be specific about files, functions, or patterns found."""

            # Get AI dialogue response
            ai_response, model_used, attempts = await self.result_synthesizer.gemini_client.generate_content(
                dialogue_prompt,
                model_name='flash'  # Use flash for responsive dialogue
            )
            
            logger.info(f"Generated results-based dialogue using {model_used} model in {attempts} attempts")
            return ai_response
            
        except Exception as e:
            logger.error(f"Failed to generate results-based dialogue: {e}")
            # Fallback to structured summary of results
            return self._generate_structured_results_summary(successful_results, focus, file_paths)
    
    def _generate_structured_results_summary(self, 
                                           successful_results: Dict[str, Any],
                                           focus: str,
                                           file_paths: List[str]) -> str:
        """Generate structured fallback summary when AI dialogue generation fails"""
        
        message = f"## 🔍 Multi-Tool Analysis Complete\n\n"
        message += f"**Analysis Summary**: Completed comprehensive review of {len(file_paths)} files with focus on **{focus}**.\n\n"
        
        # List tools executed and their status
        message += f"**Tools Executed**:\n"
        for tool_name, result in successful_results.items():
            exec_time = getattr(result, 'execution_time_seconds', 0)
            message += f"- ✅ **{tool_name}** (completed in {exec_time:.1f}s)\n"
        
        message += f"\n**Key Areas Identified**:\n"
        
        # Focus-specific insights
        if focus == "architecture":
            message += f"- Code structure and organizational patterns analyzed\n"
            message += f"- Dependency relationships and coupling assessed\n"
            message += f"- Interface consistency and design patterns reviewed\n"
        elif focus == "security":
            message += f"- Configuration security and vulnerability patterns checked\n"
            message += f"- Code patterns analyzed for security implications\n"
            message += f"- Authentication and authorization patterns reviewed\n"
        else:
            message += f"- Code quality and maintainability patterns analyzed\n"
            message += f"- Architecture and design patterns reviewed\n"
            message += f"- Implementation consistency assessed\n"
        
        message += f"\n**Technical Discussion Points**:\n"
        message += f"• What specific aspects of the analysis results surprise you or align with your expectations?\n"
        message += f"• Are there particular patterns or findings you'd like to explore further?\n"
        message += f"• Which areas should we prioritize for deeper investigation or potential improvements?\n\n"
        
        message += f"**Ready for dialogue** - I have concrete findings from {len(successful_results)} analysis tools to discuss with you."
        
        return message
    
    def _get_ai_tool_rationale(self, tool_name: str, focus: str, analysis_output: Any) -> str:
        """Generate rationale for AI-recommended tool based on analysis"""
        rationales = {
            'config_validator': f'Configuration analysis recommended for {focus} focus',
            'dependency_mapper': f'Dependency analysis crucial for {focus} review',
            'interface_inconsistency_detector': f'Interface consistency important for {focus}',
            'test_coverage_analyzer': f'Test coverage analysis supports {focus} goals',
            'performance_profiler': f'Performance analysis aligns with {focus} focus',
            'api_contract_checker': f'API contract validation relevant for {focus}'
        }
        return rationales.get(tool_name, f'AI-recommended tool for {focus} analysis')
    
    def _get_tool_time_estimate(self, tool_name: str) -> str:
        """Get time estimate for tool execution"""
        estimates = {
            'config_validator': 'Fast (30-60s)',
            'dependency_mapper': 'Medium (45-90s)',
            'interface_inconsistency_detector': 'Medium (60-90s)',
            'test_coverage_analyzer': 'Medium (60-120s)',
            'performance_profiler': 'Fast (30-60s)',
            'api_contract_checker': 'Fast (30-45s)'
        }
        return estimates.get(tool_name, 'Medium (60-90s)')
    
    def get_orchestration_metrics(self) -> Dict[str, Any]:
        """Get orchestration metrics for monitoring"""
        return {
            **self.metrics,
            'available_tools': list(self.available_tools.keys()),
            'max_dialogue_rounds': self.max_dialogue_rounds,
            'config': {
                'min_tools_for_synthesis': self.min_tools_for_synthesis
            }
        }
    
    def reset_metrics(self) -> None:
        """Reset orchestration metrics"""
        self.metrics = {
            'sessions_created': 0,
            'total_dialogue_rounds': 0,
            'tools_executed': 0,
            'synthesis_generated': 0,
            'failed_orchestrations': 0
        }
        logger.info("Orchestration metrics reset")
    
    async def _get_ai_tool_recommendations(self, 
                                          initial_analysis: Any,
                                          file_paths: List[str],
                                          focus: str,
                                          context: Optional[str]) -> List[str]:
        """
        Use Gemini AI to analyze the initial code analysis and recommend appropriate tools.
        
        Args:
            initial_analysis: Output from analyze_code tool
            file_paths: Files being analyzed
            focus: Review focus area
            context: Additional context
            
        Returns:
            List of recommended tool names
        """
        try:
            # Get list of available tools for the prompt
            available_tools_info = {
                'test_coverage_analyzer': 'Analyzes test coverage, identifies untested functions',
                'dependency_mapper': 'Maps dependencies, identifies circular dependencies and coupling',
                'interface_inconsistency_detector': 'Finds naming inconsistencies and interface issues',
                'config_validator': 'Validates configuration files for security and completeness',
                'performance_profiler': 'Analyzes performance bottlenecks and optimization opportunities',
                'check_quality': 'Comprehensive quality check including security and performance',
                'analyze_docs': 'Analyzes documentation completeness and accuracy',
                'analyze_logs': 'Analyzes log files for errors and patterns',
                'analyze_database': 'Analyzes database schemas and relationships',
                'api_contract_checker': 'Validates API specifications and breaking changes',
                'search_code': 'Semantic code search for patterns and implementations'
            }
            
            # Create prompt for Gemini
            prompt = f"""Based on the following code analysis, recommend which additional analysis tools should be run.

## Initial Code Analysis:
{str(initial_analysis)[:3000]}  # Limit to avoid token issues

## Review Focus:
{focus}

## Available Tools:
{chr(10).join([f'- {name}: {desc}' for name, desc in available_tools_info.items()])}

## Instructions:
Analyze the code structure and findings from the initial analysis.
Recommend 3-7 of the most relevant tools that would provide valuable insights.
Consider the review focus area: {focus}

Return ONLY a JSON array of tool names, for example:
["test_coverage_analyzer", "dependency_mapper", "config_validator"]

Do not include explanations, just the JSON array.
"""
            
            # Call Gemini to get recommendations
            response, model_used, attempts = await self.result_synthesizer.gemini_client.generate_content(
                prompt,
                model_name='flash'  # Use flash for quick decisions
            )
            
            # Parse the response
            import json
            import re
            
            # Extract JSON array from response
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                recommended_tools = json.loads(json_match.group())
                
                # Filter to only include tools that actually exist
                valid_tools = [tool for tool in recommended_tools 
                             if tool in self.available_tools and tool != 'analyze_code']
                
                logger.info(f"AI recommended {len(valid_tools)} tools: {valid_tools}")
                return valid_tools
            else:
                logger.warning("Could not parse AI tool recommendations, falling back to standard selection")
                return []
                
        except Exception as e:
            logger.error(f"Error getting AI tool recommendations: {e}")
            return []
    
    async def _get_ai_follow_up_recommendations(self,
                                               current_results: Dict[str, Any],
                                               file_paths: List[str],
                                               focus: str,
                                               context: Optional[str]) -> List[str]:
        """
        Use Gemini AI to analyze current results and determine if follow-up tools are needed.
        
        Args:
            current_results: Results from tools already executed
            file_paths: Files being analyzed
            focus: Review focus area
            context: Additional context
            
        Returns:
            List of follow-up tool names to execute
        """
        try:
            # Prepare summary of current findings
            findings_summary = []
            tools_already_run = list(current_results.keys())
            
            for tool_name, result in current_results.items():
                if result.is_success and result.output:
                    # Truncate output to avoid token issues
                    output_preview = str(result.output)[:500]
                    findings_summary.append(f"**{tool_name}**: {output_preview}")
            
            # Get tools not yet run
            all_available = set(self.available_tools.keys())
            not_yet_run = all_available - set(tools_already_run)
            
            if not not_yet_run:
                # All tools have been run
                return []
            
            # Create prompt for follow-up decision
            prompt = f"""Based on the analysis results so far, determine if any follow-up tools should be run.

## Current Findings:
{chr(10).join(findings_summary[:10])}  # Limit to 10 tools

## Tools Already Run:
{', '.join(tools_already_run)}

## Tools NOT Yet Run:
{', '.join(not_yet_run)}

## Review Focus:
{focus}

## Instructions:
Analyze the current findings and determine if any of the tools not yet run would provide
valuable additional insights or help investigate issues found.

Consider:
1. Were security issues found that need deeper investigation?
2. Were performance problems identified that need profiling?
3. Were architectural issues found that need dependency analysis?
4. Are there test coverage gaps that need investigation?

Return ONLY a JSON array of additional tool names to run (can be empty), for example:
["performance_profiler", "security_scanner"]

If no follow-up is needed, return: []
"""
            
            # Call Gemini for follow-up recommendations
            response, model_used, attempts = await self.result_synthesizer.gemini_client.generate_content(
                prompt,
                model_name='flash'
            )
            
            # Parse the response
            import json
            import re
            
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                follow_up_tools = json.loads(json_match.group())
                
                # Filter to only include valid tools not yet run
                valid_follow_ups = [tool for tool in follow_up_tools 
                                   if tool in not_yet_run]
                
                if valid_follow_ups:
                    logger.info(f"AI recommended {len(valid_follow_ups)} follow-up tools: {valid_follow_ups}")
                else:
                    logger.info("AI determined no follow-up tools needed")
                    
                return valid_follow_ups
            else:
                logger.warning("Could not parse AI follow-up recommendations")
                return []
                
        except Exception as e:
            logger.error(f"Error getting AI follow-up recommendations: {e}")
            return []
    
    def _expand_directory(self, directory: str, max_depth: int = None) -> List[str]:
        """
        Safely expand directory to file list with security checks.
        
        Args:
            directory: Directory path to expand
            max_depth: Maximum recursion depth (defaults to class constant)
            
        Returns:
            List of file paths within the directory
        """
        if max_depth is None:
            max_depth = self.MAX_EXPAND_DEPTH
            
        try:
            # Security: Resolve to absolute path and check it's within project
            dir_path = Path(directory).resolve()
            project_root = Path.cwd()
            
            # Security check: Ensure directory is within project root
            try:
                dir_path.relative_to(project_root)
            except ValueError:
                logger.warning(f"Directory {directory} is outside project root - skipping for security")
                return []
            
            # Check if directory exists
            if not dir_path.exists():
                logger.warning(f"Directory {directory} does not exist")
                return []
            
            if not dir_path.is_dir():
                logger.warning(f"Path {directory} is not a directory")
                return []
            
            # Collect files with depth limit
            files = []
            for root, dirs, filenames in os.walk(dir_path):
                # Calculate depth relative to starting directory
                depth = len(Path(root).relative_to(dir_path).parts)
                
                if depth > max_depth:
                    dirs.clear()  # Stop traversing deeper
                    continue
                
                # Filter out common non-source directories
                dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS]
                
                # Add files (skip hidden files and common non-source files)
                for filename in filenames:
                    if filename.startswith('.'):
                        continue  # Skip hidden files
                    
                    # Skip common non-source files
                    if filename.endswith(self.IGNORED_FILE_EXTENSIONS):
                        continue
                        
                    file_path = str(Path(root) / filename)
                    files.append(file_path)
                    
                    # Limit total files to prevent memory issues
                    if len(files) >= self.MAX_EXPAND_FILES:
                        logger.warning(f"Directory {directory} contains more than {self.MAX_EXPAND_FILES} files, truncating")
                        return files
            
            logger.info(f"Expanded directory {directory} to {len(files)} files (depth limit: {max_depth})")
            return files
            
        except Exception as e:
            logger.error(f"Error expanding directory {directory}: {e}")
            return []