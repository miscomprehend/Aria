import time
import random
import json
import base64
import ssl
import re
import hashlib
from typing import Dict, Any, Optional

# Try to import curl_cffi, fallback to requests if not available
try:
    from curl_cffi.requests import Session, Response
    import curl_cffi.requests as _http
except ImportError:
    try:
        import requests as _http
        Session = _http.Session
        Response = _http.Response
    except ImportError:
        _http = None
        Session = None
        Response = None


_FALLBACK_BUILD = 305411  # April 2026 stable


def get_latest_build() -> int:
    """Fetch the current Discord client build number from public JS assets.

    Returns the fallback build number if the fetch fails for any reason.
    """
    try:
        import requests as _req  # use plain requests to avoid circular session issues
    except ImportError:
        return _FALLBACK_BUILD

    try:
        resp = _req.get("https://discord.com", timeout=10,
                        headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return _FALLBACK_BUILD

        # Find JS asset filenames from the HTML
        assets = re.findall(r'assets/([a-z0-9]+)\.js', resp.text)
        if not assets:
            return _FALLBACK_BUILD

        # Walk the last few bundles — build number lives in one of them
        for asset in reversed(assets[-8:]):
            try:
                js = _req.get(f"https://discord.com/assets/{asset}.js",
                              timeout=10,
                              headers={"User-Agent": "Mozilla/5.0"}).text
                m = re.search(r'buildNumber["\s]*:["\s]*(\d{5,6})', js)
                if m:
                    build = int(m.group(1))
                    print(f"[BUILD] Detected Discord build: {build}")
                    return build
            except Exception:
                continue

        return _FALLBACK_BUILD
    except Exception as e:
        print(f"[BUILD] Fetch failed, using fallback {_FALLBACK_BUILD}: {e}")
        return _FALLBACK_BUILD

class RateLimiter:
    """Advanced rate limiter with bucket management and DM protection"""

    def __init__(self):
        self.buckets: Dict[str, Dict[str, Any]] = {}
        self.dm_protection: Dict[str, float] = {}
        self.client_rate_limits: Dict[str, Dict[str, Any]] = {}

    def parse_bucket_hash(self, headers: Dict[str, str]) -> str:
        """Parse bucket hash from response headers"""
        return headers.get("X-RateLimit-Bucket", "global")

    def update_bucket(self, bucket_hash: str, headers: Dict[str, str]):
        """Update bucket information from response headers"""
        if bucket_hash not in self.buckets:
            self.buckets[bucket_hash] = {}

        bucket = self.buckets[bucket_hash]
        bucket.update({
            "limit": int(headers.get("X-RateLimit-Limit", 5)),
            "remaining": int(headers.get("X-RateLimit-Remaining", 5)),
            "reset": float(headers.get("X-RateLimit-Reset", time.time() + 1)),
            "reset_after": float(headers.get("X-RateLimit-Reset-After", 1.0))
        })

    def should_wait(self, bucket_hash: str) -> Optional[float]:
        """Check if we should wait before making a request"""
        if bucket_hash not in self.buckets:
            return None

        bucket = self.buckets[bucket_hash]
        now = time.time()

        if bucket.get("remaining", 5) <= 0:
            reset_time = bucket.get("reset", now + 1)
            if now < reset_time:
                return reset_time - now

        return None

    def decrement(self, bucket_hash: str):
        """Decrement remaining requests for a bucket"""
        if bucket_hash in self.buckets:
            self.buckets[bucket_hash]["remaining"] = max(0, self.buckets[bucket_hash].get("remaining", 5) - 1)

    def handle_429(self, headers: Dict[str, str], endpoint: str) -> float:
        """Handle 429 response and return retry time"""
        bucket_hash = self.parse_bucket_hash(headers)
        self.update_bucket(bucket_hash, headers)
        retry_after = float(headers.get("Retry-After", "1.0"))
        return retry_after + random.uniform(0.5, 2.0)

    def check_dm_protection(self, channel_id: str) -> Optional[float]:
        """Check DM-specific rate limiting"""
        if not channel_id:
            return None

        now = time.time()
        last_message = self.dm_protection.get(channel_id, 0)

        if now - last_message < 2.0:
            return 2.0 - (now - last_message)

        self.dm_protection[channel_id] = now
        return None

    def get_wait_time(self, endpoint: str) -> Optional[float]:
        """Get wait time for endpoint"""
        bucket_hash = self.parse_bucket_hash({})
        return self.should_wait(bucket_hash)


class BrowserProfile:
    """Enhanced browser profile for spoofing with modern browsers and better randomization"""

    def __init__(self):
        timestamp = int(time.time())
        random.seed(timestamp % 1000)

        # Chrome versions (2025-2026)
        self.chrome_versions = [
            {"major": "124", "full": "124.0.0.0"},
            {"major": "135", "full": "135.0.7049.115"},
            {"major": "134", "full": "134.0.6998.117"},
            {"major": "133", "full": "133.0.6943.141"},
            {"major": "132", "full": "132.0.6834.160"},
            {"major": "131", "full": "131.0.6778.264"},
        ]

        # Edge (Chromium-based) versions (2025-2026)
        self.edge_versions = [
            {"major": "135", "full": "135.0.3179.98"},
            {"major": "134", "full": "134.0.3124.83"},
            {"major": "133", "full": "133.0.3065.92"},
        ]

        # Firefox versions on Linux (inspired by headerspoofer-discord-plugin)
        self.firefox_versions = [
            {"major": "136", "full": "136.0"},
            {"major": "135", "full": "135.0.1"},
            {"major": "134", "full": "134.0.2"},
            {"major": "133", "full": "133.0"},
        ]

        # Linux distros for Firefox spoofing
        self.linux_distros = [
            "Ubuntu 24.04",
            "Ubuntu 22.04",
            "Debian 12",
            "Fedora 41",
        ]

        # Browser rotation: Chrome (Windows), Edge (Windows), Firefox (Linux), Firefox (macOS)
        browser_choice = random.choice([
            "chrome", "chrome", "chrome",
            "edge",
            "firefox_linux", "firefox_linux",
            "firefox_mac",
        ])

        self.is_firefox = browser_choice.startswith("firefox")

        if browser_choice == "edge":
            version_idx = random.randint(0, len(self.edge_versions) - 1)
            browser = self.edge_versions[version_idx]
            self.browser_version = browser['full']
            browser_full = f"Edg/{browser['full']}"
            ua_template = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser['full']} Safari/537.36 {browser_full}"
            self.browser = "Edge"
            self.os = "Windows"
            self.os_version = "10"
            self.platform = "Win32"
        elif browser_choice == "firefox_linux":
            version_idx = (timestamp // 3600) % len(self.firefox_versions)
            browser = self.firefox_versions[version_idx]
            self.browser_version = browser['full']
            distro = random.choice(self.linux_distros)
            self.linux_distro = distro
            ua_template = f"Mozilla/5.0 (X11; Linux x86_64; rv:{browser['major']}.0) Gecko/20100101 Firefox/{browser['full']}"
            self.browser = "Firefox"
            self.os = "Linux"
            self.os_version = distro
            self.platform = "Linux x86_64"
        elif browser_choice == "firefox_mac":
            version_idx = (timestamp // 3600) % len(self.firefox_versions)
            browser = self.firefox_versions[version_idx]
            self.browser_version = browser['full']
            ua_template = f"Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:{browser['major']}.0) Gecko/20100101 Firefox/{browser['full']}"
            self.browser = "Firefox"
            self.os = "Mac OS X"
            self.os_version = "14.7"
            self.platform = "MacIntel"
        else:
            version_idx = (timestamp // 3600) % len(self.chrome_versions)
            browser = self.chrome_versions[version_idx]
            self.browser_version = browser['full']
            ua_template = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser['full']} Safari/537.36"
            self.browser = "Chrome"
            self.os = "Windows"
            self.os_version = "10"
            self.platform = "Win32"

        # Randomize window size for more natural spoofing
        screen_sizes = [
            "1920x1080",
            "1680x1050", 
            "1440x900",
            "1366x768",
            "2560x1440",
            "1920x1200",
            "2560x1600",
        ]

        locations = [
            {"timezone": "America/New_York", "locale": "en-US"},
            {"timezone": "America/Chicago", "locale": "en-US"},
            {"timezone": "America/Denver", "locale": "en-US"},
            {"timezone": "America/Los_Angeles", "locale": "en-US"},
            {"timezone": "America/Phoenix", "locale": "en-US"},
            {"timezone": "Europe/London", "locale": "en-GB"},
            {"timezone": "America/Toronto", "locale": "en-CA"},
            {"timezone": "Australia/Sydney", "locale": "en-AU"},
        ]

        location_idx = timestamp % len(locations)
        location = locations[location_idx]

        self.user_agent = ua_template
        self.locale = location['locale']
        self.timezone = location['timezone']
        self.screen_resolution = random.choice(screen_sizes)
        self.hardware_concurrency = random.choice([4, 8, 16])
        self.device_memory = random.choice([4, 8, 16, 32])

        width, height = map(int, self.screen_resolution.split("x"))
        self.viewport_width = str(max(800, width - random.randint(0, 280)))
        self.viewport_height = str(max(600, height - random.randint(100, 220)))
        self.dpr = random.choice(["1", "1.25", "1.5", "2", "2.5", "3"])

        self.sec_fetch_dest = "empty"
        self.sec_fetch_mode = "cors"
        self.sec_fetch_site = "same-origin"
        self.ect = random.choice(["4g", "4g", "3g"])
        self.downlink = str(random.choice([10.0, 15.0, 20.0, 30.0]))
        self.rtt = str(random.choice([20, 30, 40, 50]))
        self.save_data = "off"

        self.sec_ch_ua = None
        self.sec_ch_ua_mobile = "?0"
        self.sec_ch_ua_platform = f'"{self.os}"'
        self.sec_ch_ua_platform_version = "0.0.0"
        self.sec_ch_ua_full_version = f'"{self.browser_version}"'
        self.sec_ch_ua_arch = random.choice(["x86", "x86_64"])
        self.sec_ch_ua_bitness = "64"
        self.sec_ch_ua_model = ""
        self.sec_ch_ua_form_factor = "Desktop"
        self.sec_ch_prefers_color_scheme = "light"
        self.sec_ch_prefers_reduced_motion = "no-preference"

        if not self.is_firefox:
            major = self.browser_version.split('.')[0]
            self.sec_ch_ua = f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not(A:Brand";v="99"'
            if self.os == "Windows":
                self.sec_ch_ua_platform_version = "10.0.0"
            elif self.os == "Mac OS X":
                self.sec_ch_ua_platform_version = "14.7.0"
            else:
                self.sec_ch_ua_platform_version = "0.0.0"

        self.custom_headers = []
        self.x_forwarded_for = self._generate_random_ip()
        self.x_real_ip = self._generate_random_ip()
        self.cf_connecting_ip = self._generate_random_ip()
        self.true_client_ip = self._generate_random_ip()

    def _generate_random_ip(self) -> str:
        """Generate a realistic public IPv4 address for spoofed IP headers."""
        first_octets = [13, 34, 44, 52, 54, 63, 66, 68, 70, 72, 73, 74, 75, 76, 96, 98, 99, 100, 104, 107,
                        108, 128, 129, 130, 131, 132, 134, 135, 143, 144, 147, 148, 150, 151, 152, 153, 154,
                        155, 156, 157, 158, 159, 162, 163, 164, 165, 167, 168, 169, 170, 172, 173, 174, 175,
                        176, 177, 178, 184, 185, 186, 187, 188, 189, 190, 191, 193, 194, 195, 196, 197, 198,
                        199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 216, 217, 218, 219, 220, 221,
                        222, 223]
        first = random.choice(first_octets)
        return f"{first}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


class HeaderSpoofer:
    """Main header spoofer for Discord"""

    def __init__(self):
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.fingerprint: str = ""
        self.cookies: str = ""
        self.cache_time: float = 0
        self.profile = BrowserProfile()
        self.build_number = get_latest_build()  # Fetched live; falls back to 305124
        self._cached_super_properties: Optional[str] = None  # Stable per session
        self._cached_super_properties_hash: Optional[str] = None
        self.session: Any = self._create_session()
        self.proxy_manager = None
        self._init_proxy_manager()

    def _init_proxy_manager(self):
        """Initialize proxy manager"""
        try:
            from proxy_manager import ProxyManager
            self.proxy_manager = ProxyManager()
        except:
            self.proxy_manager = None

    def _choose_tls_impersonation(self) -> str:
        """Choose the closest available curl_cffi Chrome impersonation.

        Matching the TLS impersonation to the active browser profile reduces
        fingerprint drift between headers and the underlying transport.
        """
        browser_version = getattr(getattr(self, "profile", None), "browser_version", "124.0.0.0")
        major = 124
        try:
            major = int(str(browser_version).split('.')[0])
        except Exception:
            major = 124

        candidates = []
        for value in (major, max(major, 124), 136, 135, 134, 133, 132, 131, 124, 110):
            if value not in candidates and value >= 110:
                candidates.append(value)

        for value in candidates:
            impersonation = f"chrome{value}"
            try:
                from curl_cffi.requests import Session as CurlSession
                CurlSession(impersonate=impersonation)
                return impersonation
            except Exception:
                continue

        return "chrome124"

    def _create_session(self) -> Any:
        """Create SSL-safe session using a transport profile that matches the UA."""
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            try:
                from curl_cffi.requests import Session as CurlSession
                impersonation = self._choose_tls_impersonation()
                try:
                    session = CurlSession(impersonate=impersonation)
                except Exception:
                    for _imp in ("chrome136", "chrome124", "chrome110"):
                        try:
                            session = CurlSession(impersonate=_imp)
                            break
                        except Exception:
                            continue
                    else:
                        session = CurlSession(impersonate="chrome110")
                session.trust_env = False
                return session
            except Exception:
                session = Session()
                session.verify = False
                session.trust_env = False
                return session
        except Exception:
            import requests
            session = requests.Session()
            session.verify = False
            session.trust_env = False
            return session

    def set_proxy(self, proxy: str):
        """Set proxy for the session"""
        if self.session:
            self.session.proxies = {"http": proxy, "https": proxy}
        """Keep the session default headers aligned with the current profile and token."""
        if not self.session:
            return

        try:
            default_headers = self.get_protected_headers(self.token)
            self.session.headers.update(default_headers)
        except Exception:
            pass

    def initialize_with_token(self, token: str):
        """Initialize with bot token"""
        self.token = token
        try:
            payload = token.split('.')[0]
            decoded = base64.b64decode(payload + '==').decode()
            self.user_id = decoded.split('.')[0]
        except:
            self.user_id = None

        self._update_session_headers()

    def _update_session_headers(self):
        """Keep the session default headers aligned with the current profile and token."""
        if not self.session:
            return

        try:
            default_headers = self.get_protected_headers(self.token)
            self.session.headers.update(default_headers)
        except Exception:
            pass

    def _generate_fingerprint(self) -> str:
        """Generate realistic Discord-style fingerprint"""
        # Discord fingerprints follow pattern: <timestamp_ms>.<random_64bit>
        timestamp_ms = int(time.time() * 1000)
        # 64-bit random value
        random_part = random.randint(1000000000000000000, 9999999999999999999)
        return f"{timestamp_ms}.{random_part}"

    def _fetch_fingerprint(self) -> tuple:
        """Fetch fingerprint from Discord"""
        if time.time() - self.cache_time < 3600 and self.fingerprint:
            return self.fingerprint, self.cookies

        try:
            headers = {
                "User-Agent": self.profile.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": self.profile.locale,
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://discord.com/channels/@me",
                "Origin": "https://discord.com",
                "Connection": "keep-alive",
                "Dnt": "1",
            }
            response = self.session.get(
                "https://discord.com/api/v9/experiments",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.fingerprint = data.get("fingerprint", self._generate_fingerprint())
                self.cookies = "; ".join([f"{k}={v}" for k, v in response.cookies.items()])
                self.cache_time = time.time()
            else:
                self.fingerprint = self._generate_fingerprint()
                self.cookies = f"locale={self.profile.locale}"
        except:
            self.fingerprint = self._generate_fingerprint()
            self.cookies = f"locale={self.profile.locale}"

        return self.fingerprint, self.cookies

    def _generate_super_properties(self) -> str:
        """Return a stable X-Super-Properties string for this session.

        Generated once per session (or after rotate_profile) so that every
        request in the same session sends identical super-properties, which
        is how a real browser behaves.
        """
        if self._cached_super_properties is not None:
            return self._cached_super_properties

        props = {
            "os": self.profile.os,
            "browser": self.profile.browser,
            "device": "",
            "system_locale": self.profile.locale,
            "browser_user_agent": self.profile.user_agent,
            "browser_version": self.profile.browser_version,
            "os_version": self.profile.os_version,
            "release_channel": "stable",
            "client_build_number": self.build_number,
            "client_event_source": None,
        }

        props_json = json.dumps(props, separators=(',', ':'), ensure_ascii=True)
        self._cached_super_properties = base64.b64encode(props_json.encode()).decode()
        self._cached_super_properties_hash = hashlib.md5(props_json.encode()).hexdigest()[:8]
        return self._cached_super_properties

    def _get_super_properties_hash(self) -> str:
        if self._cached_super_properties_hash is not None:
            return self._cached_super_properties_hash
        self._generate_super_properties()
        return self._cached_super_properties_hash or ""

    def _generate_track_header(self, fingerprint: str) -> str:
        window = int(time.time() // 30)
        seed = f"{fingerprint}:{self.profile.browser_version}:{window}"
        return hashlib.md5(seed.encode()).hexdigest()

    def _generate_context_properties(self) -> str:
        """Generate X-Context-Properties header for Discord API requests."""
        ctx_props = {
            "location": "Home",
            "location_guild_id": None,
            "location_channel_id": None,
        }
        return base64.b64encode(json.dumps(ctx_props, separators=(',', ':')).encode()).decode()

    def _generate_sec_ch_ua(self) -> Optional[str]:
        """Generate Sec-CH-UA header. Firefox does not send Client Hints — returns None for Firefox."""
        if self.profile.is_firefox:
            return None
        major_version = self.profile.browser_version.split('.')[0]
        return f'"Chromium";v="{major_version}", "Google Chrome";v="{major_version}", "Not(A:Brand";v="99"'

    def get_protected_headers(
        self,
        token: Optional[str] = None,
        rq_token: Optional[str] = None,
        captcha_key: Optional[str] = None,
        captcha_session_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Get fully protected headers for Discord API with modern spoofing"""
        if token:
            self.token = token
        
        fingerprint, cookies = self._fetch_fingerprint()

        header_items = [
            ("Authorization", self.token or ""),
            ("User-Agent", self.profile.user_agent),
            ("Accept", "*/*"),
            ("Accept-Language", f"{self.profile.locale},en;q=0.9,en;q=0.8"),
            ("Accept-Encoding", "gzip, deflate, br"),
            ("Cache-Control", "no-cache"),
            ("Pragma", "no-cache"),
            ("Origin", "https://discord.com"),
            ("Referer", "https://discord.com/channels/@me"),
            ("Sec-Fetch-Dest", self.profile.sec_fetch_dest),
            ("Sec-Fetch-Mode", self.profile.sec_fetch_mode),
            ("Sec-Fetch-Site", self.profile.sec_fetch_site),
            ("Dnt", "1"),
            ("X-Debug-Options", "bugReporterEnabled"),
            ("X-Discord-Locale", self.profile.locale),
            ("X-Discord-Timezone", self.profile.timezone),
            ("X-Super-Properties", self._generate_super_properties()),
            ("X-Super-Properties-Hash", self._get_super_properties_hash()),
            ("X-Track", self._generate_track_header(fingerprint)),
            ("X-Context-Properties", self._generate_context_properties()),
            ("X-Fingerprint", fingerprint),
            ("Cookie", cookies),
            ("Device-Memory", str(self.profile.device_memory)),
            ("Sec-Ch-Viewport-Width", self.profile.viewport_width),
            ("Sec-Ch-Viewport-Height", self.profile.viewport_height),
            ("Sec-Ch-DPR", self.profile.dpr),
            ("DPR", self.profile.dpr),
            ("ECT", self.profile.ect),
            ("Downlink", self.profile.downlink),
            ("RTT", self.profile.rtt),
            ("Save-Data", self.profile.save_data),
            ("Connection", "keep-alive"),
            ("TE", "trailers"),
        ]

        if self.profile.sec_ch_ua is not None:
            header_items.extend([
                ("Sec-Ch-Ua", self.profile.sec_ch_ua),
                ("Sec-Ch-Ua-Mobile", self.profile.sec_ch_ua_mobile),
                ("Sec-Ch-Ua-Platform", self.profile.sec_ch_ua_platform),
                ("Sec-Ch-Ua-Platform-Version", self.profile.sec_ch_ua_platform_version),
                ("Sec-Ch-Ua-Full-Version-List", self.profile.sec_ch_ua_full_version),
                ("Sec-Ch-Ua-Arch", self.profile.sec_ch_ua_arch),
                ("Sec-Ch-Ua-Bitness", self.profile.sec_ch_ua_bitness),
                ("Sec-Ch-Ua-Model", self.profile.sec_ch_ua_model),
                ("Sec-Ch-Ua-Form-Factor", self.profile.sec_ch_ua_form_factor),
                ("Sec-Ch-Prefers-Color-Scheme", self.profile.sec_ch_prefers_color_scheme),
                ("Sec-Ch-Prefers-Reduced-Motion", self.profile.sec_ch_prefers_reduced_motion),
                ("Upgrade-Insecure-Requests", "1"),
                ("Sec-Fetch-User", "?1"),
            ])

        # Avoid sending proxy-style IP headers by default; these can trigger Discord 403s on normal user requests.
        # These headers are valuable only when an actual proxy/transport layer supports them.
        # If you want to experiment with IP spoofing, enable it explicitly in the future.
        # header_items.extend([
        #     ("X-Forwarded-For", self.profile.x_forwarded_for),
        #     ("X-Real-IP", self.profile.x_real_ip),
        #     ("CF-Connecting-IP", self.profile.cf_connecting_ip),
        #     ("True-Client-IP", self.profile.true_client_ip),
        # ])

        for custom in getattr(self.profile, "custom_headers", []):
            if isinstance(custom, dict):
                name = custom.get("name")
                value = custom.get("value")
                if name and value:
                    header_items.append((name, value))

        if rq_token:
            header_items.append(("X-Captcha-Rqtoken", rq_token))
        if captcha_key:
            header_items.append(("X-Captcha-Key", captcha_key))
        if captcha_session_id:
            header_items.append(("X-Captcha-Session-Id", captcha_session_id))

        random.shuffle(header_items)
        return {name: value for name, value in header_items if value is not None}

    def get_websocket_headers(self) -> Dict[str, str]:
        """Get websocket headers"""
        headers = {
            "User-Agent": self.profile.user_agent,
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": self.profile.locale,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-WebSocket-Extensions": "permessage-deflate; client_max_window_bits",
            "Sec-WebSocket-Key": base64.b64encode(str(time.time()).encode()).decode()[:24],
            "Sec-WebSocket-Version": "13",
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            "Origin": "https://discord.com",
            "Sec-WebSocket-Protocol": "json",
        }

        if self.profile.sec_ch_ua is not None:
            headers.update({
                "Sec-Ch-Ua": self.profile.sec_ch_ua,
                "Sec-Ch-Ua-Mobile": self.profile.sec_ch_ua_mobile,
                "Sec-Ch-Ua-Platform": self.profile.sec_ch_ua_platform,
                "Sec-Ch-Ua-Platform-Version": self.profile.sec_ch_ua_platform_version,
                "Sec-Ch-Ua-Full-Version-List": self.profile.sec_ch_ua_full_version,
            })

        if self.profile.dpr:
            headers.update({
                "Sec-Ch-Viewport-Width": self.profile.viewport_width,
                "Sec-Ch-Viewport-Height": self.profile.viewport_height,
                "Sec-Ch-DPR": self.profile.dpr,
                "DPR": self.profile.dpr,
            })

        return headers

    def check_rate_limits(self) -> Optional[float]:
        """Check rate limits"""
        return None

    def handle_response(self, response: Any) -> Optional[float]:
        """Handle response"""
        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", "1.0"))
            return retry_after + random.uniform(0.5, 2.0)
        return None

    def rotate_profile(self):
        """Rotate browser profile and reset all per-session cached values."""
        self.profile = BrowserProfile()
        self.build_number = get_latest_build()
        self.cache_time = 0
        self.fingerprint = ""
        self._cached_super_properties = None  # Force rebuild with new profile
        self._cached_super_properties_hash = None

        # Full transport teardown: this prevents session bleed when a keep-alive
        # connection is reused across a user-agent / fingerprint change.
        try:
            if getattr(self, "session", None) is not None:
                close = getattr(self.session, "close", None)
                if callable(close):
                    close()
        except Exception:
            pass

        try:
            self.session = self._create_session()
        except Exception:
            self.session = None
        self._update_session_headers()

    def rotate_user_agent(self) -> Dict[str, str]:
        """Return a fully synchronized UA + header profile and rebuild the live transport.

        The returned dict intentionally contains the modern browser fingerprinting
        data that must stay in sync with the underlying TLS impersonation.
        """
        self.rotate_profile()
        return {
            "User-Agent": self.profile.user_agent,
            "Accept-Language": f"{self.profile.locale},en;q=0.9,en;q=0.8",
            "Sec-Ch-Ua": self.profile.sec_ch_ua or '"Chromium";v="136", "Google Chrome";v="136", "Not(A:Brand";v="99"',
            "Sec-Ch-Ua-Mobile": self.profile.sec_ch_ua_mobile,
            "Sec-Ch-Ua-Platform": self.profile.sec_ch_ua_platform,
            "Sec-Ch-Ua-Platform-Version": self.profile.sec_ch_ua_platform_version,
            "Sec-Ch-Ua-Full-Version-List": self.profile.sec_ch_ua_full_version,
            "Sec-Ch-Ua-Arch": self.profile.sec_ch_ua_arch,
            "Sec-Ch-Ua-Bitness": self.profile.sec_ch_ua_bitness,
            "Sec-Ch-Ua-Form-Factor": self.profile.sec_ch_ua_form_factor,
            "browser_target": f"chrome{self.profile.browser_version.split('.')[0]}",
        }

    def rotate_tls(self):
        """Alias for rotate_profile used by captcha retry flows."""
        self.rotate_profile()


__all__ = ['HeaderSpoofer', 'RateLimiter', 'BrowserProfile']
