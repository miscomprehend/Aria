import os
import threading
import urllib.parse
import time
import re


GIVEAWAY_KEYWORDS = [
    "giveaway", "prize", "hosted by", "ends in", "react to win", "🎉",
    "win", "winner", "congratulations", "reward", "raffle", "event", "drop",
    "claim your prize", "enter to win", "react to enter", "click to enter",
    "join to win", "give away", "🎁", "🎊", "🎈", "🪅", "🥳",
]
_CUSTOM_EMOJI = re.compile(r"<(a?):([^:>]+):([0-9]{15,25})>")
_ENTRY_INSTRUCTIONS = ("react", "reaction", "emoji", "entry", "enter", "join", "click")
_GIVEAWAY_EMOJIS = ("🎉", "🎁", "🎊", "🎈", "🪅", "🥳")


def iter_component_nodes(node):
    if isinstance(node, list):
        for item in node:
            yield from iter_component_nodes(item)
    elif isinstance(node, dict):
        yield node
        for key in ("components", "components_v2", "items", "accessory", "children", "elements", "nodes"):
            if node.get(key):
                yield from iter_component_nodes(node[key])


def component_text(message_data: dict) -> str:
    roots = list(message_data.get("components") or []) + list(message_data.get("components_v2") or [])
    parts = []
    for node in iter_component_nodes(roots):
        for key in ("content", "label", "description", "placeholder", "title", "text"):
            value = node.get(key)
            if isinstance(value, str):
                parts.append(value)
        emoji = node.get("emoji")
        if isinstance(emoji, str):
            parts.append(emoji)
        elif isinstance(emoji, dict):
            name, emoji_id = emoji.get("name"), emoji.get("id")
            if emoji_id and name:
                animated = "a" if emoji.get("animated") else ""
                parts.append(f"<{animated}:{name}:{emoji_id}>")
            elif name:
                parts.append(str(name))
    return " ".join(parts)


def extract_entry_emojis(text: str) -> list[str]:
    lowered = text.lower()
    instruction_positions = [
        lowered.find(term)
        for term in _ENTRY_INSTRUCTIONS
        if lowered.find(term) >= 0
    ]
    has_instruction = bool(instruction_positions)
    relevant_text = text[min(instruction_positions):] if has_instruction else ""
    custom_text = relevant_text or text
    matches = [
        (
            match.start(),
            match.end(),
            f"{'a:' if match.group(1) else ''}{match.group(2)}:{match.group(3)}",
        )
        for match in _CUSTOM_EMOJI.finditer(custom_text)
    ]

    i = 0
    while i < len(relevant_text):
        char = relevant_text[i]
        codepoint = ord(char)
        start = i
        if char in "#*0123456789":
            end = i + 1
            if end < len(relevant_text) and relevant_text[end] == "\ufe0f":
                end += 1
            if end < len(relevant_text) and relevant_text[end] == "\u20e3":
                matches.append((start, end + 1, relevant_text[start:end + 1]))
                i = end + 1
                continue
        is_emoji = (
            0x1F000 <= codepoint <= 0x1FAFF
            or 0x2600 <= codepoint <= 0x27BF
            or 0x1F1E6 <= codepoint <= 0x1F1FF
            or char in "©®™"
        )
        if not is_emoji:
            i += 1
            continue
        end = i + 1
        if 0x1F1E6 <= codepoint <= 0x1F1FF and end < len(relevant_text):
            next_codepoint = ord(relevant_text[end])
            if 0x1F1E6 <= next_codepoint <= 0x1F1FF:
                end += 1
        while end < len(relevant_text):
            next_char = relevant_text[end]
            next_codepoint = ord(next_char)
            if (
                next_char in {"\ufe0e", "\ufe0f", "\u20e3"}
                or 0x1F3FB <= next_codepoint <= 0x1F3FF
                or 0x0300 <= next_codepoint <= 0x036F
            ):
                end += 1
            elif next_char == "\u200d" and end + 1 < len(relevant_text):
                end += 2
            else:
                break
        matches.append((start, end, relevant_text[start:end]))
        i = end

    if not has_instruction and not matches:
        for emoji in _GIVEAWAY_EMOJIS:
            position = text.find(emoji)
            if position >= 0:
                matches.append((position, position + len(emoji), emoji))

    matches.sort(key=lambda item: item[0])
    result = []
    for _, _, emoji in matches:
        if emoji not in result:
            result.append(emoji)
    return result


