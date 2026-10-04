"""Super React module based on Aria implementation"""

import json
import queue
import threading
import time
import websocket
from typing import Optional
from urllib.parse import quote as url_quote
from discord_api_types import GatewayOpcodes

# logger = Logger("Superreact")
print("Superreact initialized")


class SuperReactClient:
    """WebSocket-based super react client from Aria"""

    API_GW = "wss://gateway.discord.gg/?v=9&encoding=json"
    def __init__(self, token: str, api_client=None):
        self.token = token
        self.api_client = api_client
        self.user_id = None
        self.fingerprint = None
        self.last_seq = None
        self.targets = {}
        self.msr_targets = {}  # multi super react: user_id -> (emojis, current_idx)
        self.ssr_targets = {}  # single super react: user_id -> [emojis]
        self.targets_lock = threading.Lock()
        self.ws = None
        self.thread = None
        self.heartbeat_thread = None
        self.stop_event = threading.Event()
        self.ready_event = threading.Event()
        self.reaction_queue = queue.Queue(maxsize=500)
        self.worker_threads = []
        self.emoji_path_cache = {}

    def is_running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def is_ready(self) -> bool:
        return self.ready_event.is_set()

    def _start_workers(self, count: int = 4):
        if self.worker_threads:
            return
        for i in range(count):
            worker = threading.Thread(target=self._reaction_worker, name=f"sr-worker-{i}")
            worker.start()
            self.worker_threads.append(worker)

    def _format_emoji_path(self, emoji: str) -> str:
        cached = self.emoji_path_cache.get(emoji)
        if cached:
            return cached

        if emoji.startswith("<a:") or emoji.startswith("<:"):
            parts = emoji.replace("<", "").replace(">", "").split(":")
            if len(parts) >= 3:
                path = f"{parts[1]}:{parts[2]}"
            else:
                path = url_quote(emoji)
        else:
            path = url_quote(emoji)

        if len(self.emoji_path_cache) > 1024:
            self.emoji_path_cache.clear()
        self.emoji_path_cache[emoji] = path
        return path

    def _reaction_worker(self):
        while not self.stop_event.is_set():
            try:
                guild_id, channel_id, message_id, emoji, author_id = self.reaction_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self.send_super_reaction_rest(guild_id, channel_id, message_id, emoji)
                print(f"[Super React] Reacted {emoji} to {author_id}")
                time.sleep(0.05)  # Small delay to avoid rate limits
            except Exception as e:
                print(f"[Super React] Reaction failed for {author_id}: {e}")
            finally:
                self.reaction_queue.task_done()

    def send_super_reaction_rest(self, guild_id, channel_id, message_id, emoji):
        if self.api_client is None:
            raise RuntimeError("SuperReact requires the shared Discord API client.")
        path = self._format_emoji_path(emoji)
        endpoint = f"/channels/{channel_id}/messages/{message_id}/reactions/{path}/@me"
        response = self.api_client.request(
            "PUT",
            endpoint,
            params={"location": "Message Reaction Picker", "type": 1},
        )
        if response is None or response.status_code not in (200, 204):
            status = getattr(response, "status_code", "no response")
            raise RuntimeError(f"HTTP {status} during super reaction")

    def _heartbeat(self, interval):
        while self.ws and self.ws.sock and self.ws.sock.connected:
            time.sleep(interval)
            payload = {"op": GatewayOpcodes.Heartbeat, "d": self.last_seq}
            try:
                self.ws.send(json.dumps(payload))
            except websocket.WebSocketConnectionClosedException:
                break

    def on_message(self, ws, message):
        payload = json.loads(message)
        op, d, s, t = payload.get("op"), payload.get("d"), payload.get("s"), payload.get("t")

        if s:
            self.last_seq = s

        if op == GatewayOpcodes.Hello:
            interval = d["heartbeat_interval"] / 1000
            self.heartbeat_thread = threading.Thread(target=self._heartbeat, args=(interval,))
            self.heartbeat_thread.start()
            
            identify_payload = {
                "op": GatewayOpcodes.Identify, "d": { "token": self.token, "capabilities": 253,
                    "properties": { "os": "Windows", "browser": "Discord Client", "release_channel": "stable", "client_version": "1.0.9198", "os_version": "10.0.26100", "os_arch": "x64", "system_locale": "en-US", "client_build_number": 415714, "native_build_number": 69420, "client_event_source": None },
                    "presence": { "status": "online", "since": 0, "activities": [], "afk": False },
                    "compress": False, "client_state": { "guild_hashes": {}, "highest_last_message_id": "0", "read_state_version": 0, "user_guild_settings_version": -1, "user_settings_version": -1, "private_channels_version": "0", "api_code_version": 0 }
                }
            }
            self.ws.send(json.dumps(identify_payload))
        
        elif t == "READY":
            self.user_id = d["user"]["id"]
            self.ready_event.set()
            print("[Super React] WebSocket is READY and active.")
        
        elif t == "MESSAGE_CREATE":
            author_id = d["author"]["id"]
            guild_id = d.get("guild_id")
            channel_id = d["channel_id"]
            msg_id = d["id"]
            
            with self.targets_lock:
                emoji_to_react = self.targets.get(author_id)
                if emoji_to_react:
                    try:
                        self.reaction_queue.put_nowait((guild_id, channel_id, msg_id, emoji_to_react, author_id))
                    except queue.Full:
                        print("[Super React] Queue is full; dropping reaction event.")
                
                if author_id in self.msr_targets:
                    emojis, idx = self.msr_targets[author_id]
                    emoji = emojis[idx]
                    try:
                        self.reaction_queue.put_nowait((guild_id, channel_id, msg_id, emoji, author_id))
                    except queue.Full:
                        print("[Super React] Queue is full; dropping reaction event.")
                    self.msr_targets[author_id] = (emojis, (idx + 1) % len(emojis))
                
                if author_id in self.ssr_targets:
                    for emoji in self.ssr_targets[author_id]:
                        try:
                            self.reaction_queue.put_nowait((guild_id, channel_id, msg_id, emoji, author_id))
                        except queue.Full:
                            print("[Super React] Queue is full; dropping reaction event.")
                            break

    def on_open(self, ws):
        print("[Super React] WebSocket connection opened. Logging in...")

    def on_error(self, ws, error):
        print(f"[Super React] WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.ready_event.clear()
        print(f"[Super React] WebSocket connection closed. Code: {close_status_code}, Msg: {close_msg}")

    def start(self):
        if self.is_running():
            return self.is_ready()

        self.stop_event.clear()
        self.ready_event.clear()
        self._start_workers()
            
        self.ws = websocket.WebSocketApp(
            self.API_GW,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        self.thread = threading.Thread(target=self.ws.run_forever)
        self.thread.start()
        return self.ready_event.wait(timeout=10)

    def stop(self):
        self.stop_event.set()
        self.ready_event.clear()
        while not self.reaction_queue.empty():
            try:
                self.reaction_queue.get_nowait()
                self.reaction_queue.task_done()
            except queue.Empty:
                break
        if self.ws:
            self.ws.close()
        # Join main websocket thread
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
        # Join heartbeat thread
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=10)
        # Join worker threads
        for worker in self.worker_threads:
            if worker.is_alive():
                worker.join(timeout=10)
        self.worker_threads = []
        self.heartbeat_thread = None
        self.thread = None
        print("[Super React] Client stopping.")

    def add_target(self, user_id: str, emoji: str):
        """Add a target user for super reactions"""
        with self.targets_lock:
            self.targets[user_id] = emoji
        # Removed auto-start to prevent conflicts

    def remove_target(self, user_id: str):
        """Remove a target user"""
        with self.targets_lock:
            self.targets.pop(user_id, None)

    def get_targets(self):
        """Get all targets"""
        with self.targets_lock:
            return dict(self.targets)

    def add_msr_target(self, user_id: str, emojis: list):
        """Add a multi super react target"""
        with self.targets_lock:
            self.msr_targets[user_id] = (emojis, 0)

    def remove_msr_target(self, user_id: str):
        """Remove a multi super react target"""
        with self.targets_lock:
            self.msr_targets.pop(user_id, None)

    def add_ssr_target(self, user_id: str, emojis: list):
        """Add a single super react target"""
        with self.targets_lock:
            self.ssr_targets[user_id] = emojis

    def remove_ssr_target(self, user_id: str):
        """Remove a single super react target"""
        with self.targets_lock:
            self.ssr_targets.pop(user_id, None)

    def get_msr_targets(self):
        """Get all msr targets"""
        with self.targets_lock:
            return dict(self.msr_targets)

    def get_ssr_targets(self):
        """Get all ssr targets"""
        with self.targets_lock:
            return dict(self.ssr_targets)


# Global super react client (typed for static analysis)
super_react_client: Optional[SuperReactClient] = None