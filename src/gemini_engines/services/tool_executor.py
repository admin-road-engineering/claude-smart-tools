"""
Enhanced tool execution service with DialogueState integration.

Provides robust execution of analysis tools with comprehensive failure recovery,
intelligent error classification, and integration with the dialogue system.
"""
import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from ..tools.interfaces import (
    IToolExecutor, IAnalysisTool, AnalysisResult, ToolStatus,
    ToolExecutorConfig
)
from ..models.dialogue_models import (
    ToolOutput, ErrorType, ToolStatus as NewToolStatus,
    ValidationResult, ValidationIssue, ValidationSeverity
)
from ..models.context_models import (
    ContextEntry, ContextType, ContextCategory, ContextPriority
)
from ..services.file_integrity_validator import FileIntegrityValidator
from ..services.context_manager import ContextManager

logger = logging.getLogger(__name__)


class ToolExecutor(IToolExecutor):
    """
    Concrete implementation of tool execution with advanced error handling.
    Supports parallel execution, retry logic, and dry-run mode for testing.
    """
    
    def __init__(self, config: ToolExecutorConfig = None, 
                 file_validator: FileIntegrityValidator = None,
                 context_manager: ContextManager = None):
        """
        Initialize ToolExecutor with configuration, file validator, and context manager.
        
        Args:
            config: Configuration for execution parameters
            file_validator: File validation service for pre-execution checks
            context_manager: Context manager for cross-tool context sharing
        """
        self.config = config or ToolExecutorConfig()
        self.file_validator = file_validator
        self.context_manager = context_manager
        
        # Create semaphore for controlling parallelism
        self.semaphore = asyncio.Semaphore(self.config.max_concurrency)
        
        # Track execution metrics
        self.metrics = {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'retry_attempts': 0,
            'dry_run_executions': 0,
            'total_execution_time': 0.0,
            'validation_blocked_executions': 0
        }
        
        logger.info(f"ToolExecutor initialized with max_concurrency={self.config.max_concurrency}, file_validator={'enabled' if file_validator else 'disabled'}")
    
    async def _validate_files(self, file_paths: List[str]) -> ValidationResult:
        """
        Validate files before tool execution using FileIntegrityValidator.
        
        Args:
            file_paths: List of file paths to validate
            
        Returns:
            ValidationResult with structured validation outcome
        """
        if not self.file_validator or not file_paths:
            # If no validator or no files, assume all files are valid
            return ValidationResult(
                valid_files=file_paths,
                total_files_requested=len(file_paths)
            )
        
        try:
            # Use FileIntegrityValidator to check files
            validation_report = await self.file_validator.create_validation_report(file_paths)
            
            # Convert FileIntegrityValidator result to our ValidationResult format
            validation_result = ValidationResult(
                valid_files=validation_report.verified_files,  # Fixed: ValidationReport has verified_files, not valid_files
                total_files_requested=len(file_paths)
            )
            
            # Convert missing files to ValidationIssues
            for missing_file in validation_report.missing_paths:  # Fixed: ValidationReport has missing_paths
                validation_result.issues.append(ValidationIssue(
                    path=missing_file,
                    severity=ValidationSeverity.ERROR,
                    message="File not found",
                    suggested_action="Check file path and ensure file exists"
                ))
            
            # Convert inaccessible files to ValidationIssues (if attribute exists)
            if hasattr(validation_report, 'inaccessible_files'):
                for inaccessible_file in validation_report.inaccessible_files:
                    validation_result.issues.append(ValidationIssue(
                        path=inaccessible_file,
                        severity=ValidationSeverity.ERROR,
                        message="File cannot be read (permission denied or not accessible)",
                        suggested_action="Check file permissions"
                    ))
            
            # Convert warnings to ValidationIssues (if any are present in the validation report)
            if hasattr(validation_report, 'warnings'):
                for warning in validation_report.warnings:
                    validation_result.issues.append(ValidationIssue(
                        path=warning.get('path', 'unknown'),
                        severity=ValidationSeverity.WARNING,
                        message=warning.get('message', 'Unknown warning'),
                        suggested_action=warning.get('suggestion')
                    ))
            
            return validation_result
            
        except Exception as e:
            logger.error(f"File validation failed with exception: {e}")
            
            # If validation fails, assume all files are problematic
            return ValidationResult(
                valid_files=[],
                total_files_requested=len(file_paths),
                issues=[
                    ValidationIssue(
                        path=path,
                        severity=ValidationSeverity.ERROR,
                        message=f"Validation failed: {str(e)}",
                        suggested_action="Check file system accessibility and try again"
                    ) for path in file_paths
                ]
            )
    
    def _classify_error_type(self, error_message: str, exception: Exception = None) -> ErrorType:
        """
        Classify error type for intelligent retry logic.
        
        Args:
            error_message: Error message from tool execution
            exception: Original exception if available
            
        Returns:
            ErrorType classification for retry decisions
        """
        error_msg_lower = error_message.lower()
        
        # Transient errors that can be retried
        transient_indicators = [
            'timeout', 'connection', 'rate limit', 'network', 'temporary',
            'service unavailable', '503', '502', '504', 'retry', 'busy',
            'overloaded', 'throttle', 'quota'
        ]
        
        # User input errors that shouldn't be retried
        user_input_indicators = [
            'file not found', 'path does not exist', 'invalid path', 
            'permission denied', 'access denied', 'unauthorized', 'forbidden',
            'invalid argument', 'bad request', '400', '401', '403', '404',
            'syntax error', 'parse error', 'invalid format', 'malformed',
            'no such file', 'directory not found'
        ]
        
        # Check transient errors first
        if any(indicator in error_msg_lower for indicator in transient_indicators):
            return ErrorType.TRANSIENT
        
        # Check user input errors
        if any(indicator in error_msg_lower for indicator in user_input_indicators):
            return ErrorType.USER_INPUT
        
        # Check exception types for additional classification
        if exception:
            if isinstance(exception, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
                return ErrorType.TRANSIENT
            elif isinstance(exception, (FileNotFoundError, PermissionError)):
                return ErrorType.USER_INPUT
        
        # Default to internal error
        return ErrorType.INTERNAL
    
    def _convert_to_tool_output(self, result: AnalysisResult) -> ToolOutput:
        """
        Convert legacy AnalysisResult to new ToolOutput format.
        
        Args:
            result: AnalysisResult from tool execution
            
        Returns:
            ToolOutput with enhanced error classification
        """
        # Map legacy ToolStatus to new ToolStatus
        status_mapping = {
            ToolStatus.SUCCESS: NewToolStatus.SUCCESS,
            ToolStatus.FAILURE: NewToolStatus.FAILURE,
            ToolStatus.SKIPPED: NewToolStatus.CANCELLED  # Map skipped to cancelled
        }
        
        new_status = status_mapping.get(result.status, NewToolStatus.FAILURE)
        
        # Classify error type for failures
        error_type = None
        if not result.is_success:
            error_type = self._classify_error_type(result.error_message or "Unknown error")
        
        # Extract structured data from output
        summary = ""
        artifacts = []
        recommendations = []
        
        if isinstance(result.output, dict):
            summary = str(result.output.get('summary', result.output.get('analysis', '')))[:200]
            artifacts = result.output.get('artifacts', result.output.get('findings', []))
            recommendations = result.output.get('recommendations', result.output.get('suggestions', []))
        elif isinstance(result.output, str):
            summary = result.output[:200]
        
        return ToolOutput(
            tool_name=result.tool_name,
            status=new_status,
            summary=summary,
            artifacts=artifacts if isinstance(artifacts, list) else [],
            recommendations=recommendations if isinstance(recommendations, list) else [],
            execution_time_seconds=result.execution_time_seconds,
            files_analyzed=0,  # TODO: Could be extracted from context if available
            timestamp=result.timestamp or datetime.now(timezone.utc),
            error_message=result.error_message,
            error_type=error_type,
            raw_output=result.output if isinstance(result.output, dict) else None
        )
    
    async def execute_single_tool_enhanced(self,
                                          tool: IAnalysisTool,
                                          file_paths: List[str],
                                          context: Dict[str, Any]) -> ToolOutput:
        """
        Execute a single tool with enhanced ToolOutput format.
        
        Args:
            tool: Tool instance to execute
            file_paths: Files to analyze 
            context: Execution context
            
        Returns:
            ToolOutput with intelligent error classification
        """
        # Execute with legacy interface
        analysis_result = await self.execute_single_tool(tool, file_paths, context)
        
        # Convert to enhanced format
        return self._convert_to_tool_output(analysis_result)
    
    async def execute_tool_batch_enhanced(self,
                                         tools: List[IAnalysisTool],
                                         file_paths: List[str],
                                         context: Dict[str, Any]) -> Dict[str, ToolOutput]:
        """
        Execute multiple tools with enhanced ToolOutput format.
        
        Args:
            tools: List of tools to execute
            file_paths: Files to analyze
            context: Execution context
            
        Returns:
            Dictionary mapping tool names to ToolOutput results
        """
        # Execute with legacy interface
        analysis_results = await self.execute_tool_batch(tools, file_paths, context)
        
        # Convert to enhanced format
        return {
            tool_name: self._convert_to_tool_output(result)
            for tool_name, result in analysis_results.items()
        }
    
    async def retry_failed_tools_enhanced(self,
                                         failed_tools: List[IAnalysisTool],
                                         file_paths: List[str],
                                         context: Dict[str, Any]) -> Dict[str, ToolOutput]:
        """
        Retry failed tools with intelligent retry logic based on error classification.
        
        Only retries tools that failed with transient or internal errors.
        Skips tools that failed with user input errors.
        
        Args:
            failed_tools: Tools that failed in previous execution
            file_paths: Files to analyze
            context: Execution context
            
        Returns:
            Dictionary of retry results
        """
        if not failed_tools:
            return {}
        
        # Filter tools based on previous failure classification
        retryable_tools = []
        non_retryable_results = {}
        
        for tool in failed_tools:
            # Check if this tool has a previous failure classification
            previous_error_type = context.get(f'{tool.name}_error_type')
            
            if previous_error_type == ErrorType.USER_INPUT:
                # Don't retry user input errors
                logger.info(f"Skipping retry of {tool.name} due to user input error")
                non_retryable_results[tool.name] = ToolOutput(
                    tool_name=tool.name,
                    status=NewToolStatus.FAILURE,
                    summary="Skipped retry due to user input error",
                    execution_time_seconds=0.0,
                    error_message=context.get(f'{tool.name}_error_message', 'Previous user input error'),
                    error_type=ErrorType.USER_INPUT
                )
            else:
                retryable_tools.append(tool)
        
        if not retryable_tools:
            logger.info("No retryable tools found - all failed with user input errors")
            return non_retryable_results
        
        # Execute retries for transient/internal errors
        logger.info(f"Retrying {len(retryable_tools)} tools (excluding {len(non_retryable_results)} user input errors)")
        
        retry_results = await self.retry_failed_tools(retryable_tools, file_paths, context)
        enhanced_retry_results = {
            tool_name: self._convert_to_tool_output(result)
            for tool_name, result in retry_results.items()
        }
        
        # Combine retry results with non-retryable results
        enhanced_retry_results.update(non_retryable_results)
        
        return enhanced_retry_results
    
    async def execute_single_tool(self, 
                                 tool: IAnalysisTool, 
                                 file_paths: List[str],
                                 context: Dict[str, Any]) -> AnalysisResult:
        """
        Execute a single analysis tool with file validation, timeout and error handling.
        
        Args:
            tool: Tool instance to execute
            file_paths: Files to analyze
            context: Execution context
            
        Returns:
            AnalysisResult with execution outcome
        """
        start_time = time.time()
        
        async with self.semaphore:  # Control concurrency
            try:
                self.metrics['total_executions'] += 1
                
                # PHASE 1: File validation (new addition)
                if file_paths:  # Only validate if there are files to validate
                    validation_result = await self._validate_files(file_paths)
                    
                    # Check if validation blocks execution
                    if validation_result.is_blocking:
                        self.metrics['validation_blocked_executions'] += 1
                        execution_time = time.time() - start_time
                        error_message = f"File validation failed: {validation_result.get_user_friendly_message()}"
                        
                        logger.warning(f"Tool {tool.name} blocked by file validation: {len(validation_result.valid_files)}/{validation_result.total_files_requested} files valid")
                        
                        return AnalysisResult(
                            tool_name=tool.name,
                            status=ToolStatus.FAILURE,
                            error_message=error_message,
                            execution_time_seconds=execution_time,
                            output={
                                'validation_blocked': True,
                                'validation_result': validation_result.dict(),
                                'user_friendly_message': validation_result.get_user_friendly_message()
                            }
                        )
                    
                    # Use only validated files for execution
                    validated_file_paths = validation_result.valid_files
                    
                    # Log validation warnings but continue
                    if validation_result.has_warnings:
                        logger.warning(f"Tool {tool.name} proceeding with warnings: {validation_result.get_user_friendly_message()}")
                    
                    logger.info(f"File validation passed for {tool.name}: {len(validated_file_paths)}/{validation_result.total_files_requested} files valid")
                else:
                    # No files to validate
                    validated_file_paths = file_paths
                
                # PHASE 2: Tool execution with validated files
                if context.get('dry_run', False):
                    self.metrics['dry_run_executions'] += 1
                    logger.info(f"Executing tool {tool.name} in dry-run mode on {len(validated_file_paths)} validated files")
                else:
                    logger.info(f"Executing tool {tool.name} on {len(validated_file_paths)} validated files")
                
                # Execute with timeout using validated files
                try:
                    # Check if tool has execute method
                    if not hasattr(tool, 'execute'):
                        raise AttributeError(f"Tool {tool.name} doesn't implement execute method")
                    
                    result = await asyncio.wait_for(
                        tool.execute(validated_file_paths, context),
                        timeout=self.config.timeout_seconds
                    )
                except AttributeError as e:
                    # Specific handling for missing execute method
                    logger.error(f"Tool {tool.name} missing required method: {e}")
                    execution_time = time.time() - start_time
                    self.metrics['failed_executions'] += 1
                    
                    return AnalysisResult(
                        tool_name=tool.name,
                        status=ToolStatus.FAILURE,
                        error_message=f"Tool implementation error: {e}",
                        execution_time_seconds=execution_time
                    )
                
                execution_time = time.time() - start_time
                self.metrics['total_execution_time'] += execution_time
                
                # Track success/failure
                if result.is_success:
                    self.metrics['successful_executions'] += 1
                    logger.info(f"Tool {tool.name} completed successfully in {execution_time:.2f}s")
                else:
                    self.metrics['failed_executions'] += 1
                    logger.warning(f"Tool {tool.name} failed: {result.error_message}")
                    
                    # Store error details in context for enhanced methods (for non-exception failures)
                    error_type = self._classify_error_type(result.error_message or "Unknown error")
                    context[f'{tool.name}_error_type'] = error_type
                    context[f'{tool.name}_error_message'] = result.error_message
                    context[f'{tool.name}_status'] = result.status.name
                
                return result
                
            except asyncio.TimeoutError as e:
                execution_time = time.time() - start_time
                self.metrics['failed_executions'] += 1
                error_msg = f"Tool execution timed out after {self.config.timeout_seconds}s"
                
                logger.error(f"Tool {tool.name} timed out after {execution_time:.2f}s")
                
                # Store error details in context for enhanced methods
                context[f'{tool.name}_error_type'] = self._classify_error_type(error_msg, e)
                context[f'{tool.name}_error_message'] = error_msg
                context[f'{tool.name}_exception_type'] = type(e).__name__
                
                return AnalysisResult(
                    tool_name=tool.name,
                    status=ToolStatus.FAILURE,
                    error_message=error_msg,
                    execution_time_seconds=execution_time
                )
                
            except Exception as e:
                execution_time = time.time() - start_time
                self.metrics['failed_executions'] += 1
                error_msg = f"Tool execution failed: {str(e)}"
                
                logger.error(f"Tool {tool.name} failed with exception: {e}")
                
                # Store error details in context for enhanced methods
                context[f'{tool.name}_error_type'] = self._classify_error_type(error_msg, e)
                context[f'{tool.name}_error_message'] = error_msg
                context[f'{tool.name}_exception_type'] = type(e).__name__
                
                return AnalysisResult(
                    tool_name=tool.name,
                    status=ToolStatus.FAILURE,
                    error_message=error_msg,
                    execution_time_seconds=execution_time
                )
    
    async def execute_tool_batch(self, 
                                tools: List[IAnalysisTool], 
                                file_paths: List[str],
                                context: Dict[str, Any]) -> Dict[str, AnalysisResult]:
        """
        Execute multiple tools in parallel with comprehensive error handling.
        
        Args:
            tools: List of tools to execute
            file_paths: Files to analyze
            context: Execution context
            
        Returns:
            Dictionary mapping tool names to their results
        """
        if not tools:
            return {}
        
        logger.info(f"Executing batch of {len(tools)} tools on {len(file_paths)} files")
        
        # Create tasks for parallel execution
        tasks = []
        tool_names = []
        
        for tool in tools:
            task = asyncio.create_task(
                self.execute_single_tool(tool, file_paths, context),
                name=tool.name
            )
            tasks.append(task)
            tool_names.append(tool.name)
        
        # Execute all tasks and gather results
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle exceptions
            tool_results = {}
            for tool_name, result in zip(tool_names, results):
                if isinstance(result, Exception):
                    # Handle exceptions that escaped from execute_single_tool
                    logger.error(f"Unhandled exception in tool {tool_name}: {result}")
                    tool_results[tool_name] = AnalysisResult(
                        tool_name=tool_name,
                        status=ToolStatus.FAILURE,
                        error_message=f"Unhandled exception: {str(result)}",
                        execution_time_seconds=0.0
                    )
                else:
                    tool_results[tool_name] = result
            
            # Log batch execution summary
            successful_count = sum(1 for r in tool_results.values() if r.is_success)
            failed_count = sum(1 for r in tool_results.values() if r.is_failure)
            
            logger.info(f"Batch execution complete: {successful_count} successful, {failed_count} failed")
            
            return tool_results
            
        except Exception as e:
            # This should rarely happen due to return_exceptions=True
            logger.error(f"Batch execution failed with exception: {e}")
            
            # Return failure results for all tools
            return {
                tool.name: AnalysisResult(
                    tool_name=tool.name,
                    status=ToolStatus.FAILURE,
                    error_message=f"Batch execution failed: {str(e)}",
                    execution_time_seconds=0.0
                )
                for tool in tools
            }
    
    async def execute_tool_batch_with_context(self,
                                              tools: List[IAnalysisTool],
                                              file_paths: List[str],
                                              context: Dict[str, Any]) -> Dict[str, AnalysisResult]:
        """
        Execute multiple tools sequentially with context sharing.
        
        This method runs tools one by one, allowing later tools to benefit from
        context generated by earlier tools in the execution chain.
        
        Args:
            tools: List of tools to execute in order
            file_paths: Files to analyze
            context: Execution context
            
        Returns:
            Dictionary mapping tool names to their results
        """
        if not tools:
            return {}
        
        session_id = context.get('session_id', 'default')
        logger.info(f"Executing {len(tools)} tools sequentially with context sharing (session: {session_id})")
        
        tool_results = {}
        
        for i, tool in enumerate(tools):
            logger.info(f"Executing tool {i+1}/{len(tools)}: {tool.name}")
            
            try:
                # Get relevant context for this tool if context manager is available
                shared_context = []
                if self.context_manager and session_id:
                    # Register tool requirements
                    requirements = tool.get_context_requirements() if hasattr(tool, 'get_context_requirements') else None
                    if requirements:
                        self.context_manager.register_tool_requirements(requirements)
                    
                    # Get relevant context from previous tools
                    shared_context = self.context_manager.get_context_for_tool(session_id, tool.name)
                    logger.info(f"Tool {tool.name}: Using {len(shared_context)} context entries from previous tools")
                
                # Execute tool with context if supported
                if hasattr(tool, 'process_with_context') and shared_context:
                    # Tool supports context sharing - use enhanced execution
                    core_results = await tool.process_with_context(file_paths, shared_context, **context)
                    
                    # Create AnalysisResult from core results
                    result = AnalysisResult(
                        tool_name=tool.name,
                        status=ToolStatus.SUCCESS,
                        output=core_results,
                        execution_time_seconds=0.0  # Would need timing logic
                    )
                else:
                    # Standard execution
                    result = await self.execute_single_tool(tool, file_paths, context)
                
                tool_results[tool.name] = result
                
                # Extract and store context contributions if tool succeeded
                if (result.is_success and self.context_manager and session_id and
                    hasattr(tool, 'extract_context_contributions')):
                    context_contributions = tool.extract_context_contributions(result)
                    for entry in context_contributions:
                        self.context_manager.add_context(session_id, entry)
                        logger.info(f"Tool {tool.name}: Added context entry '{entry.title}' of type {entry.type}")
                
            except Exception as e:
                logger.error(f"Tool {tool.name} failed with exception: {e}", exc_info=True)
                tool_results[tool.name] = AnalysisResult(
                    tool_name=tool.name,
                    status=ToolStatus.FAILURE,
                    error_message=f"Execution failed: {str(e)}",
                    execution_time_seconds=0.0
                )
        
        # Log execution summary
        successful_count = sum(1 for r in tool_results.values() if r.is_success)
        failed_count = sum(1 for r in tool_results.values() if r.is_failure)
        
        logger.info(f"Context-aware execution complete: {successful_count} successful, {failed_count} failed")
        
        # Show context summary if available
        if self.context_manager and session_id:
            try:
                summary = self.context_manager.get_context_summary(session_id)
                logger.info(f"Session context: {summary.get('total_entries', 0)} entries, "
                           f"{summary.get('high_priority_count', 0)} high priority")
            except Exception as e:
                logger.warning(f"Could not get context summary: {e}")
        
        return tool_results
    
    async def retry_failed_tools(self, 
                                failed_tools: List[IAnalysisTool], 
                                file_paths: List[str],
                                context: Dict[str, Any]) -> Dict[str, AnalysisResult]:
        """
        Retry execution of previously failed tools with backoff strategy.
        
        Args:
            failed_tools: Tools that failed in previous execution
            file_paths: Files to analyze
            context: Execution context
            
        Returns:
            Dictionary of retry results
        """
        if not failed_tools:
            return {}
        
        logger.info(f"Retrying {len(failed_tools)} failed tools")
        
        retry_results = {}
        
        for attempt in range(1, self.config.retry_attempts + 1):
            remaining_tools = [
                tool for tool in failed_tools
                if tool.name not in retry_results or not retry_results[tool.name].is_success
            ]
            
            if not remaining_tools:
                break
            
            logger.info(f"Retry attempt {attempt}/{self.config.retry_attempts} for {len(remaining_tools)} tools")
            
            # Add exponential backoff delay
            if attempt > 1:
                delay = min(2 ** (attempt - 1), 30)  # Cap at 30 seconds
                logger.info(f"Waiting {delay}s before retry attempt {attempt}")
                await asyncio.sleep(delay)
            
            # Execute retry batch
            batch_results = await self.execute_tool_batch(remaining_tools, file_paths, context)
            
            # Update retry results
            retry_results.update(batch_results)
            self.metrics['retry_attempts'] += len(remaining_tools)
            
            # Check if any tools succeeded in this retry
            newly_successful = [
                name for name, result in batch_results.items()
                if result.is_success
            ]
            
            if newly_successful:
                logger.info(f"Retry attempt {attempt} succeeded for tools: {newly_successful}")
            
            # If all remaining tools failed, we'll try again (if attempts remain)
            remaining_failed = [
                tool for tool in remaining_tools
                if not batch_results.get(tool.name, AnalysisResult(tool_name=tool.name, status=ToolStatus.FAILURE)).is_success
            ]
            
            if not remaining_failed:
                logger.info(f"All tools succeeded after retry attempt {attempt}")
                break
            elif attempt == self.config.retry_attempts:
                logger.warning(f"Max retry attempts reached. {len(remaining_failed)} tools still failing")
        
        return retry_results
    
    def get_execution_metrics(self) -> Dict[str, Any]:
        """
        Get execution metrics for monitoring and debugging.
        
        Returns:
            Dictionary of execution statistics
        """
        total_executions = self.metrics['total_executions']
        if total_executions == 0:
            success_rate = 0.0
            avg_execution_time = 0.0
        else:
            success_rate = self.metrics['successful_executions'] / total_executions
            avg_execution_time = self.metrics['total_execution_time'] / total_executions
        
        return {
            **self.metrics,
            'success_rate': success_rate,
            'average_execution_time_seconds': avg_execution_time,
            'config': {
                'max_concurrency': self.config.max_concurrency,
                'retry_attempts': self.config.retry_attempts,
                'timeout_seconds': self.config.timeout_seconds
            }
        }
    
    def reset_metrics(self) -> None:
        """Reset execution metrics"""
        self.metrics = {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'retry_attempts': 0,
            'dry_run_executions': 0,
            'total_execution_time': 0.0,
            'validation_blocked_executions': 0
        }
        logger.info("Execution metrics reset")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the executor.
        
        Returns:
            Health status information
        """
        try:
            # Check semaphore availability
            semaphore_available = self.semaphore._value
            
            # Basic health indicators
            health_status = {
                'status': 'healthy',
                'semaphore_available_slots': semaphore_available,
                'max_concurrency': self.config.max_concurrency,
                'metrics': self.get_execution_metrics()
            }
            
            # Determine overall health
            success_rate = health_status['metrics']['success_rate']
            if success_rate < 0.5 and self.metrics['total_executions'] > 10:
                health_status['status'] = 'degraded'
                health_status['warning'] = f"Low success rate: {success_rate:.2%}"
            
            return health_status
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'metrics': self.get_execution_metrics()
            }


class DryRunToolExecutor(IToolExecutor):
    """
    Specialized executor for dry-run mode that mocks all tool executions.
    Useful for testing orchestration logic without running actual tools.
    """
    
    def __init__(self, mock_execution_time: float = 0.1):
        """
        Initialize dry-run executor.
        
        Args:
            mock_execution_time: Simulated execution time for each tool
        """
        self.mock_execution_time = mock_execution_time
        self.execution_log = []
    
    async def execute_single_tool(self, 
                                 tool: IAnalysisTool, 
                                 file_paths: List[str],
                                 context: Dict[str, Any]) -> AnalysisResult:
        """Mock execution of a single tool"""
        
        # Simulate execution time
        await asyncio.sleep(self.mock_execution_time)
        
        # Log execution
        self.execution_log.append({
            'tool_name': tool.name,
            'file_count': len(file_paths),
            'context_keys': list(context.keys()),
            'timestamp': time.time()
        })
        
        # Return mock successful result
        return AnalysisResult(
            tool_name=tool.name,
            status=ToolStatus.SUCCESS,
            output={
                'dry_run': True,
                'mock_result': f"Mock execution of {tool.name}",
                'files_processed': len(file_paths)
            },
            execution_time_seconds=self.mock_execution_time
        )
    
    async def execute_tool_batch(self, 
                                tools: List[IAnalysisTool], 
                                file_paths: List[str],
                                context: Dict[str, Any]) -> Dict[str, AnalysisResult]:
        """Mock batch execution"""
        
        # Execute all tools in "parallel" (but still mocked)
        tasks = [
            self.execute_single_tool(tool, file_paths, context)
            for tool in tools
        ]
        
        results = await asyncio.gather(*tasks)
        
        return {
            tool.name: result
            for tool, result in zip(tools, results)
        }
    
    async def retry_failed_tools(self, 
                                failed_tools: List[IAnalysisTool], 
                                file_paths: List[str],
                                context: Dict[str, Any]) -> Dict[str, AnalysisResult]:
        """Mock retry execution - always succeeds in dry-run"""
        
        return await self.execute_tool_batch(failed_tools, file_paths, context)
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Get log of all mock executions"""
        return self.execution_log.copy()
    
    def clear_log(self) -> None:
        """Clear the execution log"""
        self.execution_log.clear()