class GiveawaySniper:
    def __init__(self, api_client):
        self.api = api_client
        self.enabled = False
        self._entered = set()          # message IDs already entered
        self._entering = set()
        self._lock = threading.Lock()
        self.stats = {"entered": 0, "won": 0, "failed": 0}
        self.last_win = None           # {"sender", "sender_id", "source", "channel_id", "guild_id"}

    # ------------------------------------------------------------------
    # Public entry point — called from bot.py MESSAGE_CREATE
    # ------------------------------------------------------------------

    def check_message(self, message_data: dict, check_win: bool = True):
        if not self.enabled:
            return

        author = message_data.get("author") or {}
        author_id = str(author.get("id", ""))
        is_bot = author.get("bot", False)

        # Never act on own messages
        if author_id == str(getattr(self.api, "user_id", "") or ""):
            return

        # Win detection — any message that mentions us
        if check_win:
            threading.Thread(
                target=self._check_win, args=(message_data,), daemon=True
            ).start()

        # Giveaway entry — bot, webhook, or app messages
        is_webhook = bool(message_data.get("webhook_id"))
        is_app = bool(message_data.get("application_id"))
        if is_bot or is_webhook or is_app:
            threading.Thread(
                target=self._try_enter, args=(message_data,), daemon=True
            ).start()

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _full_text(self, message_data: dict) -> str:
        content = (message_data.get("content") or "").lower()
        embed_parts = []
        for embed in message_data.get("embeds") or []:
            embed_parts.append(str(embed.get("title") or ""))
            embed_parts.append(str(embed.get("description") or ""))
            for field in embed.get("fields") or []:
                embed_parts.append(str(field.get("name") or ""))
                embed_parts.append(str(field.get("value") or ""))
            embed_parts.append(str((embed.get("footer") or {}).get("text") or ""))
            embed_parts.append(str((embed.get("author") or {}).get("name") or ""))
        return content + " " + " ".join(embed_parts + [component_text(message_data)]).lower()

    def _is_giveaway(self, message_data: dict) -> bool:
        return any(kw in self._full_text(message_data) for kw in GIVEAWAY_KEYWORDS)

    def _already_reacted(self, message_data: dict) -> bool:
        for r in message_data.get("reactions") or []:
            if r.get("me"):
                return True
        return False

    def _entry_emoji_from_text(self, message_data: dict):
        parts = [str(message_data.get("content") or "")]
        for embed in message_data.get("embeds") or []:
            parts.append(str(embed.get("title") or ""))
            parts.append(str(embed.get("description") or ""))
            for field in embed.get("fields") or []:
                parts.append(str(field.get("name") or ""))
                parts.append(str(field.get("value") or ""))
            parts.append(str((embed.get("footer") or {}).get("text") or ""))

        parts.append(component_text(message_data))
        return extract_entry_emojis("\n".join(parts))

    # ------------------------------------------------------------------
    # Entry logic — button first, reactions fallback
    # ------------------------------------------------------------------

    def _button_candidates(self, message_data: dict):
        roots = []
        roots.extend(message_data.get("components") or [])
        roots.extend(message_data.get("components_v2") or [])

        buttons = []
        for node in iter_component_nodes(roots):
            if int(node.get("type") or 0) != 2:
                continue
            if not node.get("custom_id"):
                continue  # Skip link buttons; they can't be clicked via interaction payload.
            buttons.append(node)
        return buttons

    def _first_button(self, message_data: dict):
        buttons = self._button_candidates(message_data)
        if not buttons:
            return None

        # Prefer buttons that look like giveaway entry actions.
        preferred_terms = (
            "enter", "join", "participate", "entries", "entry", "claim", "giveaway"
        )
        for b in buttons:
            label = str(b.get("label") or "").lower()
            custom_id = str(b.get("custom_id") or "").lower()
            if any(t in label or t in custom_id for t in preferred_terms):
                return b
        return buttons[0]

    def _reaction_identifiers(self, message_data: dict):
        result = []
        for r in message_data.get("reactions") or []:
            if r.get("me"):
                continue
            if (r.get("count") or 0) <= 0:
                continue
            enc = self._encode_emoji(r.get("emoji"))
            if enc:
                result.append(enc)
        return result

    @staticmethod
    def _encode_emoji(emoji) -> str:
        if not emoji:
            return ""
        if isinstance(emoji, str):
            if re.fullmatch(r"(?:a:)?[^:]+:\d{15,25}", emoji):
                return emoji.removeprefix("a:")
            return urllib.parse.quote(emoji)
        eid = emoji.get("id")
        name = emoji.get("name") or ""
        if eid:
            return f"{name}:{eid}"
        return urllib.parse.quote(name) if name else ""

    def _try_enter(self, message_data: dict):
        if not self._is_giveaway(message_data):
            return

        msg_id = str(message_data.get("id", ""))

        with self._lock:
            if not msg_id or msg_id in self._entered or msg_id in self._entering:
                return
            self._entering.add(msg_id)

        try:
            if self._already_reacted(message_data):
                return

            button = self._first_button(message_data)
            reactions = self._reaction_identifiers(message_data)
            for emoji in self._entry_emoji_from_text(message_data):
                encoded = self._encode_emoji(emoji)
                if encoded and encoded not in reactions:
                    reactions.append(encoded)

            success = False
            if button:
                success = self._click_button(message_data, button)
            if not success and reactions:
                success = self._add_reactions(message_data, reactions)
            if not success and not button and not reactions:
                success = self._add_reactions(message_data, [urllib.parse.quote("🎉")])

            if success:
                with self._lock:
                    self._entered.add(msg_id)
                self.stats["entered"] += 1
                guild = message_data.get("guild_id", "DM")
                channel = message_data.get("channel_id", "?")
                ts = time.strftime("%H:%M:%S")
                print(
                    f"\033[1;34m[GIVEAWAY]\033[0m [{ts}] Entered | guild={guild} "
                    f"| channel={channel} | msg={msg_id} | total={self.stats['entered']}"
                )
            else:
                self.stats["failed"] += 1
                guild = message_data.get("guild_id", "DM")
                channel = message_data.get("channel_id", "?")
                ts = time.strftime("%H:%M:%S")
                print(
                    f"\033[1;31m[GIVEAWAY]\033[0m [{ts}] Failed entry | guild={guild} "
                    f"| channel={channel} | msg={msg_id} | total_failed={self.stats['failed']}"
                )
        finally:
            with self._lock:
                self._entering.discard(msg_id)

    def _click_button(self, message_data: dict, button: dict) -> bool:
        guild_id = message_data.get("guild_id")
        channel_id = message_data.get("channel_id")
        message_id = message_data.get("id")
        custom_id = button.get("custom_id")
        if guild_id and channel_id and message_id and custom_id and hasattr(self.api, "click_button"):
            try:
                application_id = (
                    str(message_data.get("application_id") or "")
                    or str((message_data.get("interaction_metadata") or {}).get("id") or "")
                    or str((message_data.get("author") or {}).get("id", ""))
                )
                return bool(
                    self.api.click_button(
                        str(guild_id),
                        str(channel_id),
                        str(message_id),
                        str(application_id),
                        str(custom_id),
                        int(message_data.get("flags", 0) or 0),
                    )
                )
            except Exception:
                pass

        application_id = (
            str(message_data.get("application_id") or "")
            or str((message_data.get("interaction_metadata") or {}).get("id") or "")
            or str((message_data.get("author") or {}).get("id", ""))
        )
        payload = {
            "type": 3,
            "nonce": str(int.from_bytes(os.urandom(8), "big") % (10**19 - 10**18) + 10**18),
            "guild_id": message_data.get("guild_id"),
            "channel_id": message_data.get("channel_id"),
            "message_flags": message_data.get("flags", 0),
            "message_id": message_data.get("id"),
            "application_id": application_id,
            "session_id": "0",
            "data": {
                "component_type": button.get("type", 2),
                "custom_id": button.get("custom_id"),
            },
        }
        try:
            resp = self.api.request(
                "POST",
                "/interactions",
                data=payload
            )
            return resp is not None and resp.status_code in (200, 204)
        except Exception:
            return False

    def _add_reactions(self, message_data: dict, identifiers: list) -> bool:
        channel_id = message_data.get("channel_id")
        msg_id = message_data.get("id")
        success = False
        for enc in identifiers:
            try:
                if hasattr(self.api, "add_reaction"):
                    raw_emoji = urllib.parse.unquote(str(enc or ""))
                    if self.api.add_reaction(str(channel_id), str(msg_id), raw_emoji):
                        success = True
                    continue

                resp = self.api.request(
                    "PUT",
                    f"/channels/{channel_id}/messages/{msg_id}/reactions/{enc}/@me"
                )
                if resp is not None and resp.status_code in (200, 204):
                    success = True
            except Exception:
                pass
        return success

    # ------------------------------------------------------------------
    # Win detection
    # ------------------------------------------------------------------

    def _check_win(self, message_data: dict):
        user_id = str(getattr(self.api, "user_id", "") or "")
        if not user_id:
            return

        content = self._full_text(message_data)
        mentions = message_data.get("mentions") or []

        mentioned = (
            f"<@{user_id}>" in content
            or f"<@!{user_id}>" in content
            or any(str((m or {}).get("id", "")) == user_id for m in mentions)
        )

        if mentioned and any(kw in content for kw in ["congratulations", "won", "winner", "🎉"]):
            self.stats["won"] += 1
            ts = time.strftime("%H:%M:%S")
            author = message_data.get("author") or {}
            sender_name = author.get("username") or author.get("global_name") or "Unknown"
            sender_id = str(author.get("id", ""))
            guild_id = message_data.get("guild_id")
            channel_id = str(message_data.get("channel_id", ""))
            source = f"Channel {channel_id}" if guild_id else f"DM ({channel_id})"
            self.last_win = {
                "sender": sender_name,
                "sender_id": sender_id,
                "source": source,
                "channel_id": channel_id,
                "guild_id": guild_id or "DM",
            }
            print(
                f"\033[1;32m[GIVEAWAY WIN]\033[0m [{ts}] WON! | sender={sender_name} "
                f"| source={source} | total_wins={self.stats['won']}"
            )

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def toggle(self, state=None):
        self.enabled = state if state is not None else not self.enabled
        return self.enabled

    def get_stats(self) -> dict:
        return {
            "enabled": self.enabled,
            "entered": self.stats["entered"],
            "won": self.stats["won"],
            "failed": self.stats["failed"],
            "last_win": self.last_win,
        }
