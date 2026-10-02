import json
import logging
import os
import re
import time

logger = logging.getLogger(__name__)


class AFKSystem:
    def __init__(self, state_file="afk_state.json"):
        self.state_file = state_file
        self.afk_users = {}
        self.webhook_url = None
        self.last_afk_message = {}
        self.cooldown = 60

    def load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as handle:
                    data = json.load(handle)
                self.afk_users = data.get("afk_users", {}) or {}
                self.webhook_url = data.get("webhook_url")
        except Exception:
            self.afk_users = {}
            self.webhook_url = None

    def save_state(self):
        try:
            with open(self.state_file, "w") as handle:
                json.dump(
                    {
                        "afk_users": self.afk_users,
                        "webhook_url": self.webhook_url,
                    },
                    handle,
                    indent=2,
                )
        except Exception:
            pass

    def set_afk(self, user_id, reason="AFK"):
        user_id = str(user_id)
        self.afk_users[user_id] = {
            "reason": reason or "AFK",
            "since": int(time.time()),
        }
        logger.info("AFK enabled for user %s", user_id)
        return True

    def remove_afk(self, user_id):
        user_id = str(user_id)
        if user_id in self.afk_users:
            del self.afk_users[user_id]
            self.last_afk_message.pop(user_id, None)
            logger.info("AFK cleared for user %s", user_id)
            return True
        return False

    def is_afk(self, user_id):
        return str(user_id) in self.afk_users

    def get_afk_info(self, user_id):
        return self.afk_users.get(str(user_id), {})

    def get_time_message(self, user_id):
        afk_info = self.get_afk_info(user_id)
        since = int(afk_info.get("since") or 0)
        if not since:
            return ""

        elapsed = max(0, int(time.time() - since))
        days = elapsed // 86400
        hours = (elapsed % 86400) // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)

    def should_notify(self, user_id, channel_id, cooldown=None):
        user_id = str(user_id)
        channel_id = str(channel_id)
        current_time = time.time()
        effective_cooldown = self.cooldown if cooldown is None else max(0, int(cooldown))
        user_channels = self.last_afk_message.setdefault(user_id, {})
        last_time = float(user_channels.get(channel_id, 0) or 0)
        if current_time - last_time < effective_cooldown:
            return False
        return True

    def mark_notified(self, user_id, channel_id):
        user_id = str(user_id)
        channel_id = str(channel_id)
        user_channels = self.last_afk_message.setdefault(user_id, {})
        user_channels[channel_id] = time.time()

    def build_afk_notice(self, user_id):
        afk_info = self.get_afk_info(user_id)
        reason = self.get_afk_reason(user_id)
        return f"AFK {reason}".rstrip()

    def get_afk_reason(self, user_id):
        afk_info = self.get_afk_info(user_id)
        reason = " ".join(str(afk_info.get("reason") or "").split())
        return re.sub(r"^(?:(?:i['’]?m|i am)\s+)?afk\b\s*[:,-]?\s*", "", reason, flags=re.IGNORECASE)

    def build_afk_enabled_notice(self, user_id):
        reason = self.get_afk_reason(user_id)
        return f"> AFK enabled — {reason}" if reason else "> AFK enabled"

    @staticmethod
    def build_afk_cleared_notice(away_time=""):
        duration = str(away_time or "").strip()
        if duration and duration != "0s":
            return f"> Welcome back — away for {duration}"
        return "> Welcome back"

    def set_webhook(self, webhook_url):
        self.webhook_url = webhook_url.strip() if webhook_url else None
        return True


afk_system = AFKSystem()
