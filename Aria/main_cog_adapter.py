"""Run aria_backend cogs through the synchronous command system in main.py."""

import asyncio
import importlib
import json
import logging
import sys
import threading
from email.parser import BytesParser
from email.policy import default as email_policy
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from bot import Command


_LOGGER = logging.getLogger(__name__)
_COGS = (
    ("rpc_cog", "RPC"),
    ("spotify_cog", "SpotifyLyrics"),
    ("logger_cog", "MessageLogger"),
    ("profile_cog", "Profile"),
    ("antigc_cog", "AntiGC"),
    ("friends_cog", "Friends"),
    ("gc_cog", "GCSecurity"),
    ("gcextra_cog", "GCExtra"),
    ("guild_cog", "Guild"),
    ("reactions_cog", "Reactions"),
    ("nitro_cog", "Nitro"),
    ("giveaway_cog", "Giveaway"),
    ("owo_cog", "OwoFarm"),
)


class _WreqStatus:
    def __init__(self, value):
        self._value = int(value or 0)

    def as_int(self):
        return self._value


class _WreqResponse:
    def __init__(self, response):
        self.status = _WreqStatus(getattr(response, "status_code", 0))
        self._response = response

    async def text(self):
        try:
            return self._response.text or ""
        except Exception:
            return ""


class _HttpClientShim:
    """Adapt the small wreq interface used by the RPC cog to DiscordAPIClient."""

    def __init__(self, http):
        self._http = http

    async def request(self, method, url, *, headers=None, body=None, json=None):
        method_name = getattr(method, "name", None) or getattr(method, "value", None) or method
        method_name = str(method_name).rsplit(".", 1)[-1].upper()
        parsed = urlsplit(str(url))
        path = parsed.path or "/"
        prefix = "/api/v9"
        if path == prefix:
            path = "/"
        elif path.startswith(prefix + "/"):
            path = path[len(prefix):]
        payload = json
        files = None
        if body is not None:
            content_type = next(
                (v for k, v in (headers or {}).items() if k.casefold() == "content-type"),
                "",
            )
            if content_type.casefold().startswith("multipart/form-data"):
                payload, files = self._parse_multipart(content_type, body)
            else:
                payload = json.loads(body) if isinstance(body, (bytes, bytearray, str)) else body
        if files:
            headers = {
                key: value
                for key, value in (headers or {}).items()
                if key.casefold() != "content-type"
            }
        response = await self._http.request(
            method_name,
            path,
            json=payload,
            files=files,
            headers=headers,
        )
        return _WreqResponse(response)

    @staticmethod
    def _parse_multipart(content_type, body):
        message = BytesParser(policy=email_policy).parsebytes(
            b"MIME-Version: 1.0\r\n"
            + f"Content-Type: {content_type}\r\n\r\n".encode()
            + (body if isinstance(body, bytes) else bytes(body))
        )
        payload = {}
        files = {}
        for part in message.iter_parts():
            disposition = part.get_content_disposition()
            name = part.get_param("name", header="content-disposition")
            if disposition != "form-data" or not name:
                continue
            content = part.get_payload(decode=True) or b""
            filename = part.get_filename()
            if filename is None:
                if name == "payload_json":
                    payload = json.loads(content.decode("utf-8"))
            else:
                files[name] = (
                    filename,
                    content,
                    part.get_content_type(),
                )
        return payload, files or None


class _HttpShim:
    def __init__(self, api):
        self._api = api
        self.token = api.token
        self._spoofer = _SpooferShim(api.header_spoofer)
        self._client = _HttpClientShim(self)

    def _get_client(self):
        return self._client

    async def request(self, route, *, json=None, data=None, params=None, headers=None, files=None, **kwargs):
        method = str(getattr(route, "method", "GET")).upper()
        path = str(getattr(route, "path", route))
        return await asyncio.to_thread(
            self._request_sync,
            method,
            path,
            json,
            data,
            params,
            headers,
            files,
            kwargs.get("timeout", 30),
        )

    def _request_sync(self, method, path, payload, data, params, headers, files, timeout):
        response = self._api.request(
            method,
            path,
            data=payload if payload is not None else data,
            params=params,
            headers=headers,
            files=files,
            timeout=timeout,
        )
        if response is None:
            raise RuntimeError(f"Discord request failed: {method} {path}")
        status = int(getattr(response, "status_code", 0) or 0)
        if not 200 <= status < 300:
            try:
                body = response.json()
            except Exception:
                body = getattr(response, "text", "")
            raise RuntimeError(f"Discord request failed: HTTP {status}: {str(body)[:300]}")
        if status == 204:
            return None
        try:
            return response.json()
        except (ValueError, AttributeError):
            return None

    async def edit_profile(self, **fields):
        return await self.request(
            SimpleNamespace(method="PATCH", path="/users/@me"),
            json=fields,
        )


