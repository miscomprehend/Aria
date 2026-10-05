import re
import time
import threading
from datetime import datetime
import urllib.parse

class NitroSniper:
    def __init__(self, api_client):
        self.api = api_client
        self.enabled = False
        self.used_codes = set()
        self.claimed_count = 0
        self.lock = threading.Lock()
        self.last_claimed = None       # {"code", "sender", "sender_id", "source"}
        self.stats = {"attempted": 0, "claimed": 0, "failed": 0, "invalid": 0}

    # ------------------------------------------------------------------
    # Public entry point — called from bot.py MESSAGE_CREATE
    # ------------------------------------------------------------------

    def check_message(self, message_data):
        if not self.enabled:
            return

        author = message_data.get("author") or {}
        author_id = str(author.get("id", ""))

        # Never act on own messages
        if author_id == str(getattr(self.api, "user_id", "") or ""):
            return

        # Spawn thread immediately for detection and claiming
        threading.Thread(target=self._process_message, args=(message_data,), daemon=True).start()

    def _process_message(self, message_data):
        # Use comprehensive text analysis like giveaway sniper
        full_text = self._full_text(message_data)

        # Multiple detection patterns for maximum speed
        nitro_codes = self._extract_nitro_codes(full_text)

        for code in nitro_codes:
            with self.lock:
                if code in self.used_codes:
                    continue
                self.used_codes.add(code)

            # Immediate claim attempt - no delays
            threading.Thread(target=self._claim_code_fast, args=(code, message_data), daemon=True).start()

    def _full_text(self, message_data):
        """Extract all text content from message, embeds, and components"""
        content = (message_data.get("content") or "").lower()

        # Add embed text
        embed_parts = []
        for embed in message_data.get("embeds") or []:
            embed_parts.append(str(embed.get("title") or ""))
            embed_parts.append(str(embed.get("description") or ""))
            for field in embed.get("fields") or []:
                embed_parts.append(str(field.get("name") or ""))
                embed_parts.append(str(field.get("value") or ""))
            embed_parts.append(str((embed.get("footer") or {}).get("text") or ""))
            embed_parts.append(str((embed.get("author") or {}).get("name") or ""))

        # Add component text (buttons, etc.)
        component_parts = []
        for component in message_data.get("components") or []:
            if isinstance(component, dict):
                component_parts.append(str(component.get("label") or ""))
                component_parts.append(str(component.get("placeholder") or ""))

        return content + " " + " ".join(embed_parts).lower() + " " + " ".join(component_parts).lower()

    def _extract_nitro_codes(self, text):
        """Ultra-fast nitro code extraction with multiple methods"""
        codes = set()

        # Method 1: Direct URL patterns (fastest)
        url_patterns = [
            r"discord\.gift/(\w{16,24})",
            r"discordapp\.com/gifts/(\w{16,24})",
            r"discord\.com/gifts/(\w{16,24})",
            r"discord\.com/billing/promotions/(\w{16,24})",
            r"gift/(\w{16,24})",  # Shortened links
        ]

        for pattern in url_patterns:
            found = re.findall(pattern, text, re.IGNORECASE)
            codes.update(found)

        # Method 2: Raw code detection (16 or 24 chars, alphanumeric)
        # Pre-compile patterns for speed
        if not hasattr(self, '_code_pattern'):
            self._code_pattern = re.compile(r'\b([a-zA-Z0-9]{16,24})\b')

        raw_codes = self._code_pattern.findall(text)
        for code in raw_codes:
            if len(code) in [16, 24] and code not in codes:
                # Additional validation - nitro codes are usually mixed case or all caps
                if any(c.isupper() for c in code) or any(c.islower() for c in code):
                    codes.add(code)

        # Method 3: Context-aware detection (look for giveaway/nitro keywords)
        nitro_keywords = ["nitro", "gift", "code", "redeem", "claim", "free"]
        has_nitro_context = any(kw in text for kw in nitro_keywords)

        if has_nitro_context:
            # More aggressive detection in nitro context
            aggressive_codes = re.findall(r'([A-Za-z0-9]{16,24})', text)
            for code in aggressive_codes:
                if len(code) in [16, 24]:
                    codes.add(code)

        return list(codes)
    
    def _claim_code_fast(self, code, message_data):
        """Ultra-fast nitro claiming with immediate API call"""
        start_time = time.time()
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        with self.lock:
            self.stats["attempted"] += 1

        try:
            # Immediate API call - no delays, no rate limiting checks for nitro (prioritize speed)
            if hasattr(self.api, "redeem_gift_code"):
                response = self.api.redeem_gift_code(code)
            else:
                response = self.api.request(
                    "POST",
                    f"/entitlements/gift-codes/{code}/redeem",
                    data={}
                )

            elapsed = (time.time() - start_time) * 1000

            if response and response.status_code == 200:
                response_data = response.json()
                response_text = str(response_data).lower()

                if "subscription_plan" in response_text or "nitro" in response_text:
                    with self.lock:
                        self.claimed_count += 1
                        self.stats["claimed"] += 1
                        author = message_data.get("author") or {}
                        sender_name = author.get("username") or author.get("global_name") or "Unknown"
                        sender_id = str(author.get("id", ""))
                        guild_id = message_data.get("guild_id")
                        channel_id = str(message_data.get("channel_id", ""))
                        source = f"Channel {channel_id}" if guild_id else f"DM ({channel_id})"
                        self.last_claimed = {
                            "code": code,
                            "sender": sender_name,
                            "sender_id": sender_id,
                            "source": source,
                        }
                    print(f"\033[1;32m[NITRO CLAIMED]\033[0m [{timestamp}] Code: {code} | sender={sender_name} | source={source} | {elapsed:.1f}ms ⚡")
                    return

                elif "already been redeemed" in response_text:
                    with self.lock:
                        self.stats["failed"] += 1
                    print(f"\033[1;33m[NITRO]\033[0m [{timestamp}] Already redeemed: {code} | {elapsed:.1f}ms")
                    return

                elif "unknown gift code" in response_text or "invalid" in response_text:
                    with self.lock:
                        self.stats["invalid"] += 1
                    print(f"\033[0;90m[NITRO]\033[0m [{timestamp}] Invalid code: {code} | {elapsed:.1f}ms")
                    return

            elif response and response.status_code == 429:
                with self.lock:
                    self.stats["failed"] += 1
                print(f"\033[1;31m[NITRO]\033[0m [{timestamp}] Rate limited on: {code} | {elapsed:.1f}ms")
                return

            elif response:
                with self.lock:
                    self.stats["failed"] += 1
                print(f"\033[1;31m[NITRO]\033[0m [{timestamp}] Failed: {code} | status={response.status_code} | {elapsed:.1f}ms")
                return

            # No response or other error
            with self.lock:
                self.stats["failed"] += 1
            print(f"\033[1;31m[NITRO ERROR]\033[0m [{timestamp}] No response for: {code} | {elapsed:.1f}ms")

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            with self.lock:
                self.stats["failed"] += 1
            print(f"\033[1;31m[NITRO ERROR]\033[0m [{timestamp}] {str(e)[:50]} | {elapsed:.1f}ms")
    
    def toggle(self, state=None):
        self.enabled = state if state is not None else not self.enabled
        status = "ENABLED" if self.enabled else "DISABLED"
        print(f"\033[1;36m[NITRO SNIPER]\033[0m {status} - Auto-detecting and claiming nitro codes ⚡")
        return self.enabled

    def clear_codes(self):
        with self.lock:
            count = len(self.used_codes)
            self.used_codes.clear()
            self.stats = {"attempted": 0, "claimed": 0, "failed": 0, "invalid": 0}
        print(f"\033[1;33m[NITRO]\033[0m Cleared {count} used codes from memory")
        return count

    def get_stats(self):
        """Get comprehensive nitro sniper statistics"""
        with self.lock:
            attempted = self.stats["attempted"]
            return {
                "enabled": self.enabled,
                "attempted": attempted,
                "claimed": self.stats["claimed"],
                "failed": self.stats["failed"],
                "invalid": self.stats["invalid"],
                "used_codes": len(self.used_codes),
                "used_codes_count": len(self.used_codes),
                "cached": len(self.used_codes),
                "last_claimed": self.last_claimed,
                "success_rate": f"{(self.stats['claimed'] / attempted * 100):.1f}%" if attempted else "0%",
            }

nitro_fast = None