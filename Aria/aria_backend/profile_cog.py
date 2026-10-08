"""
Aria — Profile cog (modifyself).

Edits the logged-in account's profile:
  - display name (global_name)   -> PATCH /users/@me
  - avatar / banner (from URL)   -> PATCH /users/@me  (base64 data URI)
  - accent colour                -> PATCH /users/@me
  - bio ("About Me") / pronouns  -> PATCH /users/@me/profile

Drives the Aria "Profile" tab via IPC and mirrors every field as a
"." selfbot command (and "/profile" slash, wired in aria_backend).

Only touches YOUR OWN account through Discord's normal profile endpoints.
"""


import asyncio
import base64
import binascii
import re
from typing import Optional

import ansi
from profile_avatar import download_avatar_data_uri, image_to_data_uri

from modifyself.commands.cog import Cog
from modifyself.commands.core import command
from modifyself.http.route import Route

EMIT = None

# Discord 50035 sub-codes that mean "wait, not fix" — a retry cannot succeed.
_RATE_LIMIT_HINTS = {
    "AVATAR_RATE_LIMIT": "Discord limits how often the avatar can change. Wait about 10-30 minutes, then try again.",
    "BANNER_RATE_LIMIT": "Discord limits how often the banner can change. Wait about 10-30 minutes, then try again.",
}


def _friendly_error(exc: Exception) -> str:
    """Translate a Discord form-body error into a short, actionable message."""
    text = str(exc)
    for code, hint in _RATE_LIMIT_HINTS.items():
        if code in text:
            return hint
    return text[:300]

def _emit(obj: dict) -> None:
    if EMIT:
        try:
            EMIT(obj)
        except Exception:
            pass

def _parse_accent(value) -> Optional[int]:
    """Accept '#5b8cff', '5b8cff', '0x5b8cff', or an int -> Discord int colour."""
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 0xFFFFFF else None
    s = str(value).strip().lstrip("#")
    if s.lower().startswith("0x"):
        s = s[2:]
    if not re.fullmatch(r"[0-9a-fA-F]{6}", s):
        return None
    return int(s, 16)

async def _url_to_data_uri(url: str) -> Optional[str]:
    """Download an image URL and return a base64 data URI Discord accepts."""
    url = (url or "").strip()
    if not url:
        return None
    if url.startswith("data:"):
        _, separator, encoded = url.partition(",")
        if not separator:
            raise ValueError("Invalid image data URI")
        try:
            return image_to_data_uri(base64.b64decode(encoded, validate=True))
        except (ValueError, binascii.Error) as exc:
            raise ValueError(f"Invalid image data URI: {exc}") from exc
    return await asyncio.to_thread(download_avatar_data_uri, url)

