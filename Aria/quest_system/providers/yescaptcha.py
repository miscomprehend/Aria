"""YesCaptcha solver for hCaptcha and image captchas."""

import asyncio
import json
from typing import Dict, Any, Optional
import aiohttp


class YesCaptchaSolver:
    """YesCaptcha API client for solving captchas."""

    BASE_URL = 'https://api.yescaptcha.com'

    def __init__(self, api_key: str):
        """Initialize YesCaptcha solver.
        
        Args:
            api_key: YesCaptcha API key
        """
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close the session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def create_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a captcha solving task.
        
        Args:
            task: Task configuration
            
        Returns:
            Task response
            
        Raises:
            ValueError: If task creation fails
        """
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
        
        if data.get('errorId') == 1:
            raise ValueError(f"Error creating task: {json.dumps(data, indent=2)}")
        
        return data

    async def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """Poll for task result.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task result
            
        Raises:
            ValueError: If polling fails
        """
        session = await self._get_session()
        
        max_wait = 120  # 2 minutes max wait
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
            except Exception as e:
                await asyncio.sleep(3)
                elapsed += 3
                continue
            
            if data.get('errorId') == 1:
                raise ValueError(f"Error getting task result: {json.dumps(data, indent=2)}")
            
            if data.get('status') == 'ready':
                return data
            
            # Wait before polling again
            await asyncio.sleep(3)
            elapsed += 3
        
        raise ValueError(f"Timeout while waiting for task {task_id}")

    async def hcaptcha(
        self,
        sitekey: str,
        website_url: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Solve hCaptcha.
        
        Args:
            sitekey: hCaptcha site key
            website_url: Website URL
            options: Additional options (rqdata, isInvisible, userAgent)
            
        Returns:
            Solution with gRecaptchaResponse
        """
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

    async def image_captcha(self, image_base64: str) -> Dict[str, Any]:
        """Solve image captcha.
        
        Args:
            image_base64: Base64 encoded image
            
        Returns:
            Solution with text
        """
        task = {
            'type': 'ImageToTextTaskM1',
            'body': image_base64,
        }
        
        create_result = await self.create_task(task)
        return create_result.get('solution', {})
