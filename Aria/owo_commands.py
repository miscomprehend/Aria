import json
import random
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULTS = {
    "channel_id": None,
    "commands": ["wh", "wb"],
    "cmd_gap": 0.6,
    "delay_min": 11.0,
    "delay_max": 19.0,
}
OWO_BOT_ID = "408785106942164992"
STOP_WORDS = ("captcha", "are you a real human", "verify", "banned", "warning")


def _load_config(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as config_file:
            saved = json.load(config_file)
    except FileNotFoundError:
        return {**DEFAULTS, "commands": list(DEFAULTS["commands"])}
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load OwO settings: {exc}") from exc

    if not isinstance(saved, dict):
        raise ValueError("OwO settings must contain a JSON object.")

    config = {**DEFAULTS, **saved}
    commands = config.get("commands")
    if not isinstance(commands, list) or not all(
        isinstance(command, str) and command.strip() for command in commands
    ):
        raise ValueError("OwO commands must be a list of non-empty strings.")
    config["commands"] = [command.strip() for command in commands]

    try:
        config["cmd_gap"] = float(config["cmd_gap"])
        config["delay_min"] = float(config["delay_min"])
        config["delay_max"] = float(config["delay_max"])
    except (TypeError, ValueError) as exc:
        raise ValueError("OwO delays in the settings file must be numbers.") from exc
    if (
        config["cmd_gap"] < 0
        or config["delay_min"] <= 0
        or config["delay_max"] < config["delay_min"]
    ):
        raise ValueError("OwO settings contain an invalid delay range.")

    channel_id = config.get("channel_id")
    if channel_id is not None:
        channel_id = str(channel_id)
        if not channel_id.isdigit():
            raise ValueError("OwO channel_id must be a numeric channel ID.")
        config["channel_id"] = channel_id
    return config


def setup_owo_commands(bot, config_path: Optional[str] = None) -> None:
    """Register OwO commands on Aria's primary command bot."""
    path = Path(config_path) if config_path else Path(__file__).with_name("owo_config.json")
    config = _load_config(path)
    lock = threading.RLock()
    worker: Optional[threading.Thread] = None
    stop_event: Optional[threading.Event] = None

    def save_config() -> None:
        with path.open("w", encoding="utf-8") as config_file:
            json.dump(config, config_file, indent=2)

    def send(ctx, content: str) -> None:
        response = ctx["api"].send_message(ctx["channel_id"], content)
        if response is None:
            raise RuntimeError("OwO message was not sent.")

    def current_worker() -> Optional[threading.Thread]:
        with lock:
            return worker if worker and worker.is_alive() else None

    def send_cycle(channel_id: str, stop: Optional[threading.Event] = None) -> None:
        with lock:
            commands = list(config["commands"])
            gap = config["cmd_gap"]
        for index, command in enumerate(commands):
            if stop is not None and stop.is_set():
                return
            response = bot.api.send_message(channel_id, command)
            if response is None:
                raise RuntimeError(f"OwO command `{command}` was not sent.")
            if index < len(commands) - 1 and gap and stop is not None:
                if stop.wait(gap):
                    return
            elif index < len(commands) - 1 and gap:
                time.sleep(gap)

    def run_farm(channel_id: str, stop: threading.Event) -> None:
        try:
            while not stop.is_set():
                send_cycle(channel_id, stop)
                with lock:
                    delay_min = config["delay_min"]
                    delay_max = config["delay_max"]
                if stop.wait(random.uniform(delay_min, delay_max)):
                    break
        except Exception as exc:
            print(f"[OWO] farm stopped: {exc}")

    def on_message_create(message: Dict[str, Any]) -> None:
        with lock:
            active = worker is not None and worker.is_alive()
            channel_id = config["channel_id"]
            active_stop_event = stop_event
        if not active or active_stop_event is None:
            return
        author = message.get("author") or {}
        if str(author.get("id") or "") != OWO_BOT_ID:
            return
        message_channel = str(message.get("channel_id") or "")
        if message.get("guild_id") and message_channel != str(channel_id or ""):
            return
        content = str(message.get("content") or "").lower()
        if any(word in content for word in STOP_WORDS):
            active_stop_event.set()
            print("[OWO] captcha/warning detected, farm stopped")

    bot._owo_on_message_create = on_message_create

    @bot.command(name="owofarm", aliases=["owof"])
    def owofarm(ctx, args: List[str]) -> None:
        nonlocal worker, stop_event
        parts = [str(arg) for arg in args]
        subcommand = parts[0].lower() if parts else "status"
        values = parts[1:]

        if subcommand == "channel":
            channel_id = values[0] if values else str(ctx.get("channel_id") or "")
            if not channel_id.isdigit():
                send(ctx, "Usage: owofarm channel [channel_id]")
                return
            with lock:
                config["channel_id"] = channel_id
                save_config()
            send(ctx, f"OwO farm channel set to {channel_id}.")
        elif subcommand in ("cmds", "commands"):
            with lock:
                listing = ", ".join(
                    f"{index + 1}:{command}"
                    for index, command in enumerate(config["commands"])
                ) or "none"
            send(ctx, f"OwO commands: {listing}")
        elif subcommand == "add" and values:
            command = " ".join(values).strip()
            if len(command) > 200:
                send(ctx, "OwO commands must be 200 characters or fewer.")
                return
            with lock:
                config["commands"].append(command)
                save_config()
            send(ctx, f"Added `{command}`.")
        elif subcommand == "remove" and values and values[0].isdigit():
            index = int(values[0])
            with lock:
                if not 1 <= index <= len(config["commands"]):
                    send(ctx, "Invalid command position.")
                    return
                removed = config["commands"].pop(index - 1)
                save_config()
            send(ctx, f"Removed `{removed}`.")
        elif subcommand == "delay" and len(values) in (2, 3):
            try:
                delay_min, delay_max = float(values[0]), float(values[1])
                gap = float(values[2]) if len(values) == 3 else None
            except ValueError:
                send(ctx, "Usage: owofarm delay <min> <max> [gap]")
                return
            if delay_min <= 0 or delay_max < delay_min or (gap is not None and gap < 0):
                send(ctx, "Invalid delay range.")
                return
            with lock:
                config["delay_min"] = delay_min
                config["delay_max"] = delay_max
                if gap is not None:
                    config["cmd_gap"] = gap
                save_config()
            send(ctx, f"OwO delay set to {delay_min}-{delay_max}s.")
        elif subcommand == "once":
            with lock:
                channel_id = config["channel_id"]
            if not channel_id:
                send(ctx, "Set a channel first: owofarm channel")
                return
            send_cycle(channel_id)
            send(ctx, "OwO cycle sent.")
        elif subcommand == "start":
            with lock:
                channel_id = config["channel_id"]
                if not channel_id:
                    send(ctx, "Set a channel first: owofarm channel")
                    return
                if worker and worker.is_alive():
                    send(ctx, "OwO farm is already running.")
                    return
                stop_event = threading.Event()
                worker = threading.Thread(
                    target=run_farm,
                    args=(channel_id, stop_event),
                    name="AriaOwOFarm",
                    daemon=True,
                )
                worker.start()
            send(ctx, "OwO farm started.")
        elif subcommand == "stop":
            with lock:
                if not worker or not worker.is_alive() or stop_event is None:
                    send(ctx, "OwO farm is not running.")
                    return
                stop_event.set()
            send(ctx, "OwO farm stopping.")
        elif subcommand in ("status", "check"):
            with lock:
                channel_id = config["channel_id"] or "not set"
                commands = ", ".join(config["commands"]) or "none"
                delay_min = config["delay_min"]
                delay_max = config["delay_max"]
            running = current_worker() is not None
            send(
                ctx,
                f"OwO farm: {'running' if running else 'stopped'}; "
                f"channel: {channel_id}; commands: {commands}; "
                f"delay: {delay_min}-{delay_max}s.",
            )
        else:
            send(
                ctx,
                "Usage: owofarm <start|stop|once|status|channel [id]|cmds|"
                "add <command>|remove <n>|delay <min> <max> [gap]>",
            )

    @bot.command(name="owo")
    def owo(ctx, _args: List[str]) -> None:
        send(ctx, "OwO! You look amazing today!")

    @bot.command(name="uwu")
    def uwu(ctx, _args: List[str]) -> None:
        send(ctx, "UwU! You're so adorable!")