class _SpooferShim:
    def __init__(self, spoofer):
        self._spoofer = spoofer

    def __getattr__(self, name):
        return getattr(self._spoofer, name)

    def get_headers(self, **kwargs):
        headers = self._spoofer.get_protected_headers()
        referer = kwargs.get("referer")
        if referer:
            headers["Referer"] = referer
        return headers


class _SocketShim:
    def __init__(self, bot):
        self._bot = bot

    async def close(self, *_args, **_kwargs):
        self._bot._schedule_reconnect("cog requested gateway reconnect")


class _GatewayShim:
    def __init__(self, bot):
        self._bot = bot
        self._closed_event = asyncio.Event()
        self._reconnect_attempts = 0

    @property
    def _session_id(self):
        return self._bot.session_id

    @_session_id.setter
    def _session_id(self, value):
        self._bot.session_id = value
        self._bot.can_resume = bool(value)

    @property
    def _ws(self):
        return _SocketShim(self._bot) if self._bot.ws else None

    async def send_json(self, payload):
        ws = self._bot.ws
        if ws is None:
            raise RuntimeError("Gateway is not connected.")
        await asyncio.to_thread(ws.send, json.dumps(payload))


class _CogBotFacade:
    def __init__(self, bot):
        self._main_bot = bot
        self._http = _HttpShim(bot.api)
        self._gateway = _GatewayShim(bot)
        self.command_prefix = bot.prefix
        self._commands = []
        self._listeners = {}

    @property
    def user(self):
        user_id = self._main_bot.user_id
        return SimpleNamespace(id=int(user_id)) if str(user_id or "").isdigit() else None

    @property
    def session_id(self):
        return self._main_bot.session_id

    def add_command(self, command):
        self._commands.append(command)

    def remove_command(self, _name):
        return None

    def add_listener(self, event, callback):
        self._listeners.setdefault(str(event).upper(), []).append(callback)

    def remove_listener(self, event, callback):
        listeners = self._listeners.get(str(event).upper(), [])
        if callback in listeners:
            listeners.remove(callback)


