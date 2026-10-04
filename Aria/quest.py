"""Enhanced Quest System - Integrating Auto-Quest TypeScript features with Aria's Python implementation."""

import time
import random
import threading
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List, Any

# Import new quest system modules
try:
    from .quest_system import (
        QuestManager,
        Quest as EnhancedQuest,
        AllQuestsResponse,
        Utils as QuestUtils,
        Constants,
    )
except ImportError:
    from quest_system import (
        QuestManager,
        Quest as EnhancedQuest,
        AllQuestsResponse,
        Utils as QuestUtils,
        Constants,
    )

# Logger
logger = logging.getLogger(__name__)

QUESTS_BASE = "https://discord.com/api/v9"


class QuestSystem:
    """Enhanced quest system combining legacy Aria implementation with Auto-Quest features."""

    def __init__(self, api_client):
        self.api = api_client
        self.quests = {}  # quest_id (str) -> raw quest dict from API
        self.excluded = set()  # quest_ids to skip
        self.auto_complete = False
        self._task_thread = None
        self.last_fetch = 0
        self.refresh_interval = 5 * 60  # 5 minutes for quicker real-time pickup
        
        # New quest system manager
        self.quest_manager: Optional[QuestManager] = None
        self.user_id = getattr(api_client, 'user_id', '')

    # =====================================================================
    # Enhanced Header Management (from Auto-Quest)
    # =====================================================================

    def _headers(self, is_android: bool = False) -> Dict[str, str]:
        """Get enhanced headers with Auto-Quest features.
        
        Args:
            is_android: Whether to use Android headers
            
        Returns:
            Headers dictionary
        """
        token = self.api.token
        if token.startswith('Bot '):
            token = token[4:]
        
        base_headers = self.api.header_spoofer.get_protected_headers(token) if hasattr(
            self.api, 'header_spoofer'
        ) else {}
        
        return QuestUtils.make_headers(
            token,
            base_headers=base_headers,
            is_android=is_android,
            with_origin=True,
        )

    # =====================================================================
    # Internal helpers (maintaining legacy compatibility)
    # =====================================================================

    def _expired(self, iso) -> bool:
        """Check if date is expired."""
        if not iso:
            return False
        try:
            return datetime.now(timezone.utc) > datetime.fromisoformat(
                str(iso).replace("Z", "+00:00")
            )
        except Exception:
            return False

    def _tasks_map(self, q: dict) -> dict:
        """Extract tasks map from quest."""
        config = q.get("config", {}) or {}
        if not isinstance(config, dict):
            return {}
        
        for key in ("task_config_v2", "taskConfigV2", "task_config", "taskConfig"):
            tc = config.get(key, {})
            if not isinstance(tc, dict):
                continue

            tasks = tc.get("tasks", {})
            if isinstance(tasks, dict) and tasks:
                return tasks

            looks_like_tasks = False
            for _, tv in tc.items():
                if isinstance(tv, dict) and (
                    "event_name" in tv
                    or "eventName" in tv
                    or "target" in tv
                ):
                    looks_like_tasks = True
                    break
            if looks_like_tasks:
                return tc
        return {}

    def _task_names(self, q: dict) -> list:
        """Collect all task/event identifiers."""
        tasks = self._tasks_map(q)
        names = [str(k).lower() for k in tasks.keys()]
        for _, tv in tasks.items():
            if not isinstance(tv, dict):
                continue
            ev = str(tv.get("event_name") or tv.get("eventName") or "").lower().strip()
            if ev:
                names.append(ev)
        return names

    def _task_platforms(self, q: dict) -> set:
        """Infer target platforms from task names/events."""
        names = self._task_names(q)
        platforms = set()
        for n in names:
            if any(x in n for x in ("desktop", "pc", "windows", "mac", "linux")):
                platforms.add("desktop")
            if "mobile" in n:
                platforms.add("mobile")
            if "xbox" in n:
                platforms.add("xbox")
            if "playstation" in n or "ps5" in n or "ps4" in n:
                platforms.add("playstation")
            if "switch" in n or "nintendo" in n:
                platforms.add("switch")
        return platforms

    def _task_type(self, q: dict) -> str:
        """Determine quest task type."""
        return QuestUtils.get_task_type(q)

    def _quest_name(self, q: dict) -> str:
        """Get human-readable quest name."""
        return QuestUtils.get_quest_display_name(q)

    def _get_progress(self, q: dict):
        """Returns (event_name, done, total)."""
        tasks = self._tasks_map(q)
        status = q.get("user_status") or {}
        progress = status.get("progress", {}) if isinstance(status, dict) else {}
        if not isinstance(progress, dict):
            progress = {}
        done = 0
        event_name = None

        if isinstance(progress, dict):
            for _, val in progress.items():
                if not isinstance(val, dict):
                    continue
                try:
                    v = max(0, int(float(val.get("value", 0) or 0)))
                except (TypeError, ValueError, OverflowError):
                    continue
                if v >= done:
                    done = v
                    event_name = val.get("event_name")

        total = 100
        if event_name:
            for _, task in tasks.items():
                if isinstance(task, dict) and task.get("event_name") == event_name:
                    try:
                        total = int(float(task.get("target", 100) or 100))
                    except (TypeError, ValueError, OverflowError):
                        total = 100
                    break
        elif tasks:
            smallest = None
            for _, task in tasks.items():
                if isinstance(task, dict):
                    try:
                        target = int(float(task.get("target", 100) or 100))
                    except (TypeError, ValueError, OverflowError):
                        continue
                    if smallest is None or target < smallest:
                        smallest = target
                        event_name = task.get("event_name") or event_name
            total = smallest if smallest is not None else 100

        return str(event_name or "Unknown"), max(0, done), max(1, total)

    def get_quest_state(self, q: dict) -> str:
        """Describe the server-reported quest state without changing it."""
        status = q.get("user_status") or {}
        if not isinstance(status, dict):
            status = {}
        config = q.get("config") or {}
        if not isinstance(config, dict):
            config = {}
        if self._expired(config.get("expires_at")):
            return "Expired"
        if status.get("completed_at"):
            return "Reward claimed" if status.get("claimed_at") else "Completed"
        if status.get("enrolled_at"):
            return "In progress"
        return "Available"

    def _is_enrollable(self, q: dict) -> bool:
        """Check if quest can be enrolled."""
        config = q.get("config", {}) or {}
        return not q.get("user_status") and not self._expired(config.get("expires_at"))

    def _is_completeable(self, q: dict) -> bool:
        """Check if quest can be completed."""
        config = q.get("config", {}) or {}
        status = q.get("user_status") or {}
        return bool(
            status
            and status.get("enrolled_at")
            and not status.get("completed_at")
            and not self._expired(config.get("expires_at"))
        )

    def _is_claimable(self, q: dict) -> bool:
        """Check if quest rewards can be claimed."""
        config = q.get("config", {}) or {}
        rewards_cfg = config.get("rewards_config", {}) or {}
        status = q.get("user_status") or {}
        return bool(
            status
            and status.get("completed_at")
            and not status.get("claimed_at")
            and not self._expired(config.get("expires_at"))
            and rewards_cfg.get("rewards_expire_at")
            and not self._expired(rewards_cfg.get("rewards_expire_at"))
        )

    def _is_worthy(self, q: dict) -> bool:
        """Check if quest is worth completing (has good rewards)."""
        config = q.get("config", {}) or {}
        rewards_cfg = config.get("rewards_config", {}) or {}
        
        if not isinstance(rewards_cfg, dict):
            return False
        
        rewards = rewards_cfg.get("rewards", [])
        if not rewards:
            return False
        
        for reward in rewards:
            if isinstance(reward, dict):
                reward_type = reward.get("reward_type", "").lower()
                if "nitro" in reward_type or "boost" in reward_type or "cosmetic" in reward_type:
                    return True
        
        return len(rewards) > 0

    # =====================================================================
    # API Methods
    # =====================================================================

    def fetch_quests(self, force: bool = False) -> tuple[bool, str]:
        """Fetch quests from Discord API."""
        now = time.time()
        if not force and now - self.last_fetch < 30:
            return False, "Please wait before refreshing quests again."
        
        try:
            resp = self.api.request("GET", "/quests/@me")
            if resp and resp.status_code == 200:
                data = resp.json()
                if not isinstance(data, dict):
                    return False, "Discord returned an invalid quest response."

                quest_entries = [
                    quest for quest in data.get("quests", [])
                    if isinstance(quest, dict)
                    and quest.get("id")
                    and (quest.get("config") or {}).get("grant_type") != "USER_MADE"
                ]
                filtered_data = dict(data)
                filtered_data["quests"] = quest_entries
                response = AllQuestsResponse.from_dict(filtered_data, self.user_id)
                quest_manager = QuestManager.from_response(
                    response, self.user_id, fetch_excluded=False
                )
                parsed_ids = {quest.id for quest in quest_manager}
                quest_cache = {
                    str(quest["id"]): quest
                    for quest in quest_entries
                    if str(quest["id"]) in parsed_ids
                }

                self.quest_manager = quest_manager
                self.quests = quest_cache
                
                self.last_fetch = now
                return True, "Quest data updated."
            status = getattr(resp, "status_code", "no response") if resp else "no response"
            return False, f"Quest request failed (HTTP {status})."
        except Exception as e:
            logger.error(f"Failed to fetch quests: {e}")
            return False, f"Quest request failed: {e}"

    def enroll(self, q: dict):
        """Enroll in a single quest."""
        if not self._is_enrollable(q):
            return None
        
        qid = q.get("id")
        try:
            resp = self.api.request(
                "POST",
                f"/quests/{qid}/enroll",
                data={"is_targeted": False, "location": 11, "metadata_raw": None},
            )
            if resp and resp.status_code in (200, 201):
                body = resp.json() if resp.content else {}
                if isinstance(body, dict):
                    return body
                return q.get("user_status") or {}
            if resp and resp.status_code == 204:
                return q.get("user_status") or {"enrolled_at": datetime.now(timezone.utc).isoformat()}
        except Exception as e:
            logger.error(f"Failed to enroll in quest {qid}: {e}")
        
        return None

    def claim(self, q: dict) -> bool:
        """Claim quest rewards."""
        qid = str(q.get("id", ""))
        if not qid or not self._is_claimable(q):
            return False
        
        endpoints = (
            f"/quests/{qid}/claim-reward",
            f"/quests/{qid}/claim_reward",
            f"/quests/{qid}/claim",
        )
        
        for ep in endpoints:
            try:
                resp = self.api.request("POST", ep, data={})
                if resp and resp.status_code in (200, 201, 204):
                    us = q.get("user_status") or {}
                    us["claimed_at"] = datetime.now(timezone.utc).isoformat()
                    q["user_status"] = us
                    return True
            except Exception:
                continue
        
        return False

    def _send_progress(self, q: dict):
        """Send one progress tick."""
        qid = str(q.get("id", ""))
        qtype = self._task_type(q)
        platforms = self._task_platforms(q)
        _, done, total = self._get_progress(q)

        try:
            if qtype == "watch":
                enrolled_raw = (q.get("user_status") or {}).get("enrolled_at")
                try:
                    enrolled_ts = datetime.fromisoformat(
                        str(enrolled_raw).replace("Z", "+00:00")
                    ).timestamp()
                except Exception:
                    enrolled_ts = datetime.now(timezone.utc).timestamp()

                max_allowed = int(datetime.now(timezone.utc).timestamp() - enrolled_ts) + 10
                speed = 7
                if max_allowed - done < speed:
                    return True, False, done, total

                new_val = min(done + speed + random.random(), max_allowed)
                resp = None
                watch_endpoints = (
                    f"/quests/{qid}/video-progress",
                    f"/quests/{qid}/video_progress",
                )
                watch_payloads = (
                    {"timestamp": new_val},
                    {"value": new_val},
                    {"seconds": new_val},
                )
                for ep in watch_endpoints:
                    for payload in watch_payloads:
                        resp = self.api.request("POST", ep, data=payload)
                        if resp and resp.status_code in (200, 204):
                            break
                    if resp and resp.status_code in (200, 204):
                        break
            elif qtype in ("play", "stream"):
                app_id = str(((q.get("config") or {}).get("application") or {}).get("id") or "")
                resp = None
                hb_endpoints = (
                    f"/quests/{qid}/heartbeat",
                    f"/quests/{qid}/heartbeats",
                )

                base_payload = {}
                if app_id:
                    base_payload["application_id"] = app_id

                terminal_candidates = [False, True]
                if "desktop" in platforms:
                    terminal_candidates = [True, False]

                platform_candidates = [None]
                if platforms:
                    platform_candidates = list(platforms) + [None]

                for ep in hb_endpoints:
                    for term in terminal_candidates:
                        for plat in platform_candidates:
                            hb_payload = dict(base_payload)
                            hb_payload["terminal"] = term
                            if plat:
                                hb_payload["platform"] = plat
                            resp = self.api.request("POST", ep, data=hb_payload)
                            if resp and resp.status_code in (200, 204):
                                break
                        if resp and resp.status_code in (200, 204):
                            break
                    if resp and resp.status_code in (200, 204):
                        break
            else:
                return False, False, done, total

            if not resp or resp.status_code not in (200, 204):
                if resp and resp.status_code in (401, 404):
                    self.excluded.add(qid)
                return False, False, done, total

            if resp.status_code == 204:
                return True, False, done, total

            rdata = resp.json() if resp.content else {}
            if not isinstance(rdata, dict):
                rdata = {}

            # Completed?
            if rdata.get("completed_at"):
                us = q.get("user_status") or {}
                us["completed_at"] = rdata["completed_at"]
                q["user_status"] = us
                return True, True, total, total

            # Parse updated progress
            prog = rdata.get("progress") or rdata.get("user_status", {}).get("progress") or {}
            for _, pv in prog.items():
                if isinstance(pv, dict):
                    try:
                        v = int(float(pv.get("value", done)))
                        if v > done:
                            done = v
                    except Exception:
                        pass
            sps = rdata.get("streamProgressSeconds")
            if sps is not None:
                try:
                    done = max(done, int(float(sps)))
                except Exception:
                    pass

            return True, False, done, total
        except Exception as e:
            logger.error(f"Failed to send progress for quest {qid}: {e}")
            return False, False, done, total

    # =====================================================================
    # Background runner
    # =====================================================================

    def _run_auto_complete(self):
        """Background thread for auto-completing quests."""
        # Auto-enroll first
        for q in list(self.quests.values()):
            if not self.auto_complete:
                return
            if self._is_enrollable(q):
                status = self.enroll(q)
                if status:
                    q["user_status"] = status
                time.sleep(0.8)

        while self.auto_complete:
            try:
                if time.time() - self.last_fetch > self.refresh_interval:
                    self.fetch_quests()

                to_process = [
                    q for q in self.quests.values()
                    if self._is_completeable(q) and str(q.get("id", "")) not in self.excluded
                ]
                to_process.sort(key=lambda q: 0 if self._is_worthy(q) else 1)

                for q in to_process:
                    if not self.auto_complete:
                        break
                    self._send_progress(q)

                for q in list(self.quests.values()):
                    if not self.auto_complete:
                        break
                    if self._is_claimable(q):
                        self.claim(q)
                        time.sleep(0.6)

                time.sleep(random.randint(45, 60))
            except Exception as e:
                logger.error(f"Error in auto-complete loop: {e}")
                time.sleep(30)

    def start(self):
        """Start auto-complete."""
        if self.auto_complete:
            return False, "Already running"
        self.auto_complete = True
        if not self.quests:
            self.fetch_quests()
        self._task_thread = threading.Thread(target=self._run_auto_complete, daemon=True)
        self._task_thread.start()
        return True, "Started"

    def stop(self):
        """Stop auto-complete."""
        if not self.auto_complete:
            return False, "Not running"
        self.auto_complete = False
        self._task_thread = None
        return True, "Stopped"

    # =====================================================================
    # Summary
    # =====================================================================

    def get_summary(self):
        """Get summary of quests."""
        enrollable, completeable, claimable, completed, expired = [], [], [], [], []
        for q in self.quests.values():
            config = q.get("config", {}) or {}
            if self._expired(config.get("expires_at")):
                expired.append(q)
            elif self._is_claimable(q):
                claimable.append(q)
            elif self._is_completeable(q):
                completeable.append(q)
            elif self._is_enrollable(q):
                enrollable.append(q)
            else:
                completed.append(q)
        return {
            "running": self.auto_complete,
            "total": len(self.quests),
            "enrollable": enrollable,
            "completeable": completeable,
            "claimable": claimable,
            "completed": completed,
            "expired": expired,
            "last_fetch": self.last_fetch,
        }

    # =====================================================================
    # New Enhanced Methods (from Auto-Quest)
    # =====================================================================

    def get_quest_by_id(self, quest_id: str) -> Optional[EnhancedQuest]:
        """Get enhanced quest object by ID.
        
        Args:
            quest_id: Quest ID
            
        Returns:
            Enhanced Quest object or None
        """
        if self.quest_manager:
            return self.quest_manager.get(quest_id)
        return None

    def get_available_quests(self) -> List[EnhancedQuest]:
        """Get all quests available for enrollment."""
        if self.quest_manager:
            return self.quest_manager.get_available()
        return []

    def get_active_quests(self) -> List[EnhancedQuest]:
        """Get all active (non-expired) quests."""
        if self.quest_manager:
            return self.quest_manager.get_active()
        return []

    def get_claimable_quests(self) -> List[EnhancedQuest]:
        """Get all quests with claimable rewards."""
        if self.quest_manager:
            return self.quest_manager.get_claimable()
        return []
