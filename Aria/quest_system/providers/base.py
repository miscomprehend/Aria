"""Shared retry logic for captcha providers.

Both the NoCaptchaAI and YesCaptcha clients need the same behavior: when the
provider reports a transient/unsolvable error, submit a *fresh* task and rotate
the browser/header profile instead of failing the whole request. This module
holds that shared logic so the two provider files cannot drift apart.
"""

import asyncio
from typing import Callable, Dict, Any, Optional


# Provider error codes that are worth retrying with a fresh task + rotated headers.
RETRYABLE_ERROR_CODES = {
    "ERROR_CAPTCHA_UNSOLVABLE",
    "ERROR_NO_SLOT_AVAILABLE",
    "ERROR_WORKER_TIMEOUT",
    "ERROR_INTERNAL",
    "ERROR_TASK_TIMEOUT",
    "ERROR_PROXY_CONNECT_REFUSED",
    "ERROR_PROXY_CONNECT_TIMEOUT",
}


def is_retryable_error(exc: Exception) -> bool:
    """True when the provider error is worth retrying with a fresh task."""
    message = str(exc)
    return any(code in message for code in RETRYABLE_ERROR_CODES)


async def invoke_rotate(rotate: Optional[Callable[[], Any]]) -> None:
    """Invoke the caller's rotation callback (sync or async), ignoring errors."""
    if rotate is None:
        return
    try:
        result = rotate()
        if asyncio.iscoroutine(result):
            await result
    except Exception:
        pass


class RetryMixin:
    """Retry-with-rotation helper shared by captcha providers.

    Subclasses must define ``create_task`` and ``get_task_result`` and set
    ``max_attempts`` (and optionally ``provider_name``).
    """

    max_attempts: int
    provider_name: str = "captcha provider"

    async def _solve_with_retries(
        self,
        build_task: Callable[[], Dict[str, Any]],
        rotate: Optional[Callable[[], Any]] = None,
    ) -> Dict[str, Any]:
        """Submit a task and retry with a fresh task + rotated headers on failure.

        Args:
            build_task: Callable returning a fresh task payload each attempt.
            rotate: Optional callable invoked before each retry so the caller can
                rotate the browser/header profile (keeps fingerprints in sync).

        Returns:
            The provider solution dict.

        Raises:
            ValueError: If every attempt fails.
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_attempts + 1):
            if attempt > 1:
                # Rotate headers + TLS before submitting a brand new task.
                await invoke_rotate(rotate)

            try:
                create_result = await self.create_task(build_task())
                task_id = create_result.get('taskId')
                if not task_id:
                    raise ValueError("No task ID in create response")

                result = await self.get_task_result(task_id)
                solution = result.get('solution', {})
                if isinstance(solution, dict) and solution:
                    return solution
                raise ValueError("Provider returned an empty solution")
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    # Back off briefly, then rotate headers and try a fresh task.
                    await asyncio.sleep(2 if is_retryable_error(exc) else 1)
                    continue
                break

        raise ValueError(
            f"{self.provider_name} failed after {self.max_attempts} attempt(s): {last_error}"
        )