class MainCogRuntime:
    def __init__(self, bot):
        self.bot = bot
        self.facade = _CogBotFacade(bot)
        self.loop = asyncio.new_event_loop()
        self._started = threading.Event()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="MainCogRuntime",
            daemon=True,
        )
        self._thread.start()
        if not self._started.wait(5):
            raise RuntimeError("Timed out starting the main cog event loop.")
        try:
            self.cogs = self._load_cogs()
            self.commands = self._index_cog_commands()
            self._register_commands()
        except Exception:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self._thread.join(timeout=5)
            raise

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self._started.set()
        self.loop.run_forever()

    def _load_cogs(self):
        cog_dir = Path(__file__).resolve().parent / "aria_backend"
        if not cog_dir.is_dir():
            raise RuntimeError(f"Cog directory is missing: {cog_dir}")
        cog_dir_text = str(cog_dir)
        if cog_dir_text not in sys.path:
            sys.path.insert(0, cog_dir_text)

        cogs = []
        for module_name, class_name in _COGS:
            module = importlib.import_module(module_name)
            cog_class = getattr(module, class_name)
            cog = cog_class(self.facade)
            cog._inject(self.facade)
            cogs.append(cog)
        return cogs

    def _index_cog_commands(self):
        indexed = {}
        for command in self.facade._commands:
            for key in (command.name, *command.aliases):
                normalized = str(key or "").strip().lower()
                if not normalized:
                    continue
                if normalized in indexed:
                    raise RuntimeError(f"Duplicate cog command or alias: {normalized}")
                indexed[normalized] = command
                compact = self.bot._normalize_command_key(normalized)
                compact_owner = indexed.get(compact)
                if compact_owner is not None and compact_owner is not command:
                    raise RuntimeError(f"Conflicting normalized cog command: {normalized}")
                indexed[compact] = command
        return indexed

    def _register_commands(self):
        for command in self.facade._commands:
            existing = self.bot._resolve_command(command.name)
            self._remove_main_command(existing)
            aliases = list(dict.fromkeys(
                str(alias)
                for alias in command.aliases
                if str(alias).strip()
            ))
            adapter = Command(
                self._make_handler(command),
                command.name,
                aliases,
            )
            self.bot._register_command_key(command.name, adapter)
            for alias in aliases:
                # Never let an alias shadow another cog command, including
                # spellings that normalize to the same command key.
                compact = self.bot._normalize_command_key(alias)
                cog_owner = self.commands.get(alias.lower()) or self.commands.get(compact)
                if cog_owner is not None and cog_owner is not command:
                    continue
                self._remove_main_command(self.bot._resolve_command(alias))
                self.bot.commands[alias.lower()] = adapter
                if compact:
                    self.bot.commands[compact] = adapter

    def _remove_main_command(self, command):
        if command is None or getattr(getattr(command, "func", None), "__module__", None) == __name__:
            return
        for key, registered in tuple(self.bot.commands.items()):
            if registered is command:
                del self.bot.commands[key]

    def _make_handler(self, cog_command):
        def invoke(ctx, args):
            content = str(ctx.get("content") or "")
            if not content:
                content = f"{self.bot.prefix}{cog_command.name} {' '.join(args)}".strip()
            author_id = str(ctx.get("author_id") or "")
            message = SimpleNamespace(
                id=ctx.get("message_id"),
                channel_id=ctx.get("channel_id"),
                guild=SimpleNamespace(id=ctx.get("guild_id")) if ctx.get("guild_id") else None,
                author=SimpleNamespace(id=int(author_id)) if author_id.isdigit() else SimpleNamespace(id=author_id),
                content=content,
                delete=self._ignore_command_delete,
                reply=self._make_reply(ctx.get("channel_id")),
            )
            context = SimpleNamespace(
                message=message,
                command=cog_command,
                args=list(args),
                kwargs={},
                bot=self.facade,
                channel_id=str(ctx.get("channel_id") or ""),
                guild_id=str(ctx.get("guild_id") or ""),
                author=message.author,
                send=self._make_send(ctx.get("channel_id")),
            )
            future = asyncio.run_coroutine_threadsafe(cog_command.invoke(context), self.loop)
            return future.result()
        return invoke

    @staticmethod
    async def _ignore_command_delete():
        # main.py already deletes controller command messages before dispatch.
        return None

    def _make_send(self, channel_id):
        async def send(content=None, **kwargs):
            return await asyncio.to_thread(
                self.bot.api.send_message,
                str(channel_id or ""),
                str(content or ""),
                reply_to=kwargs.get("reply_to"),
                tts=kwargs.get("tts", False),
            )
        return send

    def _make_reply(self, channel_id):
        async def reply(content=None, **kwargs):
            return await self._make_send(channel_id)(content, **kwargs)
        return reply

    async def _dispatch(self, event, data=None):
        errors = []
        for callback in tuple(self.facade._listeners.get(str(event).upper(), ())):
            try:
                await callback(data) if data is not None else await callback()
            except Exception as exc:
                errors.append(f"{callback.__qualname__}: {exc}")
        if errors:
            raise RuntimeError("; ".join(errors))

    def dispatch(self, event, data=None, *, wait=False):
        if self.loop.is_closed() or not self.loop.is_running():
            return None
        future = asyncio.run_coroutine_threadsafe(self._dispatch(event, data), self.loop)
        if wait:
            return future.result()

        def report_error(done):
            try:
                done.result()
            except Exception:
                _LOGGER.exception("Cog listener failed for %s", event)

        future.add_done_callback(report_error)
        return future

    def shutdown(self):
        if not self.loop.is_running():
            return

        async def stop_cogs():
            for cog in self.cogs:
                stop = getattr(cog, "stop", None)
                if callable(stop):
                    try:
                        stop()
                    except Exception:
                        _LOGGER.exception("Failed stopping cog %s", cog.name)
            tasks = [
                task for task in asyncio.all_tasks(self.loop)
                if task is not asyncio.current_task(self.loop)
            ]
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        future = asyncio.run_coroutine_threadsafe(stop_cogs(), self.loop)
        try:
            future.result(timeout=5)
        except Exception:
            _LOGGER.exception("Failed to stop main cog runtime cleanly")
        self.loop.call_soon_threadsafe(self.loop.stop)
        if threading.current_thread() is not self._thread:
            self._thread.join(timeout=5)


