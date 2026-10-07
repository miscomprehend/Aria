import io
import json
import re
import sys
from contextlib import redirect_stdout
from urllib.parse import urlsplit

import warnings

import config

warnings.filterwarnings("ignore", message=".*Unverified HTTPS request.*")
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass


CAPTCHA_PROVIDERS = {"nocaptchaai", "yescaptcha", "twocaptcha"}


def _validate_captcha_api_url(value: str) -> str:
    api_url = str(value or "").strip().rstrip("/")
    parsed = urlsplit(api_url)
    if (
        len(api_url) > 2048
        or parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("The captcha provider API URL must be HTTPS and must not contain credentials, a query, or a fragment.")
    return api_url


def identify_token_owner(token: str) -> dict[str, str]:
    """Resolve the account ID attached to a token without exposing the token."""
    from api_client import DiscordAPIClient

    try:
        with redirect_stdout(io.StringIO()):
            profile = DiscordAPIClient(token).get_user_info(force=True)
    except Exception as error:
        raise ValueError(f"Could not verify this account token ({type(error).__name__}: {str(error)[:120]}). Check it and try again.") from error

    owner_id = str((profile or {}).get("id") or "").strip()
    if not re.fullmatch(r"[0-9]{15,22}", owner_id):
        raise ValueError("Could not verify this account token. Check it and try again.")
    username = str((profile or {}).get("username") or (profile or {}).get("global_name") or owner_id).strip()
    return {"id": owner_id, "username": username}


def _save_owner_identity(settings, owner_identity: dict[str, str]) -> None:
    owner_id = str(owner_identity.get("id") or "").strip()
    if not re.fullmatch(r"[0-9]{15,22}", owner_id):
        raise ValueError("A verified owner account ID is required.")
    settings.config["owner_id"] = owner_id
    settings.config["owner_username"] = str(owner_identity.get("username") or owner_id).strip()


def identify_saved_token_owner(config_path: str = "config.json") -> dict[str, str]:
    """Refresh configured owner identity from the already-saved account token."""
    with redirect_stdout(io.StringIO()):
        settings = config.Config(config_path)
    token = str(settings.get("token") or "").strip()
    if not token or token == "token here":
        raise ValueError("No saved account token is available to verify.")
    owner_identity = identify_token_owner(token)
    _save_owner_identity(settings, owner_identity)
    with redirect_stdout(io.StringIO()):
        settings.save_config()
    return owner_identity


def configure_token(
    token: str,
    remember: bool,
    config_path: str = "config.json",
    owner_identity: dict[str, str] | None = None,
    captcha_key: str = "",
    captcha_provider: str = "",
    captcha_api_url: str = "",
) -> None:
    if remember and not token:
        raise ValueError("Token is required when remembering it.")
    if remember and config._encrypter is None:
        raise RuntimeError("Token encryption is unavailable; install the cryptography dependency.")

    stored_token = token if remember else ""
    with redirect_stdout(io.StringIO()):
        settings = config.Config(config_path)
    settings.config["token"] = stored_token
    if captcha_key:
        if captcha_provider not in CAPTCHA_PROVIDERS:
            raise ValueError("Choose a supported captcha provider.")
        settings.config["captcha_api_key"] = captcha_key
        settings.config["captcha_provider"] = captcha_provider
        if captcha_provider == "yescaptcha":
            settings.config["yes_captcha_api_key"] = captcha_key
        elif captcha_provider == "twocaptcha":
            # Native 2Captcha uses the default https://2captcha.com endpoint; a
            # custom URL is only stored when the user supplies a compatible host.
            api_url = str(captcha_api_url or "").strip()
            if api_url and api_url.rstrip("/") != "https://2captcha.com":
                settings.config["captcha_api_url"] = _validate_captcha_api_url(api_url)
            else:
                settings.config["captcha_api_url"] = "https://2captcha.com"
    if owner_identity:
        _save_owner_identity(settings, owner_identity)
    settings.save_config()

    if remember:
        with open(settings.config_file, "r", encoding="utf-8") as handle:
            saved = json.load(handle).get("token", "")
        if not config._encrypter.is_encrypted(saved):
            raise RuntimeError("The token was not encrypted before saving.")


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "identify":
        owner_identity = identify_saved_token_owner()
        print(json.dumps({"owner": owner_identity}))
        return
    if action not in {"save", "clear"}:
        raise ValueError("Expected a save or clear action.")
    token = sys.stdin.readline().rstrip("\r\n")
    captcha_key = sys.stdin.readline().strip()
    captcha_provider = sys.stdin.readline().strip().lower()
    captcha_api_url = sys.stdin.readline().strip()
    if action == "save" and not token:
        raise ValueError("Token is required when remembering it.")
    owner_identity = identify_token_owner(token) if token else None
    configure_token(
        token, remember=action == "save", owner_identity=owner_identity,
        captcha_key=captcha_key, captcha_provider=captcha_provider, captcha_api_url=captcha_api_url,
    )
    print(json.dumps({"owner": owner_identity}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Token setup failed: {error}", file=sys.stderr)
        raise SystemExit(1)
