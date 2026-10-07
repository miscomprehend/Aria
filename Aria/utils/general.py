import re
import unicodedata
import logging
from typing import Dict

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

# Global variable to store max message length per user ID
MAX_MESSAGE_LENGTH: Dict[int, int] = {}


async def detect_message_limit(bot: commands.Bot) -> int:
    """Detect the max message length for the bot user. Returns 4000 for Nitro, 2000 otherwise."""
    try:
        if bot.user.id not in MAX_MESSAGE_LENGTH:
            premium_type = getattr(bot.user, "premium_type", None)
            premium_value = getattr(premium_type, "value", premium_type)
            has_nitro = premium_value in {1, 2, 3}
            limit = 4000 if has_nitro else 2000
            MAX_MESSAGE_LENGTH[bot.user.id] = limit
            logger.info(f"Message limit for {bot.user.name}: {limit} (Nitro: {has_nitro})")
        return MAX_MESSAGE_LENGTH[bot.user.id]
    except Exception as e:
        logger.error(f"Error in message limit detection: {e}")
        return 2000


def get_max_message_length(bot: commands.Bot) -> int:
    """Get the cached max message length, defaulting to 2000."""
    return MAX_MESSAGE_LENGTH.get(bot.user.id, 2000)


def format_as_yaml_code_block(results: list) -> str:
    formatted_rows = []
    for result in results:
        formatted_result = result.split('\n')
        source_line = formatted_result[0]
        data_lines = formatted_result[1:]
        formatted_rows.append(f"{source_line}\n" + "\n".join(data_lines))
    yaml_formatted = "\n\n".join(formatted_rows)
    return f"```yaml\n{yaml_formatted}\n```"


def calculate_chunk_size(total_results: int) -> int:
    if total_results <= 9:
        return total_results
    elif total_results <= 18:
        return (total_results + 1) // 2
    else:
        return min(20, max(9, (total_results + 2) // 3))


def is_valid_emoji(emoji: str) -> bool:
    """Check if a string is a valid emoji using discord.py's emoji parsing, with unicodedata fallback."""
    if not emoji:
        return False
    try:
        # Reject :word: style that aren't real emojis
        if emoji.startswith(':') and emoji.endswith(':') and len(emoji) > 2:
            emoji_name = emoji[1:-1]
            if len(emoji_name) <= 2 or emoji_name.isalpha():
                return False

        partial_emoji = discord.PartialEmoji.from_str(emoji)

        if partial_emoji.is_custom_emoji() and partial_emoji.id is not None:
            return True

        if partial_emoji.is_unicode_emoji():
            if emoji.isalpha() and len(emoji) > 1:
                return False
            if str(partial_emoji) != emoji:
                return False
            if emoji.startswith(':') and emoji.endswith(':'):
                if len(emoji[1:-1]) <= 3:
                    return False
            return True

        return False
    except Exception:
        # Fallback: unicodedata check
        value = str(emoji)
        if len(value) > 2 and value.startswith('<') and value.endswith('>'):
            return True
        for symbol in value:
            category = unicodedata.category(symbol)
            if category == 'So' or 'EMOJI' in unicodedata.name(symbol, ''):
                return True
        return False


def filter_valid_emojis(emojis):
    return [emoji for emoji in emojis if is_valid_emoji(emoji)]


def format_message(content, code_block=True, escape_backticks=True):
    """Format a message, optionally wrapping in inline code block."""
    if escape_backticks and code_block:
        content = content.replace('`', '\\`') if isinstance(content, str) else str(content)
    if code_block:
        if '`' in content and not escape_backticks:
            return content
        return f"`{content}`"
    return content


def quote_block(text: str) -> str:
    """Add > prefix to each line."""
    return '\n'.join(f'> {line}' for line in text.split('\n'))


async def parse_users_and_emojis(bot, ctx, args):
    users = []
    emojis = []

    for arg in args:
        if is_valid_emoji(arg):
            emojis.append(arg)
        elif arg.startswith('<@') and arg.endswith('>'):
            user_id = int(arg[2:-1].replace('!', ''))
            user = discord.utils.get(bot.users, id=user_id)
            if user:
                users.append(user)
            else:
                logger.debug(f"Failed to fetch user for mention: {arg}")
        else:
            try:
                user_id = int(arg)
                user = discord.utils.get(bot.users, id=user_id)
                if user:
                    users.append(user)
                else:
                    logger.debug(f"Failed to fetch user for ID: {user_id}")
            except ValueError:
                user = discord.utils.get(bot.users, name=arg)
                if user:
                    users.append(user)
                else:
                    logger.debug(f"Failed to fetch user for name: {arg}")
                    placeholder = discord.Object(id=0)
                    placeholder.name = arg
                    users.append(placeholder)

    if not users and ctx.guild is None:
        users.append(ctx.author)

    return users, emojis
