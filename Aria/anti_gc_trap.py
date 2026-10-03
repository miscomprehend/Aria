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
        
        logger.debug(f"[GC TRAP DEBUG] Checking channel data")
        
        channel_type = channel_data.get("type", 0)
        channel_id = channel_data.get("channel_id", "")
        
        if channel_type != 3:
            return False
        
        if not channel_id:
            return False
        
        
        threading.Thread(target=self._handle_gc_trap, args=(channel_data,), daemon=True).start()
        return True
    
    def _handle_gc_trap(self, channel_data):
        time.sleep(1)
        
        try:
            channel_id = channel_data.get("channel_id")
            recipients = channel_data.get("recipients", [])
            owner_id = channel_data.get("owner_id", "")
            
            logger.info(f"[GC TRAP] Processing GC: {channel_id}")
            logger.info(f"[GC TRAP] Members: {len(recipients)}, Owner: {owner_id}")
            
            if not recipients or len(recipients) <= 1:
                logger.info("[GC TRAP] Not enough recipients")
                return
            
            if str(owner_id) in self.whitelist:
                logger.info(f"[GC TRAP] Owner {owner_id} is whitelisted, skipping")
                return
            
            if owner_id == self.api.user_id:
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
