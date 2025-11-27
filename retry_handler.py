# -*- coding: utf-8 -*-
"""
Retry mechanism for LinkedIn scraping operations
Handles retries with exponential backoff for network errors
"""

import logging
import time
from functools import wraps
from typing import Callable, TypeVar, Any
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        retryable_exceptions: tuple = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions or (
            TimeoutException,
            WebDriverException,
            ConnectionError,
            OSError
        )


def retry_on_failure(
    config: RetryConfig = None,
    on_retry: Callable[[int, Exception], None] = None
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff
    
    Args:
        config: RetryConfig instance (uses default if None)
        on_retry: Optional callback function(attempt_number, exception) called on each retry
    
    Example:
        @retry_on_failure(RetryConfig(max_attempts=3))
        def scrape_url(...):
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts:
                        # Calculate delay with exponential backoff
                        delay = min(
                            config.base_delay * (config.exponential_base ** (attempt - 1)),
                            config.max_delay
                        )
                        
                        logger.warning(
                            f"Attempt {attempt}/{config.max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        
                        if on_retry:
                            try:
                                on_retry(attempt, e)
                            except Exception:
                                pass
                        
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {func.__name__}: {e}"
                        )
                except Exception as e:
                    # Non-retryable exception, re-raise immediately
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise
            
            # All retries exhausted
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Function {func.__name__} failed after {config.max_attempts} attempts")
        
        return wrapper
    return decorator


def retry_scrape_operation(
    max_attempts: int = 3,
    base_delay: float = 4.0,
    max_delay: float = 30.0
) -> Callable:
    """
    Convenience decorator for scraping operations with sensible defaults
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        max_delay: Maximum delay in seconds
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        retryable_exceptions=(
            TimeoutException,
            WebDriverException,
            ConnectionError,
            OSError
        )
    )
    return retry_on_failure(config)


# Example usage:
if __name__ == "__main__":
    @retry_scrape_operation(max_attempts=3)
    def test_function():
        import random
        if random.random() < 0.7:
            raise TimeoutException("Simulated timeout")
        return "Success"
    
    try:
        result = test_function()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Failed: {e}")

