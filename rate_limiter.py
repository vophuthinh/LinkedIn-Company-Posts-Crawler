# -*- coding: utf-8 -*-
"""
Rate limiter for LinkedIn scraping operations
Prevents hitting LinkedIn's rate limits by controlling request frequency
"""

import logging
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter using token bucket algorithm
    Limits number of requests per time window
    """
    
    def __init__(
        self,
        max_requests: int = 10,
        time_window: int = 60,
        min_delay: float = 1.0
    ):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum number of requests allowed in time window
            time_window: Time window in seconds
            min_delay: Minimum delay between requests in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.min_delay = min_delay
        self.request_times = deque()
        self.last_request_time = None
    
    def wait_if_needed(self) -> float:
        """
        Wait if necessary to respect rate limits
        
        Returns:
            Time waited in seconds
        """
        now = datetime.now()
        wait_time = 0.0
        
        # Remove old requests outside time window
        cutoff_time = now - timedelta(seconds=self.time_window)
        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()
        
        # Check if we've exceeded rate limit
        if len(self.request_times) >= self.max_requests:
            # Calculate how long to wait
            oldest_request = self.request_times[0]
            wait_until = oldest_request + timedelta(seconds=self.time_window)
            wait_time = (wait_until - now).total_seconds()
            
            if wait_time > 0:
                logger.info(
                    f"Rate limit reached ({len(self.request_times)}/{self.max_requests} requests). "
                    f"Waiting {wait_time:.1f}s..."
                )
                time.sleep(wait_time)
                # Clean up again after waiting
                now = datetime.now()
                cutoff_time = now - timedelta(seconds=self.time_window)
                while self.request_times and self.request_times[0] < cutoff_time:
                    self.request_times.popleft()
        
        # Enforce minimum delay between requests
        if self.last_request_time:
            time_since_last = (now - self.last_request_time).total_seconds()
            if time_since_last < self.min_delay:
                additional_wait = self.min_delay - time_since_last
                if additional_wait > 0:
                    logger.debug(f"Enforcing min delay: waiting {additional_wait:.2f}s")
                    time.sleep(additional_wait)
                    wait_time += additional_wait
        
        # Record this request
        self.request_times.append(datetime.now())
        self.last_request_time = datetime.now()
        
        return wait_time
    
    def reset(self):
        """Reset rate limiter state"""
        self.request_times.clear()
        self.last_request_time = None
    
    def get_stats(self) -> dict:
        """
        Get current rate limiter statistics
        
        Returns:
            Dictionary with stats
        """
        now = datetime.now()
        cutoff_time = now - timedelta(seconds=self.time_window)
        
        # Clean up old requests
        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()
        
        return {
            'current_requests': len(self.request_times),
            'max_requests': self.max_requests,
            'time_window': self.time_window,
            'utilization': len(self.request_times) / self.max_requests * 100
        }


class AdaptiveRateLimiter(RateLimiter):
    """
    Adaptive rate limiter that adjusts based on errors
    Reduces rate when encountering rate limit errors
    """
    
    def __init__(
        self,
        max_requests: int = 10,
        time_window: int = 60,
        min_delay: float = 1.0,
        backoff_factor: float = 1.5,
        min_requests: int = 2
    ):
        """
        Initialize adaptive rate limiter
        
        Args:
            max_requests: Initial maximum requests
            time_window: Time window in seconds
            min_delay: Minimum delay between requests
            backoff_factor: Factor to multiply delay when rate limited
            min_requests: Minimum requests to allow (won't go below this)
        """
        super().__init__(max_requests, time_window, min_delay)
        self.original_max_requests = max_requests
        self.backoff_factor = backoff_factor
        self.min_requests = min_requests
        self.consecutive_errors = 0
    
    def on_rate_limit_error(self):
        """Called when rate limit error is detected"""
        self.consecutive_errors += 1
        
        # Reduce max requests
        new_max = max(
            int(self.max_requests / self.backoff_factor),
            self.min_requests
        )
        
        if new_max < self.max_requests:
            logger.warning(
                f"Rate limit error detected. Reducing max requests from {self.max_requests} to {new_max}"
            )
            self.max_requests = new_max
            # Increase min delay
            self.min_delay *= self.backoff_factor
    
    def on_success(self):
        """Called when request succeeds"""
        if self.consecutive_errors > 0:
            self.consecutive_errors = 0
            
            # Gradually increase back to original if we've been successful
            if self.max_requests < self.original_max_requests:
                new_max = min(
                    int(self.max_requests * 1.1),
                    self.original_max_requests
                )
                if new_max > self.max_requests:
                    logger.info(f"Increasing max requests to {new_max} after success")
                    self.max_requests = new_max
                    # Reduce min delay
                    self.min_delay = max(
                        self.min_delay / 1.1,
                        1.0
                    )


# Global rate limiter instance (can be shared across requests)
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(
    max_requests: int = 10,
    time_window: int = 60,
    min_delay: float = 1.0,
    adaptive: bool = False
) -> RateLimiter:
    """
    Get or create global rate limiter instance
    
    Args:
        max_requests: Maximum requests per time window
        time_window: Time window in seconds
        min_delay: Minimum delay between requests
        adaptive: Use adaptive rate limiter
    
    Returns:
        RateLimiter instance
    """
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        if adaptive:
            _global_rate_limiter = AdaptiveRateLimiter(
                max_requests=max_requests,
                time_window=time_window,
                min_delay=min_delay
            )
        else:
            _global_rate_limiter = RateLimiter(
                max_requests=max_requests,
                time_window=time_window,
                min_delay=min_delay
            )
    
    return _global_rate_limiter


def reset_rate_limiter():
    """Reset global rate limiter"""
    global _global_rate_limiter
    if _global_rate_limiter:
        _global_rate_limiter.reset()

