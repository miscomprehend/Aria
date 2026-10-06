"""
voice.py — Discord voice channel join/leave for user tokens.

Uses the existing bot.ws (websocket-client) gateway connection to send op 4
(Voice State Update) instead of opening a second gateway, which would kick
the main bot off Discord.  bot.py must forward VOICE_STATE_UPDATE and
VOICE_SERVER_UPDATE events via VoiceClient.on_voice_state_update() /
VoiceClient.on_voice_server_update().
"""

import json
import asyncio
import socket
import struct
import time
import threading
import random
import logging
from typing import Optional, Dict
from discord_api_types import GatewayOpcodes, VoiceOpcodes

try:
    import websockets
    from websockets.exceptions import ConnectionClosed
except ImportError:
    websockets = None
    ConnectionClosed = Exception

_VOICE_WS_VERSION = 4
logger = logging.getLogger(__name__)


class VoiceClient:
    """Manages a single voice channel connection."""

    def __init__(self, bot_ws, user_id: str):
        # bot_ws is the websocket.WebSocketApp from bot.py
        self.bot_ws = bot_ws
        self.user_id = str(user_id)

        self.voice_ws = None
        self.voice_thread: Optional[threading.Thread] = None
        self.voice_loop: Optional[asyncio.AbstractEventLoop] = None
        self._voice_tasks = set()
        self.running = False
        self.gateway_joined = False

        self.guild_id: Optional[str] = None
        self.channel_id: Optional[str] = None
        self.is_dm_call = False
        self.call_channel_id: Optional[str] = None
        self.channel_type: Optional[int] = None

        # Populated by gateway events forwarded from bot.py
        self.session_id: Optional[str] = None
        self.voice_token: Optional[str] = None
        self.endpoint: Optional[str] = None

        self.ssrc: Optional[int] = None
        self.secret_key = None
        self.encryption_mode: Optional[str] = None

        # Threading events so connect() can block until gateway data arrives
        self._session_event = threading.Event()
        self._server_event = threading.Event()
        self._connected_event = threading.Event()
        self._ws_error: str = ""
        self._voice_unsupported = False

        # Local state toggles reflected via gateway op4 / voice ws operations.
        self.self_mute = False
        self.self_deaf = False
        self.self_video = False
        self.self_stream = False

    def _send_gateway_payload(self, payload: dict) -> bool:
        try:
            self.bot_ws.send(json.dumps(payload))
            return True
        except Exception as e:
            self._ws_error = str(e)
            logger.error("[Voice] Failed to send gateway payload: %s", e)
            return False
    
    # ── called by bot.on_message to deliver gateway voice events ────────────

    def _matches_current_voice_session(self, data: dict) -> bool:
        """Accept updates that match the active user or the channel currently being joined."""
        if not isinstance(data, dict):
            return False

        user_id = data.get("user_id")
        if user_id is not None:
            return bool(self.user_id and str(user_id) == str(self.user_id))

        channel_id = data.get("channel_id")
        if self.channel_id and channel_id is not None and str(channel_id) == str(self.channel_id):
            return True

        guild_id = data.get("guild_id")
        if self.guild_id and guild_id is not None and str(guild_id) == str(self.guild_id):
            return True

        return False

    def on_voice_state_update(self, data: dict):
        """Forward VOICE_STATE_UPDATE from the main gateway."""
        if not self._matches_current_voice_session(data):
            return
        self.session_id = data.get("session_id")
        if self.session_id:
            self._session_event.set()

    def on_voice_server_update(self, data: dict):
        """Forward VOICE_SERVER_UPDATE from the main gateway."""
        if not isinstance(data, dict):
            return
        guild_matches = self.guild_id and str(data.get("guild_id") or "") == str(self.guild_id)
        channel_matches = self.channel_id and str(data.get("channel_id") or "") == str(self.channel_id)
        if not (guild_matches or channel_matches):
            return

        endpoint = (data.get("endpoint") or "").replace(":443", "")
        token = data.get("token")
        if endpoint and token:
            self.endpoint = endpoint
            self.voice_token = token
            self._server_event.set()

    # ── connect / disconnect ─────────────────────────────────────────────

    def connect(self, channel_id: str, guild_id, is_dm: bool = False, channel_type: Optional[int] = None) -> bool:
        if websockets is None:
            self._ws_error = "Voice support requires the optional 'websockets' dependency"
            logger.warning("[Voice] %s", self._ws_error)
            return False

        self.channel_id = str(channel_id)
        self.guild_id = str(guild_id) if guild_id else None
        self.is_dm_call = is_dm
        self.channel_type = int(channel_type) if channel_type is not None else None
        self.call_channel_id = str(channel_id) if is_dm else None
        self.session_id = None
        self.voice_token = None
        self.endpoint = None
        self.ssrc = None
        self.secret_key = None

        self._session_event.clear()
        self._server_event.clear()
        self._connected_event.clear()
        self._ws_error = ""
        self._voice_unsupported = False

        # Send Voice State Update (op 4) through the existing bot gateway
        payload = json.dumps({
            "op": GatewayOpcodes.VoiceStateUpdate,
            "d": {
                "guild_id": self.guild_id,
                "channel_id": self.channel_id,
                "self_mute": False,
                "self_deaf": False,
                "self_video": False,
                "self_stream": False,
            },
        })
        try:
            self.bot_ws.send(payload)
            self.gateway_joined = True
        except Exception as e:
            logger.error("[Voice] Failed to send op4: %s", e)
            return False

        # Wait for session_id and endpoint from gateway events (up to 10 s each)
        if not self._session_event.wait(timeout=10) or not self.gateway_joined:
            if not self.gateway_joined:
                self._ws_error = "Voice join was cancelled"
                return False
            self._ws_error = "Timeout waiting for VOICE_STATE_UPDATE"
            logger.warning("[Voice] Timeout waiting for session_id (VOICE_STATE_UPDATE)")
            return False
        if not self._server_event.wait(timeout=10) or not self.gateway_joined:
            if not self.gateway_joined:
                self._ws_error = "Voice join was cancelled"
                return False
            self._ws_error = "Timeout waiting for VOICE_SERVER_UPDATE"
            logger.warning("[Voice] Timeout waiting for voice server (VOICE_SERVER_UPDATE)")
            return False
        if not self.gateway_joined:
            self._ws_error = "Voice join was cancelled"
            return False

        # Spawn voice WS thread
        self.running = True
        self.voice_thread = threading.Thread(target=self._run_voice_ws, daemon=True, name="VoiceWS")
        self.voice_thread.start()

        # Give the WS a chance to reach session description (op4), but don't fail
        # plain channel join if the voice WS is delayed.
        self._connected_event.wait(timeout=8)
        # The account is already in the channel via the main gateway (op 4). A media
        # WS failure (e.g. DAVE required) only means no audio, so keep the join.
        return True

    def disconnect(self) -> bool:
        self.running = False

        # Tell Discord we're leaving by sending op4 with channel_id=null
        try:
            payload = json.dumps({
                "op": GatewayOpcodes.VoiceStateUpdate,
                "d": {
                    "guild_id": self.guild_id,
                    "channel_id": None,
                    "self_mute": False,
                    "self_deaf": False,
                    "self_stream": False,
                },
            })
            self.bot_ws.send(payload)
        except Exception:
            pass
        finally:
            self.gateway_joined = False
            self._session_event.set()
            self._server_event.set()

        # Close voice WS from within its own loop
        if self.voice_loop and not self.voice_loop.is_closed() and self.voice_ws:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._close_ws(), self.voice_loop
                ).result(timeout=5)
            except Exception as e:
                logger.warning("[Voice] Error closing voice WebSocket: %s", e)

        if self.voice_thread and self.voice_thread.is_alive():
            try:
                self.voice_thread.join(timeout=8)
                if self.voice_thread.is_alive():
                    logger.warning("[Voice] Voice WebSocket thread did not stop within 8 seconds")
            except RuntimeError as e:
                logger.warning("[Voice] Could not join voice WebSocket thread: %s", e)

        logger.info("[Voice] Disconnected from channel %s", self.channel_id)
        return True

    def ws_ready(self) -> bool:
        return bool(self._connected_event.is_set() and self.voice_ws is not None)

    async def _close_ws(self):
        ws = self.voice_ws
        if ws:
            try:
                await ws.close()
                wait_closed = getattr(ws, "wait_closed", None)
                if callable(wait_closed):
                    await wait_closed()
            except Exception as e:
                logger.debug("[Voice] WebSocket close completed with error: %s", e)
            finally:
                if self.voice_ws is ws:
                    self.voice_ws = None

    # ── voice WebSocket thread ───────────────────────────────────────────

    def _run_voice_ws(self):
        self.voice_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.voice_loop)
        backoff = 2
        try:
            while self.running:
                try:
                    self.voice_loop.run_until_complete(self._voice_ws_connect())
                except Exception as e:
                    logger.error("[Voice] WS thread error: %s", e)
                    self._ws_error = str(e)
                if self._voice_unsupported:
                    # Gateway voice state remains available when media transport is unsupported.
                    break
                if not self.running:
                    break
                logger.warning("[Voice] Reconnecting in %ss", backoff)
                for _ in range(backoff):
                    if not self.running:
                        break
                    time.sleep(1)
                backoff = min(backoff * 2, 60)
        finally:
            try:
                self.voice_loop.run_until_complete(self._cancel_voice_tasks())
                self.voice_loop.run_until_complete(self.voice_loop.shutdown_asyncgens())
            except Exception as e:
                logger.warning("[Voice] Voice loop cleanup failed: %s", e)
            try:
                self.voice_loop.close()
            except Exception as e:
                logger.warning("[Voice] Could not close voice event loop: %s", e)
            self.voice_loop = None
            self.running = False

    def _start_voice_task(self, coroutine, name):
        task = asyncio.create_task(coroutine, name=name)
        self._voice_tasks.add(task)
        task.add_done_callback(self._voice_tasks.discard)
        return task

    async def _cancel_voice_tasks(self):
        current = asyncio.current_task()
        tasks = [
            task for task in self._voice_tasks
            if task is not current and not task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _voice_ws_connect(self):
        url = f"wss://{self.endpoint}/?v={_VOICE_WS_VERSION}"
        logger.info("[Voice] Connecting to voice server: %s", url)
        try:
            async with websockets.connect(
                url,
                max_size=None,
                open_timeout=5,
                close_timeout=2,
            ) as ws:
                self.voice_ws = ws
                self._ws_error = ""

                # Send Identify (op 0)
                await ws.send(json.dumps({
                    "op": VoiceOpcodes.Identify,
                    "d": {
                        "server_id": self.guild_id or self.channel_id,
                        "user_id": self.user_id,
                        "session_id": self.session_id,
                        "token": self.voice_token,
                    },
                }))

                async for raw in ws:
                    if not self.running:
                        break
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    await self._handle_voice_op(ws, msg)
        except ConnectionClosed as e:
            code = getattr(e, "code", None)
            reason = str(getattr(e, "reason", "") or "")
            if code == 4017 or "E2EE/DAVE protocol required" in reason:
                self._voice_unsupported = True
                self._ws_error = "Voice server requires E2EE/DAVE, which Aria voice does not support yet."
                logger.warning("[Voice] %s", self._ws_error)
            else:
                logger.error("[Voice] WS error: %s", e)
                self._ws_error = str(e)
        except Exception as e:
            logger.error("[Voice] WS error: %s", e)
            self._ws_error = str(e)
        finally:
            await self._cancel_voice_tasks()
            self.voice_ws = None
            self._connected_event.clear()

    async def _handle_voice_op(self, ws, msg: dict):
        op = msg.get("op")

        if op == VoiceOpcodes.Hello:
            # Hello — start heartbeat
            interval = msg["d"]["heartbeat_interval"] / 1000
            self._start_voice_task(self._heartbeat(ws, interval), "voice-heartbeat")

        elif op == VoiceOpcodes.Ready:
            # Voice Ready — do UDP IP discovery then select protocol
            d = msg["d"]
            self.ssrc = d["ssrc"]
            udp_ip = d["ip"]
            udp_port = d["port"]
            self.encryption_mode = self._select_encryption_mode(d.get("modes"))
            logger.info("[Voice] Voice ready with SSRC %s", self.ssrc)
            # Ensure ssrc is always int for run_in_executor
            ssrc_int = int(self.ssrc) if self.ssrc is not None else 0
            ext_ip, ext_port = await asyncio.get_event_loop().run_in_executor(
                None, self._ip_discovery, udp_ip, udp_port, ssrc_int
            )
            await ws.send(json.dumps({
                "op": VoiceOpcodes.SelectProtocol,
                "d": {
                    "protocol": "udp",
                    "data": {
                        "address": ext_ip,
                        "port": ext_port,
                        "mode": self.encryption_mode,
                    },
                },
            }))

        elif op == VoiceOpcodes.SessionDescription:
            # Session Description — we're fully connected
            self.secret_key = msg["d"].get("secret_key")
            mode = str(msg["d"].get("mode") or "").strip()
            if mode:
                self.encryption_mode = mode
            logger.info("[Voice] Connected to voice session")
            self._connected_event.set()
            # Mark as not-speaking (silent join)
            await ws.send(json.dumps({
                "op": VoiceOpcodes.Speaking,
                "d": {"speaking": 0, "delay": 0, "ssrc": self.ssrc},
            }))
            # Start silence keepalive so Discord doesn't evict the idle connection
            self._start_voice_task(
                self._silence_keepalive(ws),
                "voice-silence-keepalive",
            )

        elif op == VoiceOpcodes.Resumed:
            logger.info("[Voice] Session resumed")

        elif op == VoiceOpcodes.SecureFramesPrepareProtocolTransition:
            data = msg.get("d") if isinstance(msg.get("d"), dict) else {}
            if isinstance(data, dict) and data.get("protocol"):
                self.encryption_mode = str(data.get("protocol"))
            await ws.send(json.dumps({
                "op": VoiceOpcodes.SecureFramesExecuteTransition,
                "d": data or {},
            }))
            logger.info("[Voice] Acknowledged secure-frames protocol transition")

    @staticmethod
    def _select_encryption_mode(server_modes) -> str:
        """Pick the best supported voice encryption mode from server-advertised modes."""
        preferred = (
            "aead_aes256_gcm_rtpsize",
            "aead_xchacha20_poly1305_rtpsize",
            "xsalsa20_poly1305_lite_rtpsize",
            "xsalsa20_poly1305_suffix",
            "xsalsa20_poly1305",
        )
        if isinstance(server_modes, list):
            modes = [str(mode) for mode in server_modes if isinstance(mode, str)]
            for mode in preferred:
                if mode in modes:
                    return mode
            if modes:
                return modes[0]
        return "xsalsa20_poly1305"

    async def _silence_keepalive(self, ws, interval: float = 30.0):
        """Re-send speaking=0 every `interval` seconds to prevent idle disconnect."""
        while self.running:
            await asyncio.sleep(interval)
            if not self.running:
                break
            try:
                await ws.send(json.dumps({
                    "op": VoiceOpcodes.Speaking,
                    "d": {"speaking": 0, "delay": 0, "ssrc": self.ssrc},
                }))
            except Exception:
                break

    async def _heartbeat(self, ws, interval: float):
        while self.running:
            try:
                nonce = random.randint(1, 2 ** 32)
                await ws.send(json.dumps({"op": VoiceOpcodes.Heartbeat, "d": nonce}))
                await asyncio.sleep(interval)
            except Exception:
                break

    # ── UDP IP discovery ─────────────────────────────────────────────────

    def _ip_discovery(self, server_ip: str, server_port: int, ssrc: int):
        """
        Discord voice UDP IP discovery (v2 format, 74-byte packets).
        Sends: type=0x1 (2B), length=70 (2B), ssrc (4B), 66 null bytes.
        Response: type=0x2 (2B), length (2B), ssrc (4B), ip (64B null-term), port (2B LE).
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            request = struct.pack(">HHI", 0x1, 70, ssrc) + b"\x00" * 66
            sock.sendto(request, (server_ip, server_port))
            data, _ = sock.recvfrom(74)
            sock.close()
            ip_end = data.index(b"\x00", 8)
            ext_ip = data[8:ip_end].decode("utf-8")
            ext_port = struct.unpack_from("<H", data, 72)[0]
            logger.debug("[Voice] External address: %s:%s", ext_ip, ext_port)
            return ext_ip, ext_port
        except Exception as e:
            logger.warning("[Voice] IP discovery failed (%s), using fallback 0.0.0.0:0", e)
            return "0.0.0.0", 0


class SimpleVoice:
    """High-level voice manager used by main.py commands."""

    def __init__(self, api_client, token, bot=None):
        self.api = api_client
        self.token = token
        self.bot = bot
        self.active_connections: Dict[str, VoiceClient] = {}
        self.last_error: str = ""

    def _is_client_alive(self, client: Optional[VoiceClient]) -> bool:
        return bool(client and client.gateway_joined)

    def _cleanup_dead_connections(self) -> None:
        stale = []
        for key, client in self.active_connections.items():
            if not self._is_client_alive(client):
                stale.append(key)
        for key in stale:
            self.active_connections.pop(key, None)

    def _get_client(self, channel_id=None) -> Optional[VoiceClient]:
        self._cleanup_dead_connections()
        if channel_id:
            return self.active_connections.get(f"channel_{channel_id}")
        if self.active_connections:
            return next(iter(self.active_connections.values()))
        return None

    def _send_voice_state_update(self, client: VoiceClient) -> bool:
        try:
            payload = {
                "op": GatewayOpcodes.VoiceStateUpdate,
                "d": {
                    "guild_id": client.guild_id,
                    "channel_id": client.channel_id,
                    "self_mute": bool(client.self_mute),
                    "self_deaf": bool(client.self_deaf),
                    "self_video": bool(client.self_video),
                    "self_stream": bool(client.self_stream),
                },
            }
            return client._send_gateway_payload(payload)
        except Exception as e:
            self.last_error = str(e)
            logger.error("[Voice] Failed to update voice state: %s", e)
            return False

    def join_vc(self, *args, **kwargs) -> bool:
        self.last_error = ""
        channel_id = None
        if args and isinstance(args[0], str) and args[0].isdigit():
            channel_id = args[0]
        elif kwargs.get("channel_id"):
            channel_id = str(kwargs["channel_id"])

        if not channel_id:
            self.last_error = "Missing channel ID"
            return False

        if not self.bot or not self.bot.ws:
            logger.warning("[Voice] Bot gateway not ready")
            self.last_error = "Bot gateway not ready"
            return False

        # Already connected to this channel and alive.
        existing = self.active_connections.get(f"channel_{channel_id}")
        if self._is_client_alive(existing):
            return True

        # Fetch channel info to determine guild_id / type
        guild_id = None
        channel_type = None
        is_dm = False
        try:
            resp = self.api.request("GET", f"/channels/{channel_id}")
            if resp and resp.status_code == 200:
                d = resp.json()
                ctype = d.get("type", 0)
                channel_type = int(ctype) if isinstance(ctype, int) else None
                if ctype in (2, 13):    # Guild voice / stage channels
                    guild_id = d.get("guild_id")
                elif ctype in (1, 3):   # DM / group DM call
                    is_dm = True
                else:
                    logger.warning("[Voice] Channel type %s is not a voice channel", ctype)
                    self.last_error = f"Channel type {ctype} is not voice"
                    return False
        except Exception as e:
            logger.error("[Voice] Could not fetch channel info: %s", e)
            self.last_error = f"Could not fetch channel info: {str(e)[:80]}"
            return False

        # Leave any current connection first
        if self.active_connections:
            self.leave_vc()

        user_id = (
            getattr(self.api, "user_id", None)
            or getattr(self.bot, "user_id", None)
            or "0"
        )
        client = VoiceClient(self.bot.ws, user_id)

        # Register so bot.py can forward voice events to us
        if self.bot is not None:
            self.bot._voice_client = client

        key = f"channel_{channel_id}"
        # Keep the gateway membership addressable while connect waits for voice events.
        self.active_connections[key] = client
        try:
            success = client.connect(channel_id, guild_id, is_dm, channel_type)
        except TypeError:
            # Backward-compatibility for tests or legacy client shims.
            success = client.connect(channel_id, guild_id, is_dm)
        if not success:
            self.last_error = client._ws_error or "Voice gateway handshake failed"
            if not client.gateway_joined:
                self.active_connections.pop(key, None)
            if not client.gateway_joined and self.bot is not None and getattr(self.bot, "_voice_client", None) is client:
                self.bot._voice_client = None
        return success

    def leave_vc(self, *args, **kwargs) -> bool:
        self.last_error = ""
        channel_id = None
        if args and isinstance(args[0], str) and args[0].isdigit():
            channel_id = args[0]
        elif kwargs.get("channel_id"):
            channel_id = str(kwargs["channel_id"])

        if channel_id:
            key = f"channel_{channel_id}"
            client = self.active_connections.pop(key, None)
            if client:
                client.disconnect()
                if getattr(self.bot, "_voice_client", None) is client:
                    self.bot._voice_client = None
                return True
            return False

        if not self.active_connections:
            return False
        for client in list(self.active_connections.values()):
            client.disconnect()
        self.active_connections.clear()
        if self.bot:
            self.bot._voice_client = None
        return True

    def is_in_voice(self, *args, **kwargs) -> bool:
        self._cleanup_dead_connections()
        channel_id = None
        if args and isinstance(args[0], str) and args[0].isdigit():
            channel_id = args[0]
        elif kwargs.get("channel_id"):
            channel_id = str(kwargs["channel_id"])
        if channel_id:
            return f"channel_{channel_id}" in self.active_connections
        return len(self.active_connections) > 0

    def set_video(self, channel_id=None, enabled=True):
        """Toggle camera via gateway op4."""
        client = self._get_client(channel_id)
        if not client:
            self.last_error = "Not in a voice channel"
            return False, "Not in a voice channel"
        if client.channel_type == 13 and enabled:
            self.last_error = "Camera is not supported in stage channels"
            return False, self.last_error
        try:
            client.self_video = bool(enabled)
            if not self._send_voice_state_update(client):
                return False, self.last_error or "Failed to send voice state update"
            return True, "Camera " + ("enabled" if enabled else "disabled")
        except Exception as e:
            self.last_error = str(e)
            return False, str(e)

    def set_stream(self, channel_id=None, enabled=True):
        """Toggle Go Live / screen share via the main Discord gateway."""
        client = self._get_client(channel_id)
        if not client:
            self.last_error = "Not in a voice channel"
            return False, "Not in a voice channel"
        if client.channel_type == 13:
            self.last_error = "Go Live is not supported in stage channels"
            return False, self.last_error
        is_call = bool(client.is_dm_call or not client.guild_id)
        try:
            if is_call:
                stream_key = f"call:{client.channel_id}:{client.user_id}"
            else:
                stream_key = f"guild:{client.guild_id}:{client.channel_id}:{client.user_id}"
            client.self_stream = bool(enabled)
            if not self._send_voice_state_update(client):
                detail = self.last_error or "Failed to send voice state update"
                self.last_error = detail
                return False, detail

            if enabled:
                op_payload = {
                    "op": GatewayOpcodes.StreamCreate,
                    "d": {
                        "type": "call" if is_call else "guild",
                        "guild_id": None if is_call else client.guild_id,
                        "channel_id": client.channel_id,
                        "preferred_region": None,
                    },
                }
                if not client._send_gateway_payload(op_payload):
                    detail = client._ws_error or "Failed to send stream create payload"
                    self.last_error = detail
                    return False, detail

                unpause_payload = {
                    "op": GatewayOpcodes.StreamSetPaused,
                    "d": {
                        "stream_key": stream_key,
                        "paused": False,
                    },
                }
                if not client._send_gateway_payload(unpause_payload):
                    detail = client._ws_error or "Failed to send stream unpause payload"
                    self.last_error = detail
                    return False, detail
            else:
                pause_payload = {
                    "op": GatewayOpcodes.StreamSetPaused,
                    "d": {
                        "stream_key": stream_key,
                        "paused": True,
                    },
                }
                if not client._send_gateway_payload(pause_payload):
                    detail = client._ws_error or "Failed to send stream pause payload"
                    self.last_error = detail
                    return False, detail

                delete_payload = {
                    "op": GatewayOpcodes.StreamDelete,
                    "d": {
                        "stream_key": stream_key,
                    },
                }
                if not client._send_gateway_payload(delete_payload):
                    detail = client._ws_error or "Failed to send stream delete payload"
                    self.last_error = detail
                    return False, detail

            if enabled and not client.ws_ready():
                return True, "Stream requested; voice transport is still starting"
            return True, "Stream " + ("started" if enabled else "stopped")
        except Exception as e:
            self.last_error = str(e)
            logger.error("[Voice] Failed to toggle stream: %s", e)
            return False, str(e)

    def set_mute_deaf(self, channel_id=None, mute=None, deaf=None):
        client = self._get_client(channel_id)
        if not client:
            self.last_error = "Not in a voice channel"
            return False, "Not in a voice channel"
        if mute is not None:
            client.self_mute = bool(mute)
        if deaf is not None:
            client.self_deaf = bool(deaf)
        if not self._send_voice_state_update(client):
            return False, self.last_error or "Failed to update voice state"

        parts = []
        if mute is not None:
            parts.append("mute " + ("on" if client.self_mute else "off"))
        if deaf is not None:
            parts.append("deaf " + ("on" if client.self_deaf else "off"))
        return True, ", ".join(parts) if parts else "updated"

    def switch_channel(self, channel_id: str):
        return self.join_vc(channel_id)

    def rejoin(self):
        ch = self.current_channel_id()
        if not ch:
            self.last_error = "Not in a voice channel"
            return False
        self.leave_vc()
        time.sleep(0.6)
        return self.join_vc(ch)

    def get_state(self, channel_id=None) -> dict:
        client = self._get_client(channel_id)
        if not client:
            return {
                "connected": False,
                "channel_id": None,
                "camera": False,
                "stream": False,
                "mute": False,
                "deaf": False,
                "ws_ready": False,
                "last_error": self.last_error,
            }
        return {
            "connected": True,
            "channel_id": str(client.channel_id or ""),
            "channel_type": client.channel_type,
            "dm_call": bool(client.is_dm_call),
            "camera": bool(client.self_video),
            "stream": bool(client.self_stream),
            "mute": bool(client.self_mute),
            "deaf": bool(client.self_deaf),
            "ws_ready": bool(client.ws_ready()),
            "last_error": self.last_error or getattr(client, "_ws_error", ""),
        }

    def current_channel_id(self) -> Optional[str]:
        client = self._get_client()
        return str(client.channel_id) if client and client.channel_id else None
