import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from reply_helpers import ASCIIMixin, _TASKS, asend, send_temp


class ReplyHelperTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.command = SimpleNamespace(delete=AsyncMock())
        self.reply = SimpleNamespace(delete=AsyncMock())
        self.ctx = SimpleNamespace(message=self.command, send=AsyncMock(return_value=self.reply))

    async def asyncTearDown(self):
        tasks = list(_TASKS)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def test_send_temp_deletes_command_and_expires_own_reply(self):
        result = await send_temp(self.ctx, "> reply", delay=1)
        self.assertIs(result, self.reply)
        self.command.delete.assert_awaited_once()
        self.ctx.send.assert_awaited_once_with("> reply")

        await asyncio.sleep(1.05)
        self.reply.delete.assert_awaited_once()

    async def test_send_failure_does_not_schedule_reply_deletion(self):
        self.ctx.send.side_effect = RuntimeError("send failed")

        result = await send_temp(self.ctx, "reply", delay=1)

        self.assertIsNone(result)
        self.assertEqual(len(_TASKS), 0)
        self.reply.delete.assert_not_awaited()

    async def test_ascii_mixin_uses_aria_formatter(self):
        mixin = ASCIIMixin()
        mixin.ctx = self.ctx

        result = await mixin.asuccess(self.ctx, "ready", delay=60)

        self.assertIs(result, self.reply)
        payload = self.ctx.send.await_args.args[0]
        self.assertIn("ready", payload)

    async def test_asend_uses_aria_block_formatter(self):
        await asend(self.ctx, "sample", delay=60)

        self.assertIn("```ansi", self.ctx.send.await_args.args[0])


if __name__ == "__main__":
    unittest.main()