class Profile(Cog):

    def __init__(self, bot):
        super().__init__(bot)

    async def _fetch_me(self) -> dict:
        try:
            return await self.bot._http.request(Route.me()) or {}
        except Exception:
            return {}

    async def _fetch_profile(self, uid) -> dict:
        try:
            data = await self.bot._http.request(Route.profile(int(uid))) or {}
            return data.get("user_profile") or {}
        except Exception:
            return {}

    async def snapshot(self) -> dict:
        me = await self._fetch_me()
        uid = me.get("id")
        prof = await self._fetch_profile(uid) if uid else {}
        avatar_url = None
        if me.get("avatar") and uid:
            ext = "gif" if str(me["avatar"]).startswith("a_") else "png"
            avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{me['avatar']}.{ext}?size=256"
        banner_url = None
        if me.get("banner") and uid:
            ext = "gif" if str(me["banner"]).startswith("a_") else "png"
            banner_url = f"https://cdn.discordapp.com/banners/{uid}/{me['banner']}.{ext}?size=600"
        accent = me.get("accent_color")
        return {
            "type": "profile_state",
            "profile": {
                "id": uid,
                "username": me.get("username", ""),
                "display_name": me.get("global_name") or "",
                "avatar_url": avatar_url,
                "banner_url": banner_url,
                "accent_color": accent,
                "accent_hex": (f"#{accent:06x}" if isinstance(accent, int) else ""),
                "bio": prof.get("bio", ""),
                "pronouns": prof.get("pronouns", ""),
            },
        }

    async def apply(self, fields: dict) -> dict:
        """Apply any subset of {display_name, avatar, banner, accent, bio, pronouns}.

        Returns {"changed": [...], "errors": [...]}.
        """
        changed: list = []
        errors: list = []
        if not isinstance(fields, dict):
            return {"changed": changed, "errors": ["bad payload"]}

        me_patch: dict = {}
        if "display_name" in fields:
            display_name = str(fields["display_name"]).strip()
            if len(display_name) > 32:
                errors.append("Display name must be 32 characters or fewer.")
            else:
                me_patch["global_name"] = display_name or None
        if "accent" in fields or "accent_color" in fields:
            acc = _parse_accent(fields.get("accent", fields.get("accent_color")))
            if acc is not None:
                me_patch["accent_color"] = acc
            elif str(fields.get("accent", fields.get("accent_color")) or "").strip():
                errors.append("invalid accent colour")
        for key, api_key in (("avatar", "avatar"), ("banner", "banner")):
            if key in fields:
                raw = fields[key]
                if raw in (None, "", "remove", "clear"):
                    me_patch[api_key] = None
                else:
                    try:
                        uri = await _url_to_data_uri(str(raw))
                        if uri:
                            me_patch[api_key] = uri
                        else:
                            errors.append(f"{key}: could not load image")
                    except Exception as e:
                        errors.append(f"{key}: {e}")

        if me_patch:
            try:
                await self.bot._http.edit_profile(**me_patch)
                changed.extend(
                    {"global_name": "display name", "avatar": "avatar",
                     "banner": "banner", "accent_color": "accent"}[k]
                    for k in me_patch
                )
            except Exception as e:
                errors.append(f"account update failed: {_friendly_error(e)}")

        prof_patch: dict = {}
        if "bio" in fields:
            bio = str(fields["bio"]).strip()
            if len(bio) > 190:
                errors.append("Bio must be 190 characters or fewer.")
            else:
                prof_patch["bio"] = bio
        if "pronouns" in fields:
            pronouns = str(fields["pronouns"]).strip()
            if len(pronouns) > 40:
                errors.append("Pronouns must be 40 characters or fewer.")
            else:
                prof_patch["pronouns"] = pronouns
        if prof_patch:
            try:
                await self.bot._http.edit_profile_details(**prof_patch)
                if "bio" in prof_patch:
                    changed.append("bio")
                if "pronouns" in prof_patch:
                    changed.append("pronouns")
            except Exception as e:
                errors.append(f"profile update failed: {_friendly_error(e)}")

        return {"changed": changed, "errors": errors}

    async def _reply(self, ctx, text):
        _emit({"type": "command"})
        import ascii_helper
        await ascii_helper.send_temp(ctx, text, 15)

    async def _run(self, ctx, field: str, value: str, label: str):
        value = (value or "").strip()
        if field in ("bio", "pronouns") and value.casefold() in {"clear", "remove"}:
            value = ""
        if not value and field not in ("avatar", "banner", "bio", "pronouns"):
            cmd = ctx.message.content.split()[0].lstrip(".")
            await self._reply(ctx, ansi.command_usage(cmd, f"{cmd} <{label}>",
                                                      f"Set your {label}.", "."))
            return
        if field in ("avatar", "banner") and not value:
            cmd = ctx.message.content.split()[0].lstrip(".")
            await self._reply(ctx, ansi.command_usage(cmd, f"{cmd} <image_url|remove>",
                                                      f"Set or clear your {label}.", "."))
            return
        result = await self.apply({field: value})
        _emit(await self.snapshot())
        if result.get("errors"):
            await self._reply(ctx, ansi.error("; ".join(result["errors"])))
        else:
            action = "cleared" if value.casefold() in {"clear", "remove"} or (not value and field in ("bio", "pronouns")) else "updated"
            await self._reply(ctx, ansi.success(f"{label.capitalize()} {action}."))

    @command(
        name="setdisplayname",
        aliases=["setname", "setdisplay", "setglobalname", "changename", "setdn"],
    )
    async def setdisplayname(self, ctx, *, value: str = ""):
        await self._run(ctx, "display_name", value, "display name")

    @command(name="setbio", aliases=["setabout"])
    async def setbio(self, ctx, *, value: str = ""):
        await self._run(ctx, "bio", value, "bio")

    @command(name="setpronouns")
    async def setpronouns(self, ctx, *, value: str = ""):
        await self._run(ctx, "pronouns", value, "pronouns")

    @command(name="setaccent", aliases=["setcolor", "setcolour"])
    async def setaccent(self, ctx, *, value: str = ""):
        await self._run(ctx, "accent", value, "accent colour")

    @command(name="setpfp", aliases=["setavatar", "spfp", "changepfp"])
    async def setpfp(self, ctx, *, value: str = ""):
        await self._run(ctx, "avatar", value, "avatar URL (blank/`remove` to clear)")

    @command(name="setbanner", aliases=["sbanner", "changebanner"])
    async def setbanner(self, ctx, *, value: str = ""):
        await self._run(ctx, "banner", value, "banner URL (blank/`remove` to clear)")

    @command(name="profile", aliases=["myprofile"])
    async def profile(self, ctx):
        snap = await self.snapshot()
        p = snap["profile"]
        _emit(snap)
        pairs = [
            ("Name", p["display_name"] or p["username"]),
            ("Handle", f"@{p['username']}"),
            ("Bio", p["bio"] or "-"),
            ("Pronouns", p["pronouns"] or "-"),
            ("Accent", p["accent_hex"] or "-"),
        ]
        await self._reply(ctx, ansi.header("profile") + "\n" + ansi.command_list(pairs))

def setup(bot):
    bot.add_cog(Profile(bot))
