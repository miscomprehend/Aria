"""
Token Encrypter — symmetric encryption for secrets stored in config.json.

Encryption key is stored in `.aria_key` (never committed).
Encrypted values are prefixed with `enc:` so the system can detect them.

Usage:
    from token_encrypter import TokenEncrypter
    enc = TokenEncrypter()
    enc.encrypt_config("config.json")       # one-time: encrypts plaintext tokens
    token = enc.decrypt("enc:...")           # returns plaintext
"""

import os
import json
import base64
from cryptography.fernet import Fernet

KEY_FILE = os.path.join(os.path.dirname(__file__), ".aria_key")
ENC_PREFIX = "enc:"

# Fields in config.json that should be encrypted
SENSITIVE_KEYS = {
    "token",
    "vr_oauth_token",
    "discord_client_secret",
    "discord_bot_token",
    "captcha_api_key",
    "yes_captcha_api_key",
    "mongo_uri",
}


class TokenEncrypter:
    def __init__(self, key_file: str = KEY_FILE):
        self.key_file = key_file
        self._fernet = Fernet(self._load_or_create_key())

    # ── Key management ────────────────────────────────────────────────────────

    def _load_or_create_key(self) -> bytes:
        """Load existing key or generate and persist a new one."""
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as f:
                return f.read().strip()
        key = Fernet.generate_key()
        with open(self.key_file, "wb") as f:
            f.write(key)
        # Restrict permissions so only the owner can read it
        try:
            os.chmod(self.key_file, 0o600)
        except OSError:
            pass
        return key

    # ── Core encrypt / decrypt ────────────────────────────────────────────────

    def encrypt(self, plaintext: str) -> str:
        """Return `enc:<base64-ciphertext>` for a plaintext string."""
        if not plaintext or plaintext.startswith(ENC_PREFIX):
            return plaintext
        token_bytes = plaintext.encode("utf-8")
        encrypted = self._fernet.encrypt(token_bytes)
        return ENC_PREFIX + base64.urlsafe_b64encode(encrypted).decode("utf-8")

    def decrypt(self, value: str) -> str:
        """Return plaintext for an `enc:…` value; pass through non-encrypted values unchanged."""
        if not value or not value.startswith(ENC_PREFIX):
            return value
        raw = base64.urlsafe_b64decode(value[len(ENC_PREFIX):].encode("utf-8"))
        return self._fernet.decrypt(raw).decode("utf-8")

    def is_encrypted(self, value: str) -> bool:
        return isinstance(value, str) and value.startswith(ENC_PREFIX)

    # ── Config file helpers ───────────────────────────────────────────────────

    def encrypt_config(self, config_file: str = "config.json") -> int:
        """
        Encrypt all sensitive plaintext values in a config file in-place.
        Returns the number of fields encrypted.
        """
        if not os.path.exists(config_file):
            return 0
        with open(config_file, "r") as f:
            data = json.load(f)

        changed = 0
        for key in SENSITIVE_KEYS:
            val = data.get(key, "")
            if val and isinstance(val, str) and not self.is_encrypted(val):
                data[key] = self.encrypt(val)
                changed += 1

        if changed:
            with open(config_file, "w") as f:
                json.dump(data, f, indent=4)

        return changed

    def decrypt_config(self, config: dict) -> dict:
        """
        Return a copy of `config` with all `enc:…` values decrypted.
        Does not touch the file on disk.
        """
        result = dict(config)
        for key in SENSITIVE_KEYS:
            val = result.get(key, "")
            if self.is_encrypted(val):
                result[key] = self.decrypt(val)
        return result


# ── CLI helper ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    enc = TokenEncrypter()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "encrypt-config"

    if cmd == "encrypt-config":
        cfg = sys.argv[2] if len(sys.argv) > 2 else "config.json"
        n = enc.encrypt_config(cfg)
        print(f"[token_encrypter] Encrypted {n} field(s) in {cfg}")

    elif cmd == "encrypt":
        val = sys.argv[2] if len(sys.argv) > 2 else ""
        print(enc.encrypt(val))

    elif cmd == "decrypt":
        val = sys.argv[2] if len(sys.argv) > 2 else ""
        print(enc.decrypt(val))

    elif cmd == "show-key":
        with open(enc.key_file, "rb") as f:
            print(f.read().decode())

    else:
        print("Usage: python token_encrypter.py [encrypt-config|encrypt|decrypt|show-key] [value]")
