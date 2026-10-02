import discord
from discord.ext import commands, tasks
import time
from utils.general import is_valid_emoji, format_message, quote_block
from reply_helpers import ASCIIMixin
import traceback
import logging
import asyncio
import re

logger = logging.getLogger(__name__)

class Presence(commands.Cog, ASCIIMixin):
    def __init__(self, bot):
        self.bot = bot
        self.application_assets = {}  # Change to store per application ID
        self.external_asset_cache = {}  # Add this line
        self.rotation_task = None
        self.session = None
        self.discord_url_images = set()  # Track Discord CDN/media URLs for presence images
        logger.info("Presence cog initialized")

    async def cog_load(self):
        """Register event handlers when cog is loaded"""
        logger.info("Loading Presence cog...")
        event_manager = self.bot.get_cog('EventManager')
        if event_manager:
            event_manager.register_handler('on_ready', self.__class__.__name__, self._handle_ready)
            logger.info("Registered on_ready handler with event manager")
        else:
            logger.warning("EventManager not found, falling back to direct event listener")
            # If no event manager, add the listener directly
            self.bot.add_listener(self._handle_ready, 'on_ready')

        # Start the URL refresh task
        self.refresh_discord_urls_periodically.start()
        logger.info("Started Discord URL refresh task")

    async def _handle_ready(self):
        """Initialize presence when bot is ready"""
        logger.debug("Initializing presence...")
        if self.bot.is_closed():
            logger.debug("Bot is closed, skipping presence initialization")
            return
        
        # Cancel existing task first
        if self.rotation_task and not self.rotation_task.done():
            logger.debug("Cancelling existing rotation task")
            self.rotation_task.cancel()
            try:
                await self.rotation_task
            except asyncio.CancelledError:
                pass
        
        # Load config
        config = self.load_config()
        presence_config = config.get('presence', {})
        rotation_settings = presence_config.get('rotation', {})
        
        # Check if presence and rotation are enabled
        if presence_config.get('enabled', False) and rotation_settings.get('enabled', False):
            # Start rotation task if enabled
            if not self.rotation_task or self.rotation_task.done():
                self.rotation_task = asyncio.create_task(self.rotate_presence())
                logger.info("Started presence rotation task")
        else:
            # Just update regular presence if rotation is disabled
            await self.update_presence()
        
    async def fetch_application_assets(self, application_id: str):
        """Fetch assets for the application using discord.py-self's HTTP handler"""
        try:
            logger.debug(f"Fetching assets for application {application_id}")
            # Use the bot's HTTP handler which handles ratelimits properly
            # Route is not public, so use the endpoint string directly
            assets = await self.bot.http.request(
                'GET', f'/oauth2/applications/{application_id}/assets'
            )
            # Cache the assets per application ID
            self.application_assets[application_id] = {
                asset['name']: asset['id']
                for asset in assets
            }
            logger.info(f"Fetched {len(self.application_assets[application_id])} assets for app {application_id}")
            return True
        except Exception as e:
            logger.error(f"Error fetching application assets: {e}", exc_info=True)
        return False

    async def register_external_asset(self, image_url: str) -> str:
        """Register external asset using discord.py-self's HTTP handler, with Discord CDN/media URL support and refresh tracking."""
        try:
            # Check if it's a Discord CDN/media URL - convert directly to mp: format and track for refresh
            if image_url.startswith('https://cdn.discordapp.com/') or image_url.startswith('https://media.discordapp.net/'):
                self.discord_url_images.add(image_url)
                logger.debug(f"Detected Discord CDN URL: {image_url[:50]}...")
                # strip the base and return the remaining path with mp: prefix
                if image_url.startswith('https://cdn.discordapp.com/'):
                    image_url = image_url.replace('https://cdn.discordapp.com/', '')
                else:
                    image_url = image_url.replace('https://media.discordapp.net/', '')
                return f"mp:{image_url}"
            # For other URLs, use external asset registration
            app_id = self.bot.config_manager.presence.get('application_id') if self.bot.config_manager.presence else None
            logger.debug(f"Registering external asset: {image_url[:50]}... for app {app_id}")
            data = await self.bot.http.request(
                'POST', f'/applications/{app_id}/external-assets',
                json={'urls': [image_url]}
            )
            if data and len(data) > 0:
                logger.info(f"Registered external asset successfully")
                return f"mp:{data[0]['external_asset_path']}"
            logger.error("Empty response when registering external asset")
        except Exception as e:
            logger.error(f"Error registering external asset: {e}", exc_info=True)
        return None
    async def rotate_presence(self):
        """
        Rotates through different presence settings at specified intervals.
        Use periods (.) to separate values in name/state/details/custom_status.
        """
        try:
            name_index = state_index = details_index = custom_status_index = 0

            config = self.load_config()
            presence = config.get('presence', {})
            rotation_settings = presence.get('rotation', {})
            custom_status = presence.get('custom_status', {})
            custom_status_text = custom_status.get('text', '')
            emoji_data = custom_status.get('emoji', {})

            name_parts = presence.get('name', '').split('.') if '.' in presence.get('name', '') else [presence.get('name', '')]
            state_parts = presence.get('state', '').split('.') if '.' in presence.get('state', '') else [presence.get('state', '')]
            details_parts = presence.get('details', '').split('.') if '.' in presence.get('details', '') else [presence.get('details', '')]
            custom_status_parts = custom_status_text.split('.') if '.' in custom_status_text else [custom_status_text]
            rotation_delay = rotation_settings.get('delay', 60)

            while rotation_settings.get('enabled', False):
                current_name = name_parts[name_index % len(name_parts)] if len(name_parts) > 1 else name_parts[0]
                current_state = state_parts[state_index % len(state_parts)] if len(state_parts) > 1 else state_parts[0]
                current_details = details_parts[details_index % len(details_parts)] if len(details_parts) > 1 else details_parts[0]
                current_custom = custom_status_parts[custom_status_index % len(custom_status_parts)] if len(custom_status_parts) > 1 else custom_status_parts[0]

                custom_status_data = {'text': current_custom, 'emoji': emoji_data if emoji_data else None}
                await self.update_presence(name=current_name, state=current_state, details=current_details, custom_status=custom_status_data)

                if len(name_parts) > 1: name_index += 1
                if len(state_parts) > 1: state_index += 1
                if len(details_parts) > 1: details_index += 1
                if len(custom_status_parts) > 1: custom_status_index += 1

                await asyncio.sleep(rotation_delay)

                if (name_index + state_index + details_index) % 10 == 0:
                    config = self.load_config()
                    rotation_settings = config.get('presence', {}).get('rotation', {})

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Error in rotate_presence: %s", e)

    def is_discord_url_expired(self, url: str, offset_hours: int = 3) -> bool:
        """Check if a Discord CDN/media URL is expired based on ex= hex timestamp."""
        match = re.search(r'ex=([0-9a-fA-F]+)', url)
        if match:
            ex_hex = match.group(1)
            try:
                ex_unix = int(ex_hex, 16)
                now = int(time.time())
                # Offset: expire 3 hours before actual expiration
                offset = offset_hours * 3600
                return now > (ex_unix - offset)
            except Exception as e:
                logger.debug(f"Error checking URL expiration: {e}")
                return False
        return False

    @tasks.loop(hours=2)
    async def refresh_discord_urls_periodically(self):
        """Background task to refresh Discord CDN/media URLs every 2 hours."""
        try:
            if self.discord_url_images:
                # Filter to only Discord CDN/media URLs that need refreshing
                urls_to_refresh = []
                for url in list(self.discord_url_images):
                    # Only process Discord CDN/media URLs
                    if (url.startswith('https://cdn.discordapp.com/') or 
                        url.startswith('https://media.discordapp.net/')) and \
                       self.is_discord_url_expired(url, offset_hours=3):
                        urls_to_refresh.append(url)
                        
                if urls_to_refresh:
                    logger.info(f"Refreshing {len(urls_to_refresh)} Discord CDN/media URLs...")
                    # Send POST request to refresh URLs
                    refreshed = await self.refresh_discord_urls(urls_to_refresh)
                    
                    # Check if refresh was successful
                    if refreshed != urls_to_refresh:
                        # Update the set with new URLs
                        for old_url, new_url in zip(urls_to_refresh, refreshed):
                            # Handle case where new_url might be a dict from API response
                            if isinstance(new_url, dict):
                                new_url = new_url.get('refreshed', new_url.get('original', str(new_url)))
                            elif not isinstance(new_url, str):
                                new_url = str(new_url)
                                
                            if old_url != new_url:  # Only update if actually refreshed
                                self.discord_url_images.discard(old_url)
                                self.discord_url_images.add(new_url)
                                
                                # Update cache entries that use this URL
                                cache_keys_to_update = []
                                for cache_key in list(self.external_asset_cache.keys()):
                                    if old_url == cache_key:
                                        cache_keys_to_update.append(cache_key)
                                
                                for cache_key in cache_keys_to_update:
                                    # Remove old cache entry and add new one
                                    del self.external_asset_cache[cache_key]
                                    self.external_asset_cache[new_url] = await self.register_external_asset(new_url)
                                    logger.debug(f"Updated cache: {cache_key} -> {new_url}")
                    else:
                        logger.warning(f"Failed to refresh {len(urls_to_refresh)} URLs - using original URLs")
                
                # Clean up expired cache entries (only Discord URLs)
                await self.cleanup_expired_cache()
                
        except Exception as e:
            logger.error(f"Error in refresh_discord_urls_periodically: {e}", exc_info=True)

    async def refresh_discord_urls(self, urls):
        """Send POST to Discord API to refresh CDN/media URLs."""
        try:
            logger.debug(f"Refreshing {len(urls)} Discord URLs")
            response = await self.bot.http.request(
                discord.http.Route('POST', '/attachments/refresh-urls'),
                json={"attachment_urls": urls}
            )
            refreshed_urls = response.get('refreshed_urls', [])
            
            # Validate that we got the expected number of URLs back
            if len(refreshed_urls) != len(urls):
                logger.warning(f"Expected {len(urls)} refreshed URLs, got {len(refreshed_urls)}")
                # Pad with original URLs if needed
                while len(refreshed_urls) < len(urls):
                    refreshed_urls.append(urls[len(refreshed_urls)])
            
            # Log successful refreshes
            successful_refreshes = sum(1 for old, new in zip(urls, refreshed_urls) if old != new)
            if successful_refreshes > 0:
                logger.info(f"Successfully refreshed {successful_refreshes}/{len(urls)} URLs")
            
            return refreshed_urls
        except Exception as e:
            logger.error(f"Error refreshing Discord URLs: {e}", exc_info=True)
            return urls

    async def cleanup_expired_cache(self):
        """Remove expired Discord CDN/media URLs from external asset cache."""
        try:
            expired_keys = []
            for url in list(self.external_asset_cache.keys()):
                # Only clean up Discord CDN/media URLs
                if ((url.startswith('https://cdn.discordapp.com/') or 
                     url.startswith('https://media.discordapp.net/')) and
                    self.is_discord_url_expired(url, offset_hours=1)):  # More aggressive cleanup
                    expired_keys.append(url)
            
            for key in expired_keys:
                del self.external_asset_cache[key]
                logger.debug(f"Removed expired cache entry: {key}")
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}", exc_info=True)

    def load_config(self):
        config = {'presence': self.bot.config_manager.presence if self.bot.config_manager.presence else {}}
        return config
    
    async def save_config(self, config):
        """Save config file"""
        try:
            # Only save to this token's settings
            if not hasattr(self.bot.config_manager, 'presence') or self.bot.config_manager.presence is None:
                self.bot.config_manager.presence = {}
            self.bot.config_manager.presence = config['presence']
            await self.bot.config_manager.save_config_async()
            logger.debug("Presence config saved")
        except Exception as e:
            logger.error("Error saving config: %s", e)

    def is_enabled(self):
        """Check if rich presence is enabled"""
        config = self.load_config()
        if not config or 'presence' not in config:
            return False
        return config['presence'].get('enabled', False)

    # Map string types to ActivityType enum
    ACTIVITY_TYPES = {
        'playing': discord.ActivityType.playing,      # 0
        'streaming': discord.ActivityType.streaming,  # 1
        'listening': discord.ActivityType.listening,  # 2
        'watching': discord.ActivityType.watching,    # 3
        'competing': discord.ActivityType.competing,  # 5
        '0': discord.ActivityType.playing,
        '1': discord.ActivityType.streaming,
        '2': discord.ActivityType.listening,
        '3': discord.ActivityType.watching,
        '5': discord.ActivityType.competing
    }

    async def update_presence(self, status=None, name=None, state=None, details=None, custom_status=None):
        try:
            # check if bot is closed or disconnected
            if self.bot.is_closed() or not self.bot.is_ready():
                logger.debug("Bot not ready, skipping presence update")
                return

            config = self.load_config()
            presence_config = config.get('presence', {})
            
            # Determine status
            status_value = status.name.lower() if status else presence_config.get('status', 'dnd').lower()
            status = getattr(discord.Status, status_value, discord.Status.dnd)
            
            activities = []

            # Handle custom status input properly
            if isinstance(custom_status, str):
                # If custom_status is a string, use it directly as text
                custom_status_data = {'text': custom_status}
            else:
                # Otherwise use the config or passed dictionary
                custom_status_data = custom_status or presence_config.get('custom_status', {})
    
            # Add rich presence if enabled
            if presence_config.get('enabled'):

                # Use rotated values if provided, else use values from config
                name = name or presence_config.get('name', '')
                state = state or presence_config.get('state', '')
                details = details or presence_config.get('details', '')


                activity_type = str(presence_config.get('type', 'playing')).lower()
                activity_kwargs = {
                    'type': self.ACTIVITY_TYPES.get(activity_type.lower()) or self.ACTIVITY_TYPES.get(activity_type) or discord.ActivityType.playing,
                    'name': name,
                    'state': state,
                    'details': details if activity_type not in ['streaming', '1'] else None,
                }

                if app_id := presence_config.get('application_id'):
                    try:
                        activity_kwargs['application_id'] = int(app_id)
                        if app_id not in self.application_assets:
                            await self.fetch_application_assets(app_id)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid application_id '{app_id}', must be a valid integer. Skipping application_id.")

                # Only add URL if type is streaming (either by name or number)
                if (activity_type == 'streaming' or activity_type == '1') and presence_config.get('url'):
                    activity_kwargs['url'] = presence_config['url']
    
                # Handle assets
                assets = {}
                app_assets = self.application_assets.get(app_id, {})

                # Handle large image
                if large_image := presence_config.get('large_image'):
                    # If dict, extract the URL or asset name
                    if isinstance(large_image, dict):
                        large_image_val = large_image.get('url') or large_image.get('name') or str(large_image)
                    else:
                        large_image_val = large_image
                    
                    # Ensure large_image_val is a string
                    if not isinstance(large_image_val, str):
                        logger.error(f"Invalid large_image_val type: {type(large_image_val)} - {large_image_val}")
                        large_image_val = str(large_image_val)
                    
                    if large_image_val.startswith(('http://', 'https://')):
                        # Check cache first, refresh if expired
                        if large_image_val not in self.external_asset_cache or self.is_discord_url_expired(large_image_val, offset_hours=3):
                            if self.is_discord_url_expired(large_image_val, offset_hours=3):
                                refreshed = await self.refresh_discord_urls([large_image_val])
                                if refreshed and len(refreshed) > 0:
                                    new_url = refreshed[0]
                                    # Handle Discord API response format
                                    if isinstance(new_url, dict):
                                        logger.debug(f"API returned refresh dict: {new_url}")
                                        new_url = new_url.get('refreshed', new_url.get('original', str(new_url)))
                                    elif not isinstance(new_url, str):
                                        new_url = str(new_url)
                                    
                                    if new_url != large_image_val:
                                        # Remove old cache entry if URL changed
                                        self.external_asset_cache.pop(large_image_val, None)
                                        large_image_val = new_url
                            self.external_asset_cache[large_image_val] = await self.register_external_asset(large_image_val)
                        assets['large_image'] = self.external_asset_cache[large_image_val]
                    else:
                        assets['large_image'] = app_assets.get(large_image_val, large_image_val)

                # Handle small image 
                if small_image := presence_config.get('small_image'):
                    if isinstance(small_image, dict):
                        small_image_val = small_image.get('url') or small_image.get('name') or str(small_image)
                    else:
                        small_image_val = small_image
                    
                    # Ensure small_image_val is a string
                    if not isinstance(small_image_val, str):
                        logger.error(f"Invalid small_image_val type: {type(small_image_val)} - {small_image_val}")
                        small_image_val = str(small_image_val)
                    
                    if small_image_val.startswith(('http://', 'https://')):
                        # Check cache first, refresh if expired
                        if small_image_val not in self.external_asset_cache or self.is_discord_url_expired(small_image_val, offset_hours=3):
                            if self.is_discord_url_expired(small_image_val, offset_hours=3):
                                refreshed = await self.refresh_discord_urls([small_image_val])
                                if refreshed and len(refreshed) > 0:
                                    new_url = refreshed[0]
                                    # Handle Discord API response format
                                    if isinstance(new_url, dict):
                                        logger.debug(f"API returned refresh dict: {new_url}")
                                        new_url = new_url.get('refreshed', new_url.get('original', str(new_url)))
                                    elif not isinstance(new_url, str):
                                        new_url = str(new_url)
                                    
                                    if new_url != small_image_val:
                                        # Remove old cache entry if URL changed
                                        self.external_asset_cache.pop(small_image_val, None)
                                        small_image_val = new_url
                            self.external_asset_cache[small_image_val] = await self.register_external_asset(small_image_val)
                        assets['small_image'] = self.external_asset_cache[small_image_val]
                    else:
                        assets['small_image'] = app_assets.get(small_image_val, small_image_val)

                if assets:
                    activity_kwargs['assets'] = assets
    
                # Add timestamps
                if self.bot.start_time:
                    activity_kwargs['timestamps'] = {'start': int(self.bot.start_time * 1000)}
    
                # Handle buttons
                buttons = []
                if button1 := presence_config.get('button1'):
                    buttons.append(button1)
                if button2 := presence_config.get('button2'):
                    buttons.append(button2)
                if buttons:
                    activity_kwargs['buttons'] = buttons
                    activity_kwargs['session_id'] = self.bot.ws.session_id
                    activity_kwargs["application_id"] = activity_kwargs.get("application_id", "1")
                    
                    # Add metadata with button URLs to make buttons clickable
                    button_urls = []
                    if url1 := presence_config.get('url1'):
                        button_urls.append(url1)
                    elif len(buttons) > 0:
                        button_urls.append("")  # Empty placeholder if url1 not specified
                        
                    if url2 := presence_config.get('url2'):
                        button_urls.append(url2)
                    elif len(buttons) > 1:
                        button_urls.append("")  # Empty placeholder if url2 not specified
                        
                    activity_kwargs['metadata'] = {
                        "button_urls": button_urls
                    }
    
                # Add party info
                if presence_config.get('party_id') or (presence_config.get('party_size') and presence_config.get('party_max')):
                    party = {}
                    if party_id := presence_config.get('party_id'):
                        party['id'] = party_id
                    if party_size := presence_config.get('party_size'):
                        party['size'] = [int(party_size), int(presence_config.get('party_max', party_size))]
                    activity_kwargs['party'] = party
    
                activities.append(discord.Activity(**activity_kwargs))
    
            # Set custom status if configured
            if custom_status_data:
                emoji = None
                if emoji_data := custom_status_data.get('emoji'):
                    emoji = discord.PartialEmoji(name=emoji_data.get('name'), id=emoji_data.get('id'))
                activities.append(discord.CustomActivity(
                    name=custom_status_data.get('text', ''),
                    emoji=emoji
                ))
            try:
                # Update presence with all activities
                await self.bot.change_presence(status=status, activities=activities, afk=True)
                logger.debug(f"Presence updated: {len(activities)} activities")
            except (discord.HTTPException, discord.GatewayNotFound, discord.ConnectionClosed, discord.ClientException) as e:
                # log but don't raise - connection issues are expected sometimes
                logger.error(f"Connection error updating presence: {e}")
                return

    
        except Exception as e:
            logger.error(f"Error updating presence: {e}")
            logger.debug("".join(traceback.format_exc()))

    @commands.command(aliases=['rp'])
    async def presence(self, ctx, setting=None, *, value=None):
        """Rich presence settings
        presence true - Enable/disable
        presence name Game - Set activity name
        presence type streaming - Set activity type"""
        try:
            await ctx.message.delete()
        except:
            pass

        config = self.load_config()
        if not config:
            config = {}
        if 'presence' not in config:
            config['presence'] = {}
        presence_config = config['presence']

        if not setting:
            await ctx.send(
                format_message("Please specify a setting to modify"),
                delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
            )
            return

        if setting.lower() in ['true', 'false', 'on', 'off']:
            new_state = setting.lower() in ['true', 'on']
            current_state = presence_config.get('enabled', False)
            
            if new_state == current_state:
                state_word = "enabled" if new_state else "disabled"
                await ctx.send(
                    format_message(f"Presence is already {state_word}"),
                    delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
                )
                return
                
            presence_config['enabled'] = new_state
            logger.info(f"Presence {'enabled' if new_state else 'disabled'}")

            # if disabling presence, also disable rotation
            if not presence_config['enabled']:
                if 'rotation' in presence_config:
                    presence_config['rotation']['enabled'] = False
                if self.rotation_task and not self.rotation_task.done():
                    self.rotation_task.cancel()
                    self.rotation_task = None

            await self.save_config(config)
            if presence_config['enabled']:
                self.start_time = int(time.time())
            await self.update_presence()
            msg = "Presence enabled" if presence_config['enabled'] else "Presence disabled"
            await ctx.send(
                format_message(msg),
                delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
            )
            return

        valid_settings = [
            'name', 'details', 'state', 'large_image', 'large_text',
            'small_image', 'small_text', 'button1', 'url1', 'button2', 
            'url2', 'application_id', 'party_id', 'party_size', 'party_max',
            'type', 'url'
        ]

        if setting not in valid_settings:
            msg = f"Invalid setting. Valid settings are: {', '.join(valid_settings)}"
            await ctx.send(
                format_message(msg),
                delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
            )
            return

        # Basic URL validation for streaming URL
        if setting == 'url':
            if value and not value.startswith(('http://', 'https://')):
                await ctx.send(
                    format_message("Invalid URL. Must start with http:// or https://"),
                    delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
                )
                return

        # Handle clearing values for all valid settings
        if value and value.lower() in ['none', 'clear', 'reset']:
            if setting in presence_config:
                del presence_config[setting]
                await self.save_config(config)
                await self.update_presence()
                logger.info(f"Cleared presence setting: {setting}")
                await ctx.send(
                    format_message(f"Cleared {setting} value"),
                    delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
                )
                return
            else:
                await ctx.send(
                    format_message(f"{setting} was already empty."),
                    delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
                )
                return

        if not value:
            await ctx.send(
                format_message("Please provide a value"),
                delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
            )
            return

        if setting in ['large_image', 'small_image']:
            if value:
                # Only check assets if we have an application ID
                if presence_config.get('application_id'):
                    await self.fetch_application_assets(presence_config['application_id'])
                    is_asset = value in self.application_assets.get(presence_config['application_id'], {})
                    is_url = value.startswith(('http://', 'https://'))
                    
                    if not (is_asset or is_url):
                        available_assets = ", ".join(self.application_assets.get(presence_config['application_id'], {}).keys())
                        await ctx.send(
                            format_message(
                                f"'{value}' is not a valid asset name or URL! Available assets: {available_assets}\n"
                                "You can also use direct image URLs starting with http:// or https://"
                            ),
                            delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
                        )
                        return
                # Only validate URL format if no application ID
                elif not value.startswith(('http://', 'https://')):
                    await ctx.send(
                        format_message("Please provide a direct image URL starting with http:// or https://"),
                        delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
                    )
                    return
                # tell the user to set the application ID if they want to use assets
                elif not presence_config.get('application_id'):
                    await ctx.send(
                        format_message("Cannot use assets without an application ID. Set the application ID first!"),
                        delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
                    )
                    return

            presence_config[setting] = value
            await self.save_config(config)

        presence_config[setting] = value
        await self.save_config(config)
        logger.info(f"Updated presence setting: {setting} = {value}")
        
        # Check if rotation is enabled 
        rotation_settings = presence_config.get('rotation', {})
        if rotation_settings.get('enabled', False):
            # Restart the rotation task to pick up new settings
            if self.rotation_task and not self.rotation_task.done():
                self.rotation_task.cancel()
            self.rotation_task = asyncio.create_task(self.rotate_presence())
        else:
            # Update regular presence if rotation disabled
            await self.update_presence()

        msg = f"Updated {setting} to: {value}"
        await ctx.send(
            format_message(msg),
            delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None
        )

    @commands.command(aliases=['rt'])
    async def rotation(self, ctx, setting=None, delay: int = None):
        """Presence rotation settings
        rotation on/off - Enable or disable rotation
        rotation delay <seconds> - Set rotation interval (min 5s)
        rotation - Show current status"""
        try: await ctx.message.delete()
        except: pass

        config = self.load_config()
        if 'presence' not in config:
            config['presence'] = {}
        if 'rotation' not in config['presence']:
            config['presence']['rotation'] = {'enabled': False, 'delay': 60}

        if not config['presence'].get('enabled', False):
            await ctx.send(format_message("Presence must be enabled first"),
                delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None)
            return

        if setting in ['on', 'off']:
            config['presence']['rotation']['enabled'] = setting == 'on'
            await self.save_config(config)
            if setting == 'on':
                if self.rotation_task and not self.rotation_task.done():
                    self.rotation_task.cancel()
                self.rotation_task = asyncio.create_task(self.rotate_presence())
            elif setting == 'off' and self.rotation_task and not self.rotation_task.done():
                self.rotation_task.cancel()
                self.rotation_task = None
                await self.update_presence()
            msg = f"Presence rotation {'enabled' if setting == 'on' else 'disabled'}"

        elif setting == 'delay' and delay is not None:
            if delay < 5:
                await ctx.send(format_message("Delay must be at least 5 seconds"),
                    delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None)
                return
            config['presence']['rotation']['delay'] = delay
            await self.save_config(config)
            if config['presence']['rotation']['enabled']:
                if self.rotation_task and not self.rotation_task.done():
                    self.rotation_task.cancel()
                self.rotation_task = asyncio.create_task(self.rotate_presence())
            msg = f"Rotation delay set to {delay} seconds"

        else:
            rotation = config['presence'].get('rotation', {})
            msg = f"Rotation is {'enabled' if rotation.get('enabled') else 'disabled'} with {rotation.get('delay', 60)}s delay"

        await ctx.send(format_message(msg),
            delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None)

    @commands.command()
    async def dnd(self, ctx):
        """Set status to Do Not Disturb"""
        try: await ctx.message.delete()
        except: pass
        await self.update_presence(status=discord.Status.dnd)
        await ctx.send(format_message("Status set to Do Not Disturb"),
            delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None)

    @commands.command()
    async def idle(self, ctx):
        """Set status to Idle"""
        try: await ctx.message.delete()
        except: pass
        await self.update_presence(status=discord.Status.idle)
        await ctx.send(format_message("Status set to Idle"),
            delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None)

    @commands.command()
    async def online(self, ctx):
        """Set status to Online"""
        try: await ctx.message.delete()
        except: pass
        await self.update_presence(status=discord.Status.online)
        await ctx.send(format_message("Status set to Online"),
            delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None)

    @commands.command()
    async def invisible(self, ctx):
        """Set status to Invisible"""
        try: await ctx.message.delete()
        except: pass
        await self.update_presence(status=discord.Status.invisible)
        await ctx.send(format_message("Status set to Invisible"),
            delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None)

    @commands.command(aliases=['st', 'setstatus'])
    async def state(self, ctx, status_type: str = None):
        """Set online state: online / idle / dnd / invisible"""
        try: await ctx.message.delete()
        except: pass

        valid_statuses = ['online', 'idle', 'dnd', 'invisible']
        if not status_type or status_type.lower() not in valid_statuses:
            await ctx.send(format_message(f"Invalid status. Use: {', '.join(valid_statuses)}"),
                delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None)
            return

        config = self.load_config()
        if 'presence' not in config:
            config['presence'] = {}
        config['presence']['status'] = status_type.lower()
        await self.save_config(config)

        rotation_settings = config['presence'].get('rotation', {})
        if rotation_settings.get('enabled', False):
            if self.rotation_task and not self.rotation_task.done():
                self.rotation_task.cancel()
            self.rotation_task = asyncio.create_task(self.rotate_presence())
        else:
            await self.update_presence()

        await ctx.send(format_message(f"Status set to: {status_type}"),
            delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None)

    @commands.command(aliases=['setbrowser'])
    async def browser(self, ctx, *, browser_type: str = None):
        """Change Discord client type
        browser android / desktop / web / embedded"""
        try: await ctx.message.delete()
        except: pass

        if not browser_type:
            await ctx.send(format_message("Specify a browser type: android, embedded, desktop, web"),
                delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else 5)
            return

        browser_map = {
            'android': 'Discord Android',
            'embedded': 'Discord Embedded',
            'desktop': 'Discord Client',
            'web': 'Discord Web',
        }
        browser_type_lower = browser_type.lower()
        if browser_type_lower not in browser_map:
            valid_types = ', '.join(f'`{k}`' for k in browser_map)
            await ctx.send(f"Invalid browser type: `{browser_type}`\nValid types: {valid_types}",
                delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else 5)
            return

        browser_value = browser_map[browser_type_lower]
        if browser_value == getattr(self.bot, 'current_browser', None):
            await ctx.send(f"Already using browser property: `{browser_value}`",
                delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else 5)
            return

        temp_msg = await ctx.send(f"\U0001f504 Changing browser property to: `{browser_value}`...", delete_after=15)
        self.bot.current_browser = browser_value
        try:
            current_status = self.bot.status
            current_activities = self.bot.activities
            await temp_msg.edit(content=f"\U0001f50c Disconnecting to apply browser change to `{browser_value}`...")
            if self.bot.ws and self.bot.ws.open:
                await self.bot.ws.close(code=1000, reason=f"Browser switch -> {browser_value}")
            await asyncio.sleep(2)
            await temp_msg.edit(content=f"\u23f3 Waiting for reconnection with `{browser_value}` browser property...")
            await asyncio.sleep(3)
            try:
                await self.bot.change_presence(status=current_status, activities=current_activities)
            except Exception:
                pass
            await temp_msg.edit(content=f"\u2705 Browser property changed to: `{browser_value}`")
        except Exception as e:
            logger.error(f"Error during browser property change: {e}")
            await temp_msg.edit(content=f"\u26a0\ufe0f Error changing browser property: `{str(e)[:100]}`")

    @commands.command(aliases=['cs', 'customstatus'])
    async def status(self, ctx, *, content: str = None):
        """Set custom status
        status hello world - Set status text
        status \U0001f4bb Working - With emoji
        status clear - Remove status"""
        try: await ctx.message.delete()
        except: pass

        config = self.load_config()
        if 'presence' not in config:
            config['presence'] = {}

        if not content or content.lower() == 'clear':
            config['presence']['custom_status'] = {}
            await self.save_config(config)
            rotation_settings = config['presence'].get('rotation', {})
            if rotation_settings.get('enabled', False):
                if self.rotation_task and not self.rotation_task.done():
                    self.rotation_task.cancel()
                self.rotation_task = asyncio.create_task(self.rotate_presence())
            elif config['presence'].get('enabled', False):
                await self.update_presence()
            await ctx.send(format_message("Custom status cleared"),
                delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None)
            return

        parts = content.split(maxsplit=1)
        first_part = parts[0]
        text = content
        emoji = None

        if 'custom_status' not in config['presence']:
            config['presence']['custom_status'] = {}

        if first_part.startswith(('<:', '<a:')):
            try:
                emoji_parts = first_part.split(':')
                emoji = discord.PartialEmoji(name=emoji_parts[1], id=int(emoji_parts[2].strip('>')))
                text = parts[1] if len(parts) > 1 else ''
                config['presence']['custom_status'].update({'text': text, 'emoji': {'name': emoji.name, 'id': str(emoji.id)}})
            except Exception:
                config['presence']['custom_status'].update({'text': content, 'emoji': None})
        elif len(first_part) == 1 and not first_part.isalnum() and is_valid_emoji(first_part):
            emoji = discord.PartialEmoji(name=first_part)
            text = parts[1] if len(parts) > 1 else ''
            config['presence']['custom_status'].update({'text': text, 'emoji': {'name': emoji.name, 'id': None}})
        else:
            config['presence']['custom_status'].update({'text': content, 'emoji': None})

        await self.save_config(config)

        rotation_settings = config['presence'].get('rotation', {})
        if rotation_settings.get('enabled', False):
            if self.rotation_task and not self.rotation_task.done():
                self.rotation_task.cancel()
            self.rotation_task = asyncio.create_task(self.rotate_presence())
        elif config['presence'].get('enabled', False):
            await self.update_presence()

        status_display = []
        if emoji: status_display.append(first_part)
        if text: status_display.append(text)
        await ctx.send(format_message(f"Custom status set to: {' '.join(status_display)}"),
            delete_after=self.bot.config_manager.auto_delete.delay if self.bot.config_manager.auto_delete.enabled else None)

    async def cog_unload(self):
        """Cleanup when cog is unloaded"""
        logger.info("Unloading Presence cog...")
        # Unregister from event manager
        event_manager = self.bot.get_cog('EventManager')
        if event_manager:
            event_manager.unregister_handler('on_ready', self.__class__.__name__)
            logger.info("Unregistered from event manager")
        if self.session:
            await self.session.close()
        if self.rotation_task:
            self.rotation_task.cancel()
            try:
                await self.rotation_task
            except asyncio.CancelledError:
                pass
        # Stop the refresh task
        self.refresh_discord_urls_periodically.cancel()
        # Reset presence to default
        try:
            await self.update_presence(activity=None)
        except:
            pass
        logger.info("Presence cog unloaded")

async def setup(bot):
    await bot.add_cog(Presence(bot))
    logger.info("Presence cog setup completed")
