import os
import sys
import threading
import unittest
import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(__file__))

from bot import DiscordBot
from async_gateway import AsyncDiscordGateway
from core.client.platform import CLIENT_PROFILES, build_identify_payload
from voice import SimpleVoice, VoiceClient
from discord_api_types import VoiceOpcodes


def make_bot():
    bot = object.__new__(DiscordBot)
    defaults = {
        "running": True,
        "connection_active": False,
        "identified": False,
        "_connection_lock": threading.Lock(),
        "_connecting": False,
        "_reconnect_guard": threading.Lock(),
        "_reconnect_signal": threading.Event(),
        "_reconnect_stop": threading.Event(),
        "_reconnect_thread": None,
        "_last_connection_attempt": 0.0,
        "_consecutive_failures": 0,
        "_max_consecutive_failures": 15,
        "_connection_quality_score": 100,
        "_network_stability_score": 100,
        "_connection_start_time": 0.0,
        "_reconnect_ready_timeout": 0.04,
        "_reconnect_backoff_base": 0.01,
        "use_async_gateway": False,
        "_async_gateway_bridge_active": False,
        "gateway_bridge": None,
        "_gateway_latency_samples": [],
        "_heartbeat_sent_at": None,
        "_last_ack_at": None,
        "last_heartbeat": 0.0,
        "gateway_latency_ms": None,
        "_last_successful_heartbeat": 0.0,
    }
    for name, value in defaults.items():
        setattr(bot, name, value)
    return bot


