"""D3: Declarative retry by error class.

Classifies errors and applies different retry strategies:
- Rate limit (429) → exponential backoff
- Context too long → compress and retry
- Non-retryable → fail immediately
"""

import logging
import time
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger("2hao.retry")


class ErrorClass(Enum):
    RETRYABLE_RATE_LIMIT = "rate_limit"        # 429, 503
    RETRYABLE_TIMEOUT = "timeout"              # timeout, connection error
    RETRYABLE_CONTEXT = "context_too_long"     # context window exceeded
    RETRYABLE_TRANSIENT = "transient"          # temporary failures
    NON_RETRYABLE = "non_retryable"            # auth, permission, data corruption
    UNKNOWN = "unknown"


class RetryPolicy:
    """Declarative retry policy by error class."""

    def __init__(self):
        self.policies = {
            ErrorClass.RETRYABLE_RATE_LIMIT: {
                "max_retries": 3,
                "base_delay": 5.0,
                "max_delay": 60.0,
                "exponential_base": 2.0,
            },
            ErrorClass.RETRYABLE_TIMEOUT: {
                "max_retries": 2,
                "base_delay": 10.0,
                "max_delay": 30.0,
                "exponential_base": 2.0,
            },
            ErrorClass.RETRYABLE_CONTEXT: {
                "max_retries": 1,
                "base_delay": 0.0,
                "max_delay": 0.0,
                "exponential_base": 1.0,
            },
            ErrorClass.RETRYABLE_TRANSIENT: {
                "max_retries": 2,
                "base_delay": 2.0,
                "max_delay": 20.0,
                "exponential_base": 2.0,
            },
            ErrorClass.NON_RETRYABLE: {
                "max_retries": 0,
                "base_delay": 0.0,
                "max_delay": 0.0,
                "exponential_base": 1.0,
            },
            ErrorClass.UNKNOWN: {
                "max_retries": 1,
                "base_delay": 2.0,
                "max_delay": 10.0,
                "exponential_base": 2.0,
            },
        }

    def classify_error(self, error: Exception) -> ErrorClass:
        """Classify an error into an error class."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        # Rate limit
        if "429" in error_str or "rate" in error_str or "throttl" in error_str:
            return ErrorClass.RETRYABLE_RATE_LIMIT

        # Context too long
        if "context" in error_str and ("long" in error_str or "exceed" in error_str or "token" in error_str):
            return ErrorClass.RETRYABLE_CONTEXT
        if "context_length" in error_str or "max_tokens" in error_str:
            return ErrorClass.RETRYABLE_CONTEXT

        # Timeout
        if "timeout" in error_str or "timed out" in error_str:
            return ErrorClass.RETRYABLE_TIMEOUT
        if "connection" in error_str and ("refused" in error_str or "reset" in error_str):
            return ErrorClass.RETRYABLE_TIMEOUT

        # Non-retryable
        if "auth" in error_str or "permission" in error_str or "forbidden" in error_str:
            return ErrorClass.NON_RETRYABLE
        if "invalid" in error_str and ("key" in error_str or "token" in error_str):
            return ErrorClass.NON_RETRYABLE
        if "corrupt" in error_str or "integrity" in error_str:
            return ErrorClass.NON_RETRYABLE

        # Transient (catch-all for retryable)
        if "500" in error_str or "502" in error_str or "503" in error_str:
            return ErrorClass.RETRYABLE_TRANSIENT

        return ErrorClass.UNKNOWN

    def get_policy(self, error_class: ErrorClass) -> dict:
        return self.policies.get(error_class, self.policies[ErrorClass.UNKNOWN])


def retry_with_policy(
    func: Callable,
    *args,
    policy: RetryPolicy = None,
    on_retry: Optional[Callable] = None,
    **kwargs,
) -> Any:
    """Execute func with declarative retry by error class.

    Args:
        func: Function to execute
        policy: RetryPolicy instance (default: new RetryPolicy())
        on_retry: Callback function(error_class, attempt, delay) called before each retry
        *args, **kwargs: Arguments to pass to func

    Returns:
        Result of func

    Raises:
        Last exception if all retries exhausted
    """
    if policy is None:
        policy = RetryPolicy()

    last_error = None
    attempt = 0

    while True:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            error_class = policy.classify_error(e)
            retry_policy = policy.get_policy(error_class)
            max_retries = retry_policy["max_retries"]

            if attempt >= max_retries:
                logger.error(
                    "[RETRY] Exhausted %d retries for %s (class=%s): %s",
                    attempt, func.__name__, error_class.value, str(e)[:200]
                )
                raise

            # Calculate delay
            base_delay = retry_policy["base_delay"]
            exponential_base = retry_policy["exponential_base"]
            max_delay = retry_policy["max_delay"]
            delay = min(base_delay * (exponential_base ** attempt), max_delay)

            logger.warning(
                "[RETRY] %s attempt %d/%d failed (class=%s): %s — retrying in %.1fs",
                func.__name__, attempt + 1, max_retries, error_class.value,
                str(e)[:200], delay
            )

            if on_retry:
                on_retry(error_class, attempt, delay)

            if delay > 0:
                time.sleep(delay)

            attempt += 1
