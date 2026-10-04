import os
import time
from typing import Any, Dict, Optional

import requests

API_URL = "https://api.nocaptchaai.com"


class NoCaptchaError(Exception):
    pass


class NoCaptchaClient:
    """Minimal NoCaptchaAI client for sites you own or are authorized to test."""

    def __init__(self, client_key: Optional[str] = None, timeout: float = 30):
        self.client_key = client_key or os.environ.get("NOCAPTCHAAI_API_KEY", "")
        if not self.client_key:
            raise NoCaptchaError("NOCAPTCHAAI_API_KEY is not set.")
        self.timeout = timeout

    def _post(self, path: str, **body: Any) -> Dict[str, Any]:
        res = requests.post(
            f"{API_URL}{path}",
            json={"clientKey": self.client_key, **body},
            timeout=self.timeout,
        )
        res.raise_for_status()
        return res.json()

    def solve_turnstile(self, website_url: str, website_key: str,
                        poll_interval: float = 3, max_wait: float = 120) -> str:
        created = self._post("/createTask", task={
            "type": "AntiTurnstileTask",
            "websiteURL": website_url,
            "websiteKey": website_key,
        })
        task_id = created.get("taskId")
        if not task_id:
            raise NoCaptchaError(f"createTask failed: {created}")

        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            result = self._post("/getTaskResult", taskId=task_id)
            if result.get("status") == "ready":
                return result["solution"]["token"]
            if result.get("errorId"):
                raise NoCaptchaError(f"getTaskResult failed: {result}")
            time.sleep(poll_interval)
        raise NoCaptchaError("Timed out waiting for captcha solution.")