class GatewayLifecycleTests(unittest.TestCase):
    def test_message_create_does_not_wait_for_blocking_handler(self):
        bot = make_bot()
        bot._message_executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="GatewayMessageTest",
        )
        bot._message_slots = threading.BoundedSemaphore(100)
        bot.giveaway_sniper = Mock()
        bot.nitro_sniper = Mock()
        bot._msg_cache = {}
        handler_started = threading.Event()
        release_handler = threading.Event()
        bot._handle_message = lambda _message: (
            handler_started.set(),
            release_handler.wait(1),
        )
        self.addCleanup(bot._message_executor.shutdown, wait=True)
        self.addCleanup(release_handler.set)

        bot.on_message(
            None,
            json.dumps({"op": 0, "t": "MESSAGE_CREATE", "d": {"id": "1"}}),
        )

        self.assertTrue(handler_started.wait(1))
        self.assertFalse(release_handler.is_set())

    def test_group_chat_recipient_event_dispatches_to_security_manager(self):
        bot = make_bot()
        bot.user_id = "123"
        dispatched = threading.Event()
        received = []

        class GroupChatManager:
            def on_channel_recipient_add(self, event, current_user_id):
                received.append((event, current_user_id))
                dispatched.set()

        bot.group_chat_tools = GroupChatManager()
        event = {"channel_id": "42", "user": {"id": "456"}}
        bot._handle_group_chat_recipient_event("on_channel_recipient_add", event)

        self.assertTrue(dispatched.wait(1))
        self.assertEqual(received, [(event, "123")])

    def test_coalesces_triggers_and_retries_until_ready(self):
        bot = make_bot()
        first_attempt = threading.Event()
        attempts = []
        attempts_lock = threading.Lock()

        def connect():
            with attempts_lock:
                attempts.append(len(attempts) + 1)
                attempt_number = len(attempts)
            if attempt_number == 1:
                first_attempt.set()
                return
            bot.connection_active = True
            bot.identified = True

        bot._connect_gateway = connect
        self.assertTrue(bot._schedule_reconnect("socket close"))
        self.assertTrue(first_attempt.wait(1))
        self.assertFalse(bot._schedule_reconnect("socket error"))

        worker = bot._reconnect_thread
        worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(attempts, [1, 2])
        self.assertTrue(bot.connection_active)
        self.assertTrue(bot.identified)

    def test_stop_cancels_backoff(self):
        bot = make_bot()
        bot._reconnect_backoff_base = 10
        attempted = threading.Event()
        calls = []

        def fail_connect():
            calls.append(1)
            attempted.set()
            raise OSError("offline")

        bot._connect_gateway = fail_connect
        bot._schedule_reconnect("startup")
        self.assertTrue(attempted.wait(1))
        bot._reconnect_stop.set()

        worker = bot._reconnect_thread
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(len(calls), 1)

    def test_stop_closes_async_bridge_once(self):
        class Bridge:
            def __init__(self):
                self.stop_calls = 0
                self.close_calls = 0

            def stop(self):
                self.stop_calls += 1

            def close(self):
                self.close_calls += 1

        bot = make_bot()
        bridge = Bridge()
        bot.use_async_gateway = True
        bot.gateway_bridge = bridge
        bot.ws = bridge

        bot.stop()

        self.assertEqual(bridge.stop_calls, 1)
        self.assertEqual(bridge.close_calls, 0)

    def test_async_identify_uses_vr_profile(self):
        class Socket:
            def __init__(self):
                self.payload = None

            async def send(self, payload):
                self.payload = json.loads(payload)

        gateway = AsyncDiscordGateway("test-token", client_type="vr", compress=False)
        gateway.ws = Socket()
        asyncio.run(gateway._identify())

        payload = gateway.ws.payload
        self.assertEqual(payload["d"]["properties"], CLIENT_PROFILES["vr"])
        self.assertEqual(payload["d"]["token"], "test-token")

    def test_identify_payload_preserves_multiple_activities(self):
        activities = [{"type": 0, "name": "Game"}, {"type": 3, "name": "Show"}]
        payload = build_identify_payload("test-token", "web", activity=activities)
        self.assertEqual(payload["d"]["presence"]["activities"], activities)

    def test_set_activities_sends_multiple_activities_and_keeps_legacy_primary(self):
        bot = object.__new__(DiscordBot)
        class Socket:
            def __init__(self):
                self.payload = None
            def send(self, payload):
                self.payload = json.loads(payload)

        bot.ws = Socket()
        bot.identified = True
        bot.connection_active = True
        bot._current_status = "online"
        bot._last_activity_signature = None

        activities = [{"type": 0, "name": "Game"}, {"type": 3, "name": "Show"}]
        bot.set_activities(activities)

        self.assertEqual(bot.activity["name"], "Game")
        self.assertEqual([item["name"] for item in bot.activities], ["Game", "Show"])
        self.assertEqual(bot.ws.payload["d"]["activities"], bot.activities)

    def test_async_bridge_routes_dispatch_through_one_bot_callback(self):
        bot = make_bot()
        bot.config = {"gateway_compress": False}
        bot._client_type = "web"
        bot.token = "test-token"
        bot.can_resume = False
        bot.session_id = None
        bot.gateway_bridge = None
        bot._async_gateway_bridge_active = False

        with patch("gateway_bridge.GatewayBridge") as bridge_type:
            bridge = bridge_type.return_value
            bot._connect_gateway_bridge()

        bridge.on_ready.assert_not_called()
        bridge.on_message.assert_not_called()
        bridge.on_payload.assert_called_once_with(bot._on_bridge_payload)

    def test_async_gateway_reconnect_opcode_closes_socket_and_notifies_owner(self):
        class Socket:
            def __init__(self):
                self.closed = False

            async def close(self):
                self.closed = True

        gateway = AsyncDiscordGateway("test-token", compress=False)
        gateway.ws = Socket()
        gateway.connected = True
        close_events = []
        gateway.on_close = lambda code, reason: close_events.append((code, reason))

        asyncio.run(gateway._handle_message(json.dumps({"op": 7, "d": None})))

        self.assertTrue(gateway.ws.closed)
        self.assertFalse(gateway.connected)
        self.assertEqual(close_events, [(4000, "Gateway requested reconnect")])

    def test_legacy_gateway_answers_server_requested_heartbeat(self):
        class Socket:
            def __init__(self):
                self.sent = []

            def send(self, payload):
                self.sent.append(json.loads(payload))

        bot = make_bot()
        bot.sequence = 123
        bot.ws = Socket()

        bot.on_message(bot.ws, json.dumps({"op": 1, "d": None}))

        self.assertEqual(bot.ws.sent, [{"op": 1, "d": 123}])

    def test_async_gateway_answers_server_requested_heartbeat(self):
        class Socket:
            def __init__(self):
                self.sent = []

            async def send(self, payload):
                self.sent.append(json.loads(payload))

        gateway = AsyncDiscordGateway("test-token", compress=False)
        gateway.ws = Socket()
        gateway.connected = True
        gateway.sequence = 321

        asyncio.run(gateway._handle_message(json.dumps({"op": 1, "d": None})))

        self.assertEqual(gateway.ws.sent, [{"op": 1, "d": 321}])
        self.assertIsNotNone(gateway._heartbeat_pending_since)

    def test_async_heartbeat_ack_refreshes_bot_health_timestamp(self):
        bot = make_bot()
        gateway = SimpleNamespace(_heartbeat_sent_at=time.monotonic() - 0.025)
        bot.gateway_bridge = SimpleNamespace(gateway=gateway)

        bot._on_bridge_payload({"op": 11, "d": None})

        self.assertGreater(bot._last_successful_heartbeat, 0)
        self.assertGreater(bot.gateway_latency_ms, 0)
        self.assertEqual(len(bot._gateway_latency_samples), 1)
        self.assertIsNone(gateway._heartbeat_sent_at)

    def test_async_health_recovery_stops_old_bridge_before_reconnecting(self):
        class Bridge:
            def __init__(self):
                self.stop_calls = 0

            def stop(self):
                self.stop_calls += 1

        bot = make_bot()
        bridge = Bridge()
        bot.use_async_gateway = True
        bot.gateway_bridge = bridge
        bot.ws = bridge
        bot.connection_active = True
        bot.identified = True
        bot._schedule_reconnect = Mock(return_value=True)

        bot._trigger_connection_recovery("stale_heartbeat")

        self.assertEqual(bridge.stop_calls, 1)
        self.assertFalse(bot.connection_active)
        self.assertFalse(bot.identified)
        self.assertFalse(bot._async_gateway_bridge_active)
        bot._schedule_reconnect.assert_called_once_with("health recovery: stale_heartbeat")

    def test_selecting_current_vr_profile_is_a_noop(self):
        bot = object.__new__(DiscordBot)
        bot._client_type = "vr"
        self.assertTrue(bot.set_client_type("vr"))

    def test_voice_client_accepts_state_updates_without_user_id_for_current_channel(self):
        client = VoiceClient(bot_ws=Mock(), user_id="12345")
        client.guild_id = "guild-1"
        client.channel_id = "channel-1"

        client.on_voice_state_update({
            "channel_id": "channel-1",
            "guild_id": "guild-1",
            "session_id": "session-xyz",
        })

        self.assertEqual(client.session_id, "session-xyz")
        self.assertTrue(client._session_event.is_set())

    def test_voice_client_ignores_other_users_state_updates_in_same_guild(self):
        client = VoiceClient(bot_ws=Mock(), user_id="12345")
        client.guild_id = "guild-1"
        client.channel_id = "channel-1"

        client.on_voice_state_update({
            "user_id": "another-user",
            "channel_id": "channel-1",
            "guild_id": "guild-1",
            "session_id": "wrong-session",
        })

        self.assertIsNone(client.session_id)
        self.assertFalse(client._session_event.is_set())

    def test_voice_client_accepts_server_updates_for_current_channel_when_guild_id_absent(self):
        client = VoiceClient(bot_ws=Mock(), user_id="12345")
        client.guild_id = None
        client.channel_id = "channel-1"

        client.on_voice_server_update({
            "channel_id": "channel-1",
            "endpoint": "voice.discord.gg:443",
            "token": "token-123",
        })

        self.assertEqual(client.endpoint, "voice.discord.gg")
        self.assertEqual(client.voice_token, "token-123")
        self.assertTrue(client._server_event.is_set())

    def test_partial_voice_join_remains_leaveable_after_handshake_failure(self):
        class PartialClient:
            def __init__(self, bot_ws, user_id):
                self.gateway_joined = False
                self._ws_error = ""
                self.disconnect_calls = 0

            def connect(self, channel_id, guild_id, is_dm):
                self.gateway_joined = True
                self._ws_error = "Timeout waiting for VOICE_SERVER_UPDATE"
                return False

            def disconnect(self):
                self.disconnect_calls += 1
                self.gateway_joined = False

        api = Mock()
        api.request.return_value.status_code = 200
        api.request.return_value.json.return_value = {"type": 2, "guild_id": "456"}
        bot = Mock()
        bot.ws = Mock()
        bot.user_id = "789"
        bot._voice_client = None
        manager = SimpleVoice(api, "token", bot)

        with patch("voice.VoiceClient", PartialClient):
            self.assertFalse(manager.join_vc("123"))
            self.assertTrue(manager.is_in_voice())
            client = manager.active_connections["channel_123"]

            self.assertTrue(manager.leave_vc())

        self.assertEqual(client.disconnect_calls, 1)
        self.assertIsNone(bot._voice_client)

    def test_voice_ws_stops_retrying_on_e2ee_requirement(self):
        client = VoiceClient(bot_ws=Mock(), user_id="12345")
        attempts = {"count": 0}

        async def fake_connect():
            attempts["count"] += 1
            client._voice_unsupported = True
            client._ws_error = "Voice server requires E2EE/DAVE, which Aria voice does not support yet."

        client._voice_ws_connect = fake_connect
        client.running = True

        with patch("voice.time.sleep") as sleep_mock:
            client._run_voice_ws()

        self.assertEqual(attempts["count"], 1)
        self.assertTrue(client._voice_unsupported)
        sleep_mock.assert_not_called()

    def test_set_stream_in_dm_call_uses_call_stream(self):
        bot_ws = Mock()
        bot = Mock()
        bot.ws = bot_ws
        manager = SimpleVoice(Mock(), "token", bot)
        client = VoiceClient(bot_ws=bot_ws, user_id="789")
        client.gateway_joined = True
        client.channel_id = "123"
        client.is_dm_call = True
        client.channel_type = 1
        manager.active_connections["channel_123"] = client

        ok, _ = manager.set_stream("123", True)

        self.assertTrue(ok)
        payloads = [json.loads(c.args[0]) for c in bot_ws.send.call_args_list]
        create = next(p for p in payloads if p["op"] == 18)
        self.assertEqual(create["d"]["type"], "call")
        self.assertIsNone(create["d"]["guild_id"])

    def test_join_vc_accepts_stage_channels(self):
        class CapturingClient:
            last_channel_type = None

            def __init__(self, bot_ws, user_id):
                self.gateway_joined = False
                self._ws_error = ""

            def connect(self, channel_id, guild_id, is_dm, channel_type=None):
                CapturingClient.last_channel_type = channel_type
                self.gateway_joined = True
                return True

        api = Mock()
        api.request.return_value.status_code = 200
        api.request.return_value.json.return_value = {"type": 13, "guild_id": "456"}
        bot = Mock()
        bot.ws = Mock()
        bot.user_id = "789"
        bot._voice_client = None
        manager = SimpleVoice(api, "token", bot)

        with patch("voice.VoiceClient", CapturingClient):
            self.assertTrue(manager.join_vc("123"))

        self.assertEqual(CapturingClient.last_channel_type, 13)

    def test_set_stream_sends_stream_lifecycle_payloads(self):
        api = Mock()
        bot_ws = Mock()
        bot = Mock()
        bot.ws = bot_ws
        bot.user_id = "789"
        manager = SimpleVoice(api, "token", bot)

        client = VoiceClient(bot_ws=bot_ws, user_id="789")
        client.gateway_joined = True
        client.guild_id = "456"
        client.channel_id = "123"
        client.channel_type = 2
        manager.active_connections["channel_123"] = client

        ok_start, _ = manager.set_stream("123", True)
        ok_stop, _ = manager.set_stream("123", False)

        self.assertTrue(ok_start)
        self.assertTrue(ok_stop)

        payloads = [json.loads(call.args[0]) for call in bot_ws.send.call_args_list]
        self.assertTrue(any(p.get("op") == 18 for p in payloads))
        self.assertTrue(any(p.get("op") == 19 for p in payloads))
        self.assertTrue(any(
            p.get("op") == 4 and isinstance(p.get("d"), dict) and p["d"].get("self_stream") is True
            for p in payloads
        ))

    def test_set_stream_rejects_stage_channels(self):
        api = Mock()
        bot_ws = Mock()
        bot = Mock()
        bot.ws = bot_ws
        bot.user_id = "789"
        manager = SimpleVoice(api, "token", bot)

        client = VoiceClient(bot_ws=bot_ws, user_id="789")
        client.gateway_joined = True
        client.guild_id = "456"
        client.channel_id = "123"
        client.channel_type = 13
        manager.active_connections["channel_123"] = client

        ok, detail = manager.set_stream("123", True)

        self.assertFalse(ok)
        self.assertIn("stage", detail.lower())

    def test_voice_ready_selects_best_encryption_mode(self):
        client = VoiceClient(bot_ws=Mock(), user_id="12345")

        class FakeWs:
            def __init__(self):
                self.payloads = []

            async def send(self, payload):
                self.payloads.append(json.loads(payload))

        ws = FakeWs()
        ready = {
            "op": VoiceOpcodes.Ready,
            "d": {
                "ssrc": 42,
                "ip": "127.0.0.1",
                "port": 5000,
                "modes": ["xsalsa20_poly1305", "aead_xchacha20_poly1305_rtpsize"],
            },
        }

        with patch.object(client, "_ip_discovery", return_value=("0.0.0.0", 0)):
            asyncio.run(client._handle_voice_op(ws, ready))

        self.assertEqual(client.encryption_mode, "aead_xchacha20_poly1305_rtpsize")
        self.assertEqual(ws.payloads[-1]["op"], VoiceOpcodes.SelectProtocol)
        self.assertEqual(
            ws.payloads[-1]["d"]["data"]["mode"],
            "aead_xchacha20_poly1305_rtpsize",
        )

    def test_secure_frames_prepare_acknowledges_transition(self):
        client = VoiceClient(bot_ws=Mock(), user_id="12345")

        class FakeWs:
            def __init__(self):
                self.payloads = []

            async def send(self, payload):
                self.payloads.append(json.loads(payload))

        ws = FakeWs()
        prepare = {
            "op": VoiceOpcodes.SecureFramesPrepareProtocolTransition,
            "d": {"protocol": "dave", "transition_id": "t1"},
        }

        asyncio.run(client._handle_voice_op(ws, prepare))

        self.assertEqual(client.encryption_mode, "dave")
        self.assertEqual(ws.payloads[-1]["op"], VoiceOpcodes.SecureFramesExecuteTransition)
        self.assertEqual(ws.payloads[-1]["d"], {"protocol": "dave", "transition_id": "t1"})


