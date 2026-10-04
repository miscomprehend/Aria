"""NoCaptchaAI solver for hCaptcha."""

import asyncio
import json
from typing import Dict, Any, Optional
import aiohttp


class NoCaptchaSolver:
    """NoCaptchaAI API client for solving captchas."""

    BASE_URL = 'https://api.nocaptchaai.com'

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def create_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        session = await self._get_session()
        payload = {
            'clientKey': self.api_key,
            'task': task,
        }
        try:
            async with session.post(
                f'{self.BASE_URL}/createTask',
                json=payload,
                headers={'Content-Type': 'application/json'},
            ) as resp:
                data = await resp.json()
        except Exception as e:
            raise ValueError(f"Failed to create task: {e}")

        if data.get('errorId'):
            raise ValueError(f"Error creating task: {json.dumps(data, indent=2)}")
        return data

    async def get_task_result(self, task_id: str) -> Dict[str, Any]:
        session = await self._get_session()
        max_wait = 120
        elapsed = 0

        while elapsed < max_wait:
            payload = {
                'clientKey': self.api_key,
                'taskId': task_id,
            }
            try:
                async with session.post(
                    f'{self.BASE_URL}/getTaskResult',
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                ) as resp:
                    data = await resp.json()
            except Exception:
                await asyncio.sleep(3)
                elapsed += 3
                continue

            if data.get('errorId'):
                raise ValueError(f"Error getting task result: {json.dumps(data, indent=2)}")

            if data.get('status') == 'ready':
                return data

            await asyncio.sleep(3)
            elapsed += 3

        raise ValueError(f"Timeout while waiting for task {task_id}")

    async def hcaptcha(
        self,
        sitekey: str,
        website_url: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        options = options or {}
        task = {
            'type': 'HCaptchaTaskProxyless',
            'websiteURL': website_url,
            'websiteKey': sitekey,
        }

        if options.get('userAgent'):
            task['userAgent'] = options['userAgent']
        if options.get('isInvisible') is not None:
            task['isInvisible'] = options['isInvisible']
        if options.get('rqdata'):
            task['rqdata'] = options['rqdata']

        create_result = await self.create_task(task)
        task_id = create_result.get('taskId')
        if not task_id:
            raise ValueError("No task ID in create response")

        result = await self.get_task_result(task_id)
        return result.get('solution', {})
