import json
import time
import base64
import threading
import requests
import logging
from datetime import datetime
from discord_api_types import RelationshipType

logger = logging.getLogger(__name__)

class AntiGCTrap:
    def __init__(self, api_client):
        self.api = api_client
        self.enabled = False
        self.block_creators = False
        self.leave_message = "Group chat protection is enabled."
        self.gc_name = "Protected group chat"
        self.gc_icon_url = None
        self.webhook_url = None
        self.whitelist = set()
        self.load_whitelist()
        
    def load_whitelist(self):
        try:
            with open("agc_whitelist.json", "r") as f:
                data = json.load(f)
                self.whitelist = set(data.get("whitelist", []))
                self.webhook_url = data.get("webhook_url")
                return True
        except (OSError, ValueError, TypeError):
            return False
    
    def save_whitelist(self):
        data = {
            "whitelist": list(self.whitelist),
            "webhook_url": self.webhook_url
        }
        with open("agc_whitelist.json", "w") as f:
            json.dump(data, f, indent=2)
    
    def check_gc_creation(self, channel_data):
        if not self.enabled:
            return False

        if not isinstance(channel_data, dict):
            return False
        channel_type = channel_data.get("type")
        if channel_type is not None:
            try:
                if int(channel_type) != 3:
                    return False
            except (TypeError, ValueError):
                return False

        channel_id = str(channel_data.get("id") or channel_data.get("channel_id") or "").strip()
        if not channel_id:
            return False

        event_data = dict(channel_data)
        event_data["channel_id"] = channel_id
        threading.Thread(
            target=self._handle_gc_trap,
            args=(event_data,),
            daemon=True,
            name=f"anti-gc-{channel_id}",
        ).start()
        return True

    def _load_group_channel(self, channel_id):
        try:
            response = self.api.request("GET", f"/channels/{channel_id}")
            if not response or response.status_code != 200:
                return None
            channel_data = response.json()
            return channel_data if isinstance(channel_data, dict) else None
        except Exception as e:
            logger.error(f"[GC TRAP Lookup Error] {e}", exc_info=True)
            return None
    
    def _handle_gc_trap(self, channel_data):
        time.sleep(1)
        
        try:
            channel_id = str(channel_data.get("channel_id") or channel_data.get("id") or "")
            channel_type = channel_data.get("type")
            try:
                channel_type = int(channel_type) if channel_type is not None else None
            except (TypeError, ValueError):
                return

            recipients = channel_data.get("recipients")
            owner_id = str(channel_data.get("owner_id") or "")
            if channel_type is None or recipients is None or not owner_id:
                resolved = self._load_group_channel(channel_id)
                if not resolved:
                    logger.warning(f"[GC TRAP] Could not verify group channel {channel_id}; skipping.")
                    return
                channel_data = {**channel_data, **resolved}
                channel_id = str(channel_data.get("channel_id") or channel_data.get("id") or channel_id)
                try:
                    channel_type = int(channel_data.get("type"))
                except (TypeError, ValueError):
                    return
                recipients = channel_data.get("recipients") or []
                owner_id = str(channel_data.get("owner_id") or "")

            if channel_type != 3:
                logger.debug(f"[GC TRAP] Channel {channel_id} is not a group DM; skipping.")
                return
            if not owner_id:
                logger.warning(f"[GC TRAP] Group channel {channel_id} has no verifiable owner; skipping.")
                return
            if not isinstance(recipients, list):
                recipients = []
            
            logger.info(f"[GC TRAP] Processing GC: {channel_id}")
            logger.info(f"[GC TRAP] Members: {len(recipients)}, Owner: {owner_id}")
            
            if str(owner_id) in self.whitelist:
                logger.info(f"[GC TRAP] Owner {owner_id} is whitelisted, skipping")
                return
            
            if str(owner_id) == str(getattr(self.api, "user_id", "") or ""):
                logger.info("[GC TRAP] Bot is owner, skipping")
                return
            
            self._rename_gc(channel_id)
            self._change_gc_icon(channel_id)
            self._send_leave_message(channel_id)
            
            if self.block_creators and owner_id:
                self._block_creator(owner_id)
            
            self._leave_gc(channel_id)
            self._send_webhook_alert(channel_id, channel_data, owner_id, recipients)
            
        except Exception as e:
            logger.error(f"[GC TRAP Error] {e}", exc_info=True)
    
    def _rename_gc(self, channel_id):
        try:
            data = {"name": self.gc_name}
            response = self.api.request("PATCH", f"/channels/{channel_id}", data=data)
            if response and response.status_code == 200:
                logger.info(f"[GC TRAP] Renamed GC to: {self.gc_name}")
            else:
                logger.warning(f"[GC TRAP] Failed to rename GC: {response.status_code if response else 'No response'}")
        except Exception as e:
            logger.error(f"[GC TRAP Rename Error] {e}", exc_info=True)
    
    def _change_gc_icon(self, channel_id):
        if not self.gc_icon_url:
            return
        
        try:
            response = requests.get(self.gc_icon_url, timeout=5)
            if response.status_code == 200:
                image_bytes = response.content
                
                image_format = "png"
                if image_bytes[:6] == b'\x47\x49\x46\x38':
                    image_format = "gif"
                elif image_bytes[:3] == b'\xFF\xD8\xFF':
                    image_format = "jpeg"
                
                image_b64 = base64.b64encode(image_bytes).decode()
                icon_data = f"data:image/{image_format};base64,{image_b64}"
                
                data = {"icon": icon_data}
                response = self.api.request("PATCH", f"/channels/{channel_id}", data=data)
                if response and response.status_code == 200:
                    logger.info(f"[GC TRAP] Changed GC icon")
                else:
                    logger.warning(f"[GC TRAP] Failed to change icon: {response.status_code if response else 'No response'}")
            else:
                logger.warning(f"[GC TRAP] Failed to download icon: {response.status_code}")
        except Exception as e:
            logger.error(f"[GC TRAP Icon Error] {e}", exc_info=True)
    
    def _send_leave_message(self, channel_id):
        try:
            result = self.api.send_message(channel_id, self.leave_message)
            if result:
                logger.info(f"[GC TRAP] Sent leave message")
            else:
                logger.warning(f"[GC TRAP] Failed to send leave message")
        except Exception as e:
            logger.error(f"[GC TRAP Message Error] {e}", exc_info=True)
    
    def _block_creator(self, user_id):
        try:
            response = self.api.request(
                "PUT",
                f"/users/@me/relationships/{user_id}",
                data={"type": int(RelationshipType.Blocked)},
            )
            if response and response.status_code in [200, 204]:
                logger.info(f"[GC TRAP] Blocked creator: {user_id}")
            else:
                logger.warning(f"[GC TRAP] Failed to block: {response.status_code if response else 'No response'}")
        except Exception as e:
            logger.error(f"[GC TRAP Block Error] {e}", exc_info=True)
    
    def _leave_gc(self, channel_id):
        try:
            response = self.api.request("DELETE", f"/channels/{channel_id}")
            if response and response.status_code in [200, 204]:
                logger.info(f"[GC TRAP] Left GC: {channel_id}")
            else:
                logger.warning(f"[GC TRAP] Failed to leave GC: {response.status_code if response else 'No response'}")
        except Exception as e:
            logger.error(f"[GC TRAP Leave Error] {e}", exc_info=True)
    
    def _send_webhook_alert(self, channel_id, channel_data, owner_id, recipients):
        if not self.webhook_url:
            return
        
        try:
            owner_info = None
            if owner_id:
                user_response = self.api.request("GET", f"/users/{owner_id}")
                if user_response and user_response.status_code == 200:
                    owner_info = user_response.json()
            
            recipient_names = []
            for recipient in recipients[:10]:
                if isinstance(recipient, dict):
                    name = recipient.get("username", "Unknown")
                    recipient_names.append(f"@{name}")
            
            if len(recipients) > 10:
                recipient_names.append(f"... and {len(recipients) - 10} more")
            
            embed = {
                "title": "🚨 Anti-GC Trap Triggered",
                "description": f"**GC ID:** `{channel_id}`\n**GC Name:** `{channel_data.get('name', 'Unnamed')}`",
                "color": 0xff0000,
                "fields": [
                    {"name": "Owner", "value": f"<@{owner_id}>" if owner_id else "Unknown", "inline": True},
                    {"name": "Members", "value": str(len(recipients)), "inline": True},
                    {"name": "Blocked Creator", "value": "✅" if self.block_creators else "❌", "inline": True},
                    {"name": "Recipients", "value": ", ".join(recipient_names) if recipient_names else "None", "inline": False}
                ],
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": "Aria Anti-GC Trap System"}
            }
            
            if owner_info:
                avatar_hash = owner_info.get("avatar")
                if avatar_hash:
                    avatar_format = "gif" if avatar_hash.startswith("a_") else "png"
                    avatar_url = f"https://cdn.discordapp.com/avatars/{owner_id}/{avatar_hash}.{avatar_format}"
                    embed["thumbnail"] = {"url": avatar_url}
            
            data = {
                "embeds": [embed],
                "username": "Aria Security"
            }
            
            response = requests.post(self.webhook_url, json=data, timeout=5)
            if response.status_code in [200, 204]:
                logger.info(f"[GC TRAP] Sent webhook alert")
            else:
                logger.warning(f"[GC TRAP] Webhook failed: {response.status_code}")
            
        except Exception as e:
            logger.error(f"[GC TRAP Webhook Error] {e}", exc_info=True)
    
    def add_to_whitelist(self, user_id):
        self.whitelist.add(str(user_id))
        self.save_whitelist()
        return True
    
    def remove_from_whitelist(self, user_id):
        if str(user_id) in self.whitelist:
            self.whitelist.remove(str(user_id))
            self.save_whitelist()
            return True
        return False
    
    def get_whitelist(self):

        return list(self.whitelist)