def install_cog_commands(bot):
    """Register every aria_backend cog command over any duplicate main.py handler."""
    runtime = MainCogRuntime(bot)
    bot._cog_runtime = runtime
    _LOGGER.info(
        "Registered %d aria_backend cog command names and aliases across %d cogs",
        len(runtime.commands),
        len(runtime.cogs),
    )
    return runtime


def merge_cog_help_pages(help_pages, help_catalog, runtime, category_targets):
    """Replace static help entries for registered cog commands with cog metadata."""
    command_by_key = runtime.commands

    def command_key(value):
        tokens = str(value or "").strip().split()
        if not tokens:
            return ""
        return tokens[0].lstrip(runtime.bot.prefix).casefold()

    command_help = {}
    metadata = {}
    for backend_category, category in category_targets.items():
        catalog_page = help_catalog.get(backend_category) or {}
        for name, usage, description in catalog_page.get("cmds", []):
            command = command_by_key.get(str(name).strip().casefold())
            if command is None:
                continue

            canonical = str(command.name).casefold()
            usage_tokens = str(usage or canonical).strip().split()
            rendered_usage = canonical
            if len(usage_tokens) > 1:
                rendered_usage += " " + " ".join(usage_tokens[1:])
            entry = {
                "usage": rendered_usage,
                "description": str(description),
                "category": category,
            }
            metadata[canonical] = entry
            command_help[canonical] = entry
            for alias in (canonical, *getattr(command, "aliases", ())):
                command_help[str(alias).casefold()] = entry

    for command in runtime.facade._commands:
        canonical = str(command.name).casefold()
        if canonical in metadata:
            continue
        usage = canonical
        description = str(
            getattr(command, "brief", "")
            or getattr(command, "help", "")
            or "Cog command."
        ).strip()
        entry = {
            "usage": usage,
            "description": description,
            "category": "general",
        }
        metadata[canonical] = entry
        command_help[canonical] = entry
        for alias in (canonical, *getattr(command, "aliases", ())):
            command_help[str(alias).casefold()] = entry

    seen = set()
    for page_key, page in help_pages.items():
        if not isinstance(page, dict):
            continue
        updated_lines = []
        for line in page.get("lines", []):
            if not (isinstance(line, tuple) and len(line) == 2):
                updated_lines.append(line)
                continue
            command = command_by_key.get(command_key(line[0]))
            if command is None:
                updated_lines.append(line)
                continue
            canonical = str(command.name).casefold()
            if canonical in seen:
                continue
            seen.add(canonical)
            entry = metadata[canonical]
            entry["category"] = page_key
            updated_lines.append((entry["usage"], entry["description"]))
        page["lines"] = updated_lines

    for command in runtime.facade._commands:
        canonical = str(command.name).casefold()
        if canonical in seen:
            continue
        entry = metadata[canonical]
        target_category = entry["category"]
        target_page = help_pages.setdefault(
            target_category,
            {"title": f"Help: {target_category}", "lines": []},
        )
        target_page["lines"].append((entry["usage"], entry["description"]))
        seen.add(canonical)

    seen_help_commands = set()
    for page in help_pages.values():
        if not isinstance(page, dict):
            continue
        unique_lines = []
        for line in page.get("lines", []):
            if not (isinstance(line, tuple) and len(line) == 2):
                unique_lines.append(line)
                continue
            key = command_key(line[0])
            command = command_by_key.get(key) or runtime.bot._resolve_command(key)
            if command is None:
                unique_lines.append(line)
                continue
            canonical = str(command.name).casefold()
            if canonical in seen_help_commands:
                continue
            seen_help_commands.add(canonical)
            unique_lines.append(line)
        page["lines"] = unique_lines

    return command_help
