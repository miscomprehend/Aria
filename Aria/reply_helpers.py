"""Reusable formatted reply helpers for Aria command cogs."""

import asyncio
import logging

import formatter as fmt

logger = logging.getLogger(__name__)
_TASKS: set[asyncio.Task] = set()


async def _send_and_expire(ctx, text: str, delay: int = 15):
    """Delete the invoking command and expire Aria's reply after a fixed delay."""
    command_message = getattr(ctx, "message", None)
    if command_message is not None:
        try:
            await command_message.delete()
        except Exception as exc:
            logger.debug("Could not delete invoking command: %r", exc)

    try:
        message = await ctx.send(text)
    except Exception as exc:
        logger.warning("Could not send temporary command reply: %r", exc)
        return None

    if message is None or not callable(getattr(message, "delete", None)):
        logger.debug("Temporary reply did not return a deletable message")
        return message

    try:
        delay_seconds = max(1, int(delay or 15))
    except (TypeError, ValueError):
        delay_seconds = 15

    async def expire_reply():
        try:
            await asyncio.sleep(delay_seconds)
            await message.delete()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("Could not expire command reply: %r", exc)

    task = asyncio.create_task(expire_reply())
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return message


async def send_temp(ctx, text: str, delay: int = 15):
    return await _send_and_expire(ctx, text, delay)


class ASCIIMixin:
    async def aprint(self, ctx, title: str, lines: list, delay: int = 15):
        body = "\n".join(f"{fmt.WHITE}{str(line)}{fmt.RESET}" for line in (lines or []))
        return await send_temp(ctx, fmt.header(str(title)) + "\n" + fmt._block(body), delay)

    async def asuccess(self, ctx, message: str, delay: int = 15):
        return await send_temp(ctx, fmt.success(str(message)), delay)

    async def aerror(self, ctx, message: str, delay: int = 15):
        return await send_temp(ctx, fmt.error(str(message)), delay)

    async def awarn(self, ctx, message: str, delay: int = 15):
        return await send_temp(ctx, fmt.warning(str(message)), delay)


async def asend(ctx, text: str, delay: int = 15):
    return await send_temp(ctx, fmt._block(f"{fmt.WHITE}{text}{fmt.RESET}"), delay)