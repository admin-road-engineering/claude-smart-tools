"""
Gemini AI client with rate limiting and CPU throttling
"""
import asyncio
import json
import logging
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import google.generativeai as genai

# Simplified imports for smart tools system
from ..config import (
    API_KEYS, 
    GEMINI_MODELS, 
    GEMINI_REQUEST_TIMEOUT, 
    GEMINI_CONNECT_TIMEOUT,
    TIMEOUT_RETRY_COUNT,
    RATE_LIMIT_FILE,
    config  # Add config instance for new rate limiting settings
)
from ..services.cpu_throttler import CPUThrottler

# Simple exception classes for smart tools
class GeminiApiError(Exception):
    """Gemini API error"""
    pass

class RateLimitError(GeminiApiError):
    """Rate limit exceeded error"""
    pass

class ConfigurationError(Exception):
    """Configuration error"""
    pass

# Simplified CPU throttling for smart tools
class SimpleCPUThrottler:
    """Simplified CPU throttling for smart tools"""
    def __init__(self, config):
        self.config = config
    
    async def yield_if_needed(self):
        """Simple CPU yielding"""
        await asyncio.sleep(0.001)  # Small yield

logger = logging.getLogger(__name__)

class GeminiClient:
    """Gemini AI client with rate limiting, key rotation, and CPU throttling"""
    
    def __init__(self, smart_config=None):
        self.keys = API_KEYS
        if not self.keys:
            raise ConfigurationError("At least one API key (GOOGLE_API_KEY or GOOGLE_API_KEY2) is required")
        
        # Log API key configuration
        if len(self.keys) == 1:
            logger.info("Single API key configuration - rate limit recovery disabled")
        else:
            logger.info(f"Dual API key configuration - automatic rate limit recovery enabled")
        
        self.current_key_index = 0
        genai.configure(api_key=self.keys[self.current_key_index])
        
        # Timeout configuration
        self.base_request_timeout = GEMINI_REQUEST_TIMEOUT
        self.connect_timeout = GEMINI_CONNECT_TIMEOUT
        self.timeout_retry_count = TIMEOUT_RETRY_COUNT
        
        # CPU throttling for API operations - use singleton pattern
        self.config = smart_config or config
        self.cpu_throttler = CPUThrottler.get_instance(self.config)
        
        # SECURITY: Use granular per-model locks for better concurrency
        # This allows rate limit updates for different models to proceed in parallel
        self._rate_limit_locks = defaultdict(asyncio.Lock)
        
        logger.info(f"Timeout configuration: base_request={self.base_request_timeout}s, "
                   f"connect={self.connect_timeout}s, retries={self.timeout_retry_count}")
        
        # Initialize models
        self.models = {
            name: genai.GenerativeModel(model_id) 
            for name, model_id in GEMINI_MODELS.items()
        }
        
        # Rate limiting tracking
        self.rate_limit_file = RATE_LIMIT_FILE
        self.rate_limits = self._load_rate_limits()
        
        # Clear any expired or corrupted rate limit blocks on startup
        cleared_models = self.clear_rate_limit_blocks()
        if cleared_models:
            logger.info(f"Startup: Cleared stale blocks for {len(cleared_models)} models")
        
        logger.info("Gemini client initialized")
    
    def _load_rate_limits(self) -> Dict[str, Dict]:
        """Load rate limit tracking from file"""
        try:
            if os.path.exists(self.rate_limit_file):
                with open(self.rate_limit_file, 'r') as f:
                    data = json.load(f)
                    # Reset daily counts if it's a new day
                    today = datetime.now().strftime('%Y-%m-%d')
                    for model in data:
                        if data[model].get('date') != today:
                            data[model] = {'date': today, 'count': 0, 'blocked_until': None}
                    return data
        except Exception as e:
            logger.warning(f"Could not load rate limits: {e}")
        
        # Default rate limits
        today = datetime.now().strftime('%Y-%m-%d')
        return {
            'pro': {'date': today, 'count': 0, 'blocked_until': None},
            'flash': {'date': today, 'count': 0, 'blocked_until': None}, 
            'flash-lite': {'date': today, 'count': 0, 'blocked_until': None}
        }
    
    def _save_rate_limits(self):
        """Save rate limit tracking to file"""
        try:
            with open(self.rate_limit_file, 'w') as f:
                json.dump(self.rate_limits, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save rate limits: {e}")
    
    def clear_rate_limit_blocks(self, force_clear: bool = False):
        """Clear expired or corrupted rate limit blocks"""
        current_time = datetime.now()
        cleared_models = []
        
        for model_name, model_data in self.rate_limits.items():
            blocked_until_str = model_data.get('blocked_until')
            if blocked_until_str:
                try:
                    blocked_until = datetime.fromisoformat(blocked_until_str)
                    if current_time >= blocked_until or force_clear:
                        model_data['blocked_until'] = None
                        cleared_models.append(model_name)
                        logger.info(f"Cleared rate limit block for {model_name}")
                except (ValueError, TypeError) as e:
                    # Corrupted timestamp - clear it
                    model_data['blocked_until'] = None
                    cleared_models.append(model_name)
                    logger.info(f"Cleared corrupted rate limit block for {model_name}: {e}")
        
        if cleared_models:
            self._save_rate_limits()
            logger.info(f"Cleared rate limit blocks for: {', '.join(cleared_models)}")
        
        return cleared_models
    
    def _is_model_available(self, model_name: str) -> bool:
        """Check if model is available (not rate limited)
        
        New strategy: Only block for short RPM limits if pre-blocking is enabled
        """
        # If pre-blocking is disabled, always return True
        if not config.enable_pre_blocking:
            return True
            
        # First clear any expired blocks
        self.clear_rate_limit_blocks()
        
        model_data = self.rate_limits.get(model_name, {})
        
        # Only check blocks if pre-blocking is enabled and it's a short block
        if model_data.get('blocked_until'):
            try:
                blocked_until = datetime.fromisoformat(model_data['blocked_until'])
                if datetime.now() < blocked_until:
                    time_remaining = (blocked_until - datetime.now()).total_seconds()
                    # Only respect blocks shorter than max_block_minutes
                    if time_remaining <= (config.max_block_minutes * 60):
                        logger.debug(f"Model {model_name} still blocked for {time_remaining:.0f}s (short block)")
                        return False
                    else:
                        # Clear long blocks - we don't use them anymore
                        model_data['blocked_until'] = None
                        self._save_rate_limits()
                        logger.info(f"Cleared long block for {model_name}")
            except (ValueError, TypeError):
                # Corrupted timestamp - clear it and allow use
                model_data['blocked_until'] = None
                self._save_rate_limits()
                logger.info(f"Cleared corrupted timestamp for {model_name}")
        
        logger.debug(f"Model {model_name} is available")
        return True
    
    def _is_rate_limit_error(self, error_message: str) -> bool:
        """Check if error message indicates rate limiting"""
        rate_limit_indicators = [
            'quota exceeded', 'rate limit', 'too many requests',
            'requests per minute', 'requests per day', 'resource exhausted',
            'quota_exceeded', 'rate_limit_exceeded', '429', 'ratelimit'
        ]
        
        error_lower = str(error_message).lower()
        return any(indicator in error_lower for indicator in rate_limit_indicators)
    
    def _extract_retry_after(self, error_response) -> Optional[int]:
        """Extract Retry-After header from API error response if available"""
        try:
            # Check if error response has headers (varies by API client)
            if hasattr(error_response, 'headers') and 'retry-after' in error_response.headers:
                return int(error_response.headers['retry-after'])
            elif hasattr(error_response, 'response') and hasattr(error_response.response, 'headers'):
                headers = error_response.response.headers
                if 'retry-after' in headers:
                    return int(headers['retry-after'])
        except (ValueError, AttributeError, TypeError):
            pass
        return None
    
    async def _progressive_backoff_retry(self, prompt: str, model_name: str, 
                                       timeout: float, error_response = None) -> Tuple[str, str, int]:
        """Implement progressive backoff retry strategy
        
        New strategy: Progressive delays + try both API keys at each backoff level!
        """
        retry_delays = config.progressive_backoff_seconds  # [10, 30, 60, 180, 300]
        
        # Check for Retry-After header first
        retry_after = None
        if config.enable_retry_after_header and error_response:
            retry_after = self._extract_retry_after(error_response)
            if retry_after:
                logger.info(f"Using Retry-After header: {retry_after} seconds")
                retry_delays = [retry_after]  # Use API-provided delay
        
        total_backoff_attempts = 0
        
        for attempt, delay_seconds in enumerate(retry_delays):
            logger.info(f"Rate limit backoff: waiting {delay_seconds}s before retry {attempt + 1}/{len(retry_delays)}")
            await asyncio.sleep(delay_seconds)
            
            # Try BOTH API keys at each backoff level
            for key_index in range(len(self.keys)):
                total_backoff_attempts += 1
                
                # Switch to the specific key for this attempt
                original_key = self.current_key_index
                self.current_key_index = key_index
                genai.configure(api_key=self.keys[self.current_key_index])
                
                try:
                    logger.info(f"Backoff attempt {total_backoff_attempts}: {model_name} with API key {self.current_key_index} after {delay_seconds}s delay")
                    
                    # CPU yield before heavy API operation
                    if self.cpu_throttler:
                        await self.cpu_throttler.yield_if_needed()
                    
                    model = self.models[model_name]
                    response = await asyncio.wait_for(
                        asyncio.to_thread(model.generate_content, prompt),
                        timeout=timeout
                    )
                    
                    if response and response.text:
                        logger.info(f"Backoff retry successful for {model_name} with key {self.current_key_index} after {delay_seconds}s delay")
                        return response.text, model_name, total_backoff_attempts + 1  # +1 for original attempt
                        
                except Exception as e:
                    if self._is_rate_limit_error(str(e)):
                        logger.debug(f"Key {self.current_key_index} still rate limited after {delay_seconds}s delay")
                        # Try next key at this backoff level
                        continue
                    else:
                        # Different error - switch back to original key and propagate
                        self.current_key_index = original_key
                        genai.configure(api_key=self.keys[self.current_key_index])
                        raise
                
                # Restore original key after trying this one
                self.current_key_index = original_key
                genai.configure(api_key=self.keys[self.current_key_index])
            
            # If we get here, both keys failed at this backoff level
            logger.debug(f"Both API keys still rate limited after {delay_seconds}s delay, trying longer delay")
        
        # All retries with both keys failed
        logger.warning(f"All progressive backoff retries failed for {model_name} (tried {total_backoff_attempts} attempts with both keys)")
        raise Exception(f"Model {model_name} still rate limited after {len(retry_delays)} backoff levels with both API keys")
    
    async def _record_rate_limit_hit(self, model_name: str, error_message: str):
        """Record rate limit hit for metrics only - no more aggressive blocking
        
        New strategy: Just log for metrics, minimal blocking for RPM only
        """
        async with self._rate_limit_locks[model_name]:
            today = datetime.now().strftime('%Y-%m-%d')
            current_time = datetime.now()
            
            if model_name not in self.rate_limits:
                self.rate_limits[model_name] = {
                    'date': today, 
                    'rpm_hits': 0, 
                    'rpd_hits': 0,
                    'last_rpm_reset': current_time.isoformat(),
                    'blocked_until': None
                }
            
            model_data = self.rate_limits[model_name]
            
            # Reset daily counters if new day
            if model_data.get('date') != today:
                model_data.update({
                    'date': today, 
                    'rpm_hits': 0, 
                    'rpd_hits': 0,
                    'last_rpm_reset': current_time.isoformat(),
                    'blocked_until': None
                })
            
            # Reset RPM counter if more than 1 minute has passed
            last_rpm_reset = datetime.fromisoformat(model_data.get('last_rpm_reset', current_time.isoformat()))
            if (current_time - last_rpm_reset).total_seconds() >= 60:
                model_data['rpm_hits'] = 0
                model_data['last_rpm_reset'] = current_time.isoformat()
            
            # Increment counters for metrics
            model_data['rpm_hits'] = model_data.get('rpm_hits', 0) + 1
            model_data['rpd_hits'] = model_data.get('rpd_hits', 0) + 1
            
            # New strategy: Only minimal blocking for RPM limits, NO daily blocking
            if config.enable_pre_blocking and ('minute' in error_message.lower() or 'rpm' in error_message.lower()):
                # Only short block for RPM limits - max 2 minutes
                block_minutes = min(config.max_block_minutes, 1.5)  # 1.5 minutes max for RPM
                blocked_until = current_time + timedelta(minutes=block_minutes)
                model_data['blocked_until'] = blocked_until.isoformat()
                logger.info(f"Short block for {model_name}: {block_minutes:.1f} min (RPM limit)")
            else:
                # No blocking for daily limits - let progressive backoff handle it
                model_data['blocked_until'] = None
                logger.info(f"Rate limit recorded for {model_name} - using progressive backoff instead of blocking")
            
            logger.info(f"Rate limit metrics - {model_name}: RPM {model_data['rpm_hits']}, RPD {model_data['rpd_hits']}")
            self._save_rate_limits()
    
    def select_available_model(self, preferred_models: List[str]) -> Optional[Tuple[str, genai.GenerativeModel]]:
        """Select first available model from preferred list"""
        for model_name in preferred_models:
            if model_name in self.models and self._is_model_available(model_name):
                logger.info(f"Selected model: {model_name}")
                return model_name, self.models[model_name]
        
        logger.warning("All preferred models rate limited, using flash-lite as last resort")
        return 'flash-lite', self.models['flash-lite']
    
    def switch_api_key(self):
        """Switch to next available API key"""
        if len(self.keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
            genai.configure(api_key=self.keys[self.current_key_index])
            logger.info(f"Switched to alternate API key index {self.current_key_index}")
        else:
            logger.warning("Only one API key available, cannot switch")
    
    async def generate_content(self, prompt: str, model_name: str = "flash", 
                             timeout: float = None) -> Tuple[str, str, int]:
        """
        Generate content using specified Gemini model with intelligent fallback
        
        New Strategy (User Preferred):
        1. Try requested model with current API key
        2. On rate limit → Try OTHER API KEY first (if available)
        3. If other key also rate limited → Progressive backoff (10, 30, 60s...)
        4. If still failing → Fallback to cheaper model
        5. Repeat until success or all options exhausted
        
        Returns:
            Tuple of (response_text, final_model_used, total_attempts)
        """
        if timeout is None:
            timeout = self.base_request_timeout
        
        # Simplified fallback strategy (cost-conscious for personal use)
        # Prevent automatic escalation to expensive Pro model
        if model_name == "pro":
            fallback_models = ["pro", "flash", "flash-lite"]        # Full fallback from the top
        elif model_name == "flash":
            fallback_models = ["flash", "flash-lite"]               # Fallback to cheaper, not more expensive
        elif model_name == "flash-lite":
            fallback_models = ["flash-lite", "flash"]                # If lite fails, try the next step up
        else:
            fallback_models = ["flash", "flash-lite"]               # Default: avoid pro unless explicitly requested
        
        total_attempts = 0
        last_error = None
        
        # Try each model in fallback order
        for current_model in fallback_models:
            if current_model not in self.models:
                continue
                
            model = self.models[current_model]
            
            # Check if model is available (not blocked)
            if not self._is_model_available(current_model):
                logger.info(f"Model {current_model} is rate limited, skipping to next model")
                continue
            
            try:
                total_attempts += 1
                logger.info(f"Attempt {total_attempts}: Trying {current_model} with API key {self.current_key_index}")
                
                # CPU yield before heavy API operation
                if self.cpu_throttler:
                    await self.cpu_throttler.yield_if_needed()
                
                # Make CPU-safe API call with monitoring
                response = await self._cpu_safe_api_call(model, prompt, timeout, current_model)
                
                # Success!
                if current_model != model_name:
                    logger.info(f"Successfully fell back from {model_name} to {current_model}")
                return response.text, current_model, total_attempts
                
            except asyncio.TimeoutError:
                logger.warning(f"Timeout for {current_model}")
                last_error = f"Timeout after {timeout}s"
                continue
                
            except Exception as e:
                if self._is_rate_limit_error(str(e)):
                    logger.warning(f"Rate limit hit for {current_model}")
                    await self._record_rate_limit_hit(current_model, str(e))
                    
                    # User's preferred strategy: Try other API key first
                    if config.retry_other_key_first and len(self.keys) > 1:
                        logger.info("Trying other API key first...")
                        original_key = self.current_key_index
                        self.switch_api_key()
                        
                        try:
                            total_attempts += 1
                            logger.info(f"Attempt {total_attempts}: {current_model} with alternate API key {self.current_key_index}")
                            
                            # Use CPU-safe API call for alternate key attempts too
                            response = await self._cpu_safe_api_call(model, prompt, timeout, current_model)
                            
                            # Success with other key!
                            logger.info(f"Success with alternate API key for {current_model}")
                            return response.text, current_model, total_attempts
                            
                        except Exception as e2:
                            if self._is_rate_limit_error(str(e2)):
                                logger.info("Other API key also rate limited - using progressive backoff")
                                # Switch back to original key for consistency
                                self.current_key_index = original_key
                                genai.configure(api_key=self.keys[self.current_key_index])
                            else:
                                # Different error with other key
                                logger.error(f"API error with alternate key: {e2}")
                                last_error = str(e2)
                                continue
                    
                    # Progressive backoff strategy (user preferred: 10, 30, 60s...)
                    try:
                        logger.info(f"Applying progressive backoff for {current_model}")
                        response_text, used_model, backoff_attempts = await self._progressive_backoff_retry(
                            prompt, current_model, timeout, e
                        )
                        # Success after backoff!
                        total_attempts += backoff_attempts
                        return response_text, used_model, total_attempts
                        
                    except Exception as backoff_error:
                        logger.info(f"Progressive backoff failed for {current_model}: {backoff_error}")
                        last_error = str(backoff_error)
                        # Continue to next model
                        continue
                        
                else:
                    logger.error(f"Non-rate-limit API error: {e}")
                    last_error = str(e)
                    await asyncio.sleep(0.5)  # Brief delay for other errors
                    continue
        
        # All models and keys exhausted
        error_msg = f"All models exhausted after {total_attempts} attempts. Last error: {last_error}"
        logger.error(error_msg)
        return (f"Error: {error_msg}", model_name, total_attempts)
    
    async def _cpu_safe_api_call(self, model, prompt: str, timeout: float, model_name: str):
        """
        Make API call with periodic CPU yielding during the wait.
        Implements Gemini's recommended pattern with verification-based threading.
        """
        # Create API task - model.generate_content is synchronous (verified)
        api_task = asyncio.create_task(
            asyncio.to_thread(model.generate_content, prompt)
        )
        
        check_interval = self.config.api_call_check_interval_seconds  # 500ms from config
        elapsed = 0.0
        yield_count = 0
        
        # Monitor with configurable check intervals
        while not api_task.done():
            try:
                # Try to get result with timeout
                result = await asyncio.wait_for(
                    asyncio.shield(api_task),
                    timeout=check_interval
                )
                # Task completed successfully
                logger.debug(f"API call to {model_name} completed after {elapsed:.1f}s, {yield_count} CPU yields")
                return result
                
            except asyncio.TimeoutError:
                # Task not done yet, check if we should continue
                elapsed += check_interval
                if elapsed > timeout:
                    api_task.cancel()
                    raise asyncio.TimeoutError(f"API call to {model_name} timed out after {timeout}s")
                
                # Yield CPU control and continue monitoring
                if self.cpu_throttler:
                    await self.cpu_throttler.yield_if_needed()
                    yield_count += 1
                    
                    # Log CPU throttling status
                    stats = self.cpu_throttler.get_throttling_stats()
                    if stats['throttle_active']:
                        logger.debug(f"CPU throttling active during {model_name} API wait: "
                                   f"CPU={stats['last_cpu_usage']:.1f}%, yields={yield_count}")
                else:
                    # Fallback minimal yield if no throttler
                    await asyncio.sleep(0.01)
        
        # Task completed while we were processing
        return await api_task
    
    async def generate_summary(self, prompt: str, timeout: float = None) -> str:
        """Generate summary using flash-lite model (optimized for cost)"""
        try:
            genai.configure(api_key=self.keys[self.current_key_index])
            flash_lite_model = self.models["flash-lite"]
            
            if timeout is None:
                timeout = self.base_request_timeout
            
            # CPU yield before API operation
            if self.cpu_throttler:
                await self.cpu_throttler.yield_if_needed()
            
            # Use CPU-safe API call for summary generation
            response = await self._cpu_safe_api_call(flash_lite_model, prompt, timeout, "flash-lite")
            
            return response.text
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return f"Summary generation failed: {str(e)}"