class CloseCodeTests(unittest.TestCase):
    def _close(self, code):
        bot = make_bot()
        bot._total_uptime = 0.0
        bot._last_uptime_check = time.time()
        bot.heartbeat_thread = None
        bot.health_monitor = None
        bot.session_id = "abc"
        bot.resume_gateway_url = "wss://resume"
        bot.can_resume = True
        scheduled = []
        bot._schedule_reconnect = lambda reason="": scheduled.append(reason) or True
        bot.on_close(None, code, "")
        return bot, scheduled

    def test_fatal_codes_stop_retrying(self):
        for code in (4004, 4012, 4013, 4014):
            bot, scheduled = self._close(code)
            self.assertFalse(bot.running, code)
            self.assertEqual(scheduled, [], code)

    def test_session_timeout_drops_resume_state_and_reconnects(self):
        for code in (4007, 4009):
            bot, scheduled = self._close(code)
            self.assertTrue(bot.running)
            self.assertFalse(bot.can_resume)
            self.assertIsNone(bot.session_id)
            self.assertEqual(len(scheduled), 1)

    def test_transient_close_keeps_resume_state(self):
        bot, scheduled = self._close(1006)
        self.assertTrue(bot.can_resume)
        self.assertEqual(bot.session_id, "abc")
        self.assertEqual(len(scheduled), 1)

    def test_rate_limited_close_forces_backoff(self):
        bot, _ = self._close(4008)
        self.assertGreaterEqual(bot._consecutive_failures, 3)


class InstanceLockTests(unittest.TestCase):
    def test_second_instance_blocked_until_release(self):
        import tempfile
        from connection_health_monitor import InstanceSingletonManager

        with tempfile.TemporaryDirectory() as tmp:
            first, second = InstanceSingletonManager(tmp), InstanceSingletonManager(tmp)
            self.assertTrue(first.acquire("token-a"))
            self.assertFalse(second.acquire("token-a"))
            self.assertEqual(second.holder.get("pid"), os.getpid())
            self.assertTrue(InstanceSingletonManager(tmp).acquire("token-b"))
            first.release()
            self.assertTrue(second.acquire("token-a"))
            second.release()


if __name__ == "__main__":
    unittest.main()