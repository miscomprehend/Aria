import time
import random
import json
import base64
import re
import hashlib
import threading
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


_FALLBACK_BUILD = 324310  # Fallback build constant if live scrapers fail

# Last successfully fetched build (+ timestamp). The live scrape downloads
# discord.com + up to 8 JS bundles (~2-10s of blocking I/O) — far too slow
# to run on every captcha retry. Cache the result for 1h; only the first
# HeaderSpoofer ever pays for the scrape.
_BUILD_CACHE: Dict[str, Any] = {"build": 0, "at": 0.0}
_BUILD_CACHE_TTL = 3600.0


def get_latest_build(force_refresh: bool = False) -> int:
    """Fetch the current Discord client build number from public JS assets.

    Returns the fallback build number if the fetch fails for any reason.
    Successful results are cached process-wide for 1 hour so repeated
    captcha rotations never re-scrape Discord's JS bundles on the hot path.
    """
    if not force_refresh:
        try:
            cached_build = int(_BUILD_CACHE.get("build") or 0)
            cached_at = float(_BUILD_CACHE.get("at") or 0.0)
            if cached_build and (time.time() - cached_at) < _BUILD_CACHE_TTL:
                return cached_build
        except Exception:
            pass

    def _remember(build: int) -> int:
        try:
            _BUILD_CACHE["build"] = int(build)
            _BUILD_CACHE["at"] = time.time()
        except Exception:
            pass
        return int(build)

    try:
        import requests as _req  # use plain requests to avoid circular session issues
    except ImportError:
        return _FALLBACK_BUILD

    try:
        resp = _req.get("https://discord.com", timeout=5,
                        headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return _FALLBACK_BUILD

        # Find JS asset filenames from the HTML
        assets = re.findall(r'assets/([a-z0-9]+)\.js', resp.text)
        if not assets:
            return _FALLBACK_BUILD

        # Walk the last few bundles — build number lives in one of them.
        # Cap at 3 bundles (newest first): each extra bundle is another
        # full JS download (~1s+) on the hot path.
        for asset in reversed(assets[-3:]):
            try:
                js = _req.get(f"https://discord.com/assets/{asset}.js",
                              timeout=5,
                              headers={"User-Agent": "Mozilla/5.0"}).text
                m = re.search(r'buildNumber["\s]*:["\s]*(\d{5,6})', js)
                if m:
                    build = int(m.group(1))
                    print(f"[BUILD] Detected Discord build: {build}")
                    return _remember(build)
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
    """Chrome profile kept compatible with the active HTTP transport.

    Each instance is a self-contained, randomly varied browser fingerprint.
    Call rotate_profile() on the spoofer to get a fresh profile + session.

    Randomness comes from a *private* ``random.Random`` instance rather than the
    process-global RNG. Reseeding the global RNG here (as a previous version
    did) both leaked determinism into other callers and made two profiles built
    in the same second collapse to identical fingerprints.
    """

    # Chrome versions (2025-2026) used when rotating.
    _CHROME_VERSIONS = [
        "146.0.0.0",
        "133.0.0.0",
        "131.0.0.0",
        "120.0.0.0",
        "124.0.0.0",
    ]

    def __init__(self, browser_version: str = "146.0.0.0"):
        # Private RNG: seeded from OS entropy, never touches the global RNG.
        self._rng = random.Random()

        self.browser_version = browser_version
        self.is_firefox = False
        self.browser = "Chrome"
        self.os = "Windows"
        self.os_version = "10"
        self.platform = "Win32"
        ua_template = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser_version} Safari/537.36"
        )

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

        # One independent random draw per profile: two profiles built in the
        # same second no longer collapse to the same locale, and the chosen
        # locale then stays fixed for the life of the profile (stable device
        # fingerprint within a session; rotated only via rotate_profile).
        location = self._rng.choice(locations)

        self.user_agent = ua_template
        self.locale = location['locale']
        self.timezone = location['timezone']
        self.screen_resolution = self._rng.choice(screen_sizes)
        self.hardware_concurrency = self._rng.choice([4, 8, 16])
        self.device_memory = self._rng.choice([4, 8, 16, 32])

        width, height = map(int, self.screen_resolution.split("x"))
        self.viewport_width = str(max(800, width - self._rng.randint(0, 280)))
        self.viewport_height = str(max(600, height - self._rng.randint(100, 220)))
        self.dpr = self._rng.choice(["1", "1.25", "1.5", "2", "2.5", "3"])

        self.sec_fetch_dest = "empty"
        self.sec_fetch_mode = "cors"
        self.sec_fetch_site = "same-origin"
        self.ect = self._rng.choice(["4g", "4g", "3g"])
        self.downlink = str(self._rng.choice([10.0, 15.0, 20.0, 30.0]))
        self.rtt = str(self._rng.choice([20, 30, 40, 50]))
        self.save_data = "off"

        self.sec_ch_ua = None
        self.sec_ch_ua_mobile = "?0"
        self.sec_ch_ua_platform = f'"{self.os}"'
        self.sec_ch_ua_platform_version = "0.0.0"
        self.sec_ch_ua_full_version = f'"{self.browser_version}"'
        self.sec_ch_ua_arch = self._rng.choice(["x86", "x86_64"])
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
        first = self._rng.choice(first_octets)
        return f"{first}.{self._rng.randint(0,255)}.{self._rng.randint(0,255)}.{self._rng.randint(1,254)}"


class HeaderSpoofer:
    """Main header spoofer for Discord with per-call header rotation.

    The TLS transport is impersonated to match the active Chrome profile so the
    TLS fingerprint and the User-Agent always agree. When a captcha challenge
    appears, call ``rotate_tls()`` to tear down the old keep-alive connection
    and rebuild a fresh, matching TLS session + header block.
    """

    def __init__(self, browser_version: str = "124.0.0.0"):
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.fingerprint: str = ""
        self.cookies: str = ""
        self.cache_time: float = 0
        self._browser_version = browser_version
        # Build the profile FIRST so the TLS impersonation is chosen from the
        # exact browser version that will appear in the User-Agent. Creating the
        # session before the profile caused the TLS fingerprint to be picked
        # from the default version even when a different one was requested.
        self.profile = BrowserProfile(self._browser_version)
        # The proxy manager MUST exist before the transport is built: the
        # session applies the active proxy at creation time, so a rebuilt
        # session (rotate_profile) keeps egressing from the same IP instead
        # of silently falling back to the host's real IP mid-captcha.
        self.proxy_manager = None
        self._init_proxy_manager()
        self.session: Any = self._create_session()
        self.build_number = get_latest_build()  # Fetched live; falls back to _FALLBACK_BUILD
        self._cached_super_properties: Optional[str] = None  # Stable per session
        self._cached_super_properties_hash: Optional[str] = None
        # Private RNG for rotation decisions: never touches the global RNG so
        # captcha polling / backoff jitter elsewhere stays independent.
        self._rng = random.Random()
        # Guards rotation + session rebuild so concurrent request threads can
        # never interleave a profile swap with a header build (which would
        # emit a User-Agent from profile A with super-properties from B).
        self._lock = threading.RLock()
        # Humanized timing: minimum gap between outbound requests, with
        # jitter applied in wait_for_slot(). Prevents machine-regular bursts
        # from hammering Discord at fixed intervals.
        self._last_request_at = 0.0
        self._min_request_gap = 0.4
        self._max_request_gap = 1.6

    def _init_proxy_manager(self):
        """Initialize proxy manager"""
        try:
            from proxy_manager import ProxyManager
            self.proxy_manager = ProxyManager()
        except:
            self.proxy_manager = None

    def get_active_proxy(self) -> str:
        """Return the proxy string the live transport egresses through, or ''.

        Single source of truth for both the HTTP session and the captcha
        solver: hCaptcha tokens are IP-bound, so the IP that solves the
        challenge MUST be the IP that submits the token. Reading the proxy
        from one accessor keeps the two from drifting apart.
        """
        manager = getattr(self, "proxy_manager", None)
        if not manager:
            return ""
        try:
            return str(manager.get_active_proxy() or "").strip()
        except Exception:
            return ""

    def _profile_major(self) -> int:
        """Return the major version of the active profile (default 124)."""
        version = getattr(getattr(self, "profile", None), "browser_version", "124.0.0.0")
        try:
            return int(str(version).split('.')[0])
        except Exception:
            return 124

    def _choose_tls_impersonation(self) -> str:
        """Choose the closest available curl_cffi Chrome impersonation.

        Matching the TLS impersonation to the active browser profile reduces
        fingerprint drift between headers and the underlying transport. The
        chosen impersonation's major version always matches the User-Agent's
        major version when curl_cffi supports it.
        """
        major = self._profile_major()

        candidates = []
        for value in (major, max(major, 124), 134, 131, 124, 133, 110):
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
        """Create a supported Chrome-impersonating session when available.

        The impersonation is chosen from the active profile's browser version,
        so the TLS handshake fingerprint matches the User-Agent exactly.
        """
        try:
            from curl_cffi.requests import Session as CurlSession
            impersonation = self._choose_tls_impersonation()
            try:
                session = CurlSession(impersonate=impersonation)
            except Exception:
                for _imp in ("chrome120", "chrome124", "chrome133"):
                    try:
                        session = CurlSession(impersonate=_imp)
                        break
                    except Exception:
                        continue
                else:
                    session = CurlSession(impersonate="chrome110")
            session.trust_env = False
            self._apply_proxy(session)
            return session
        except Exception:
            if Session is None:
                raise RuntimeError("Install curl_cffi or requests to create an API session.")
            session = Session()
            session.verify = False
            session.trust_env = False
            self._apply_proxy(session)
            return session

    def _apply_proxy(self, session: Any) -> None:
        """Route ``session`` through the active proxy, or clear it proxyless.

        Called on every session (re)build so the egress IP is stable for the
        lifetime of the transport. With no proxy configured the session is
        explicitly left proxyless rather than inheriting ``trust_env`` state.
        """
        if session is None:
            return
        proxy = self.get_active_proxy()
        try:
            if proxy:
                session.proxies = {"http": proxy, "https": proxy}
            else:
                session.proxies = {}
        except Exception as exc:
            print(f"[PROXY] Failed to apply proxy to session: {exc}")

    def set_proxy(self, proxy: str):
        """Pin the egress proxy and keep the live transport + manager in sync.

        Sets the proxy on the proxy manager (when present) AND applies it to
        the live session, so the session's egress IP, the manager's reported
        active proxy, and the captcha solver's proxy all agree. An empty
        string clears the proxy and leaves the session explicitly proxyless.
        """
        normalized = str(proxy or "").strip()
        manager = getattr(self, "proxy_manager", None)
        if manager is not None:
            try:
                if normalized:
                    manager.set_active_proxy(normalized)
                else:
                    manager.clear_proxy()
            except AttributeError:
                # Older manager without pinning helpers: fall back to nudging
                # its current-proxy slot when one exists.
                try:
                    if hasattr(manager, "current_proxy"):
                        manager.current_proxy = normalized or None
                except Exception:
                    pass
            except Exception as exc:
                print(f"[PROXY] Failed to pin proxy on manager: {exc}")
        session = getattr(self, "session", None)
        if session is not None:
            try:
                if normalized:
                    session.proxies = {"http": normalized, "https": normalized}
                else:
                    session.proxies = {}
            except Exception as exc:
                print(f"[PROXY] Failed to apply proxy to session: {exc}")

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

    def rebuild_session(self):
        """Replace the transport while preserving the active browser profile.

        Runs under the rotation lock so a concurrent header build can never
        read a half-swapped session/profile pair.
        """
        with self._rotation_lock():
            self._rebuild_session_inner()

    def _rebuild_session_inner(self):
        """Lock-free session rebuild; caller must hold the rotation lock."""
        old_session = getattr(self, "session", None)
        if old_session is not None:
            close = getattr(old_session, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as error:
                    print(f"[NETWORK] Failed to close prior HTTP session: {error}")
        self.session = self._create_session()
        self._update_session_headers()

    def _generate_fingerprint(self) -> str:
        """Generate realistic Discord-style fingerprint."""
        # Discord fingerprints follow pattern: <timestamp_ms>.<random_64bit>
        timestamp_ms = int(time.time() * 1000)
        # 64-bit random value from the private RNG (never the global one).
        rng = getattr(self, "_rng", None) or random
        random_part = rng.randint(1000000000000000000, 9999999999999999999)
        return f"{timestamp_ms}.{random_part}"

    # Server-issued fingerprints are stable per session; the /experiments
    # round-trip (~300-800ms) is pure latency on every request otherwise.
    _FINGERPRINT_TTL = 600.0

    def _fetch_fingerprint(self) -> tuple:
        """Fetch/generate a fingerprint, cached for 10 minutes.

        The server-provided fingerprint is stable per session, so reusing it
        for 10 minutes is both faster (no /experiments round-trip per
        request) and more browser-like than minting a fresh one every call.
        ``rotate_profile`` still resets it for a genuinely fresh identity.
        """
        now = time.time()
        try:
            if self.fingerprint and (now - float(self.cache_time or 0.0)) < self._FINGERPRINT_TTL:
                return self.fingerprint, self.cookies
        except Exception:
            pass
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
            else:
                self.fingerprint = self._generate_fingerprint()
                self.cookies = f"locale={self.profile.locale}"
            self.cache_time = time.time()
        except:
            self.fingerprint = self._generate_fingerprint()
            self.cookies = f"locale={self.profile.locale}"
            self.cache_time = time.time()

        return self.fingerprint, self.cookies

    def _generate_super_properties(self) -> str:
        """Return a stable X-Super-Properties string for this session.

        Generated once per session (or after rotate_profile) so that every
        request in the same session sends identical super-properties, which
        is how a real browser behaves. The value is a base64-encoded JSON blob
        that Discord's tracking layer expects; it is built from the same
        profile fields that drive the User-Agent and TLS impersonation.
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
        """Get fully protected headers for Discord API with modern spoofing.

        Header ORDER is rotated per call (see ``_rotate_header_order``) so
        repeated requests do not emit an identical byte-for-byte header block
        — this is the rotation step. Everything is built under ``self._lock``
        so a concurrent ``rotate_profile`` can never mix fields from two
        profiles in one header block.
        """
        with self._rotation_lock():
            if token:
                self.token = token

            fingerprint, cookies = self._fetch_fingerprint()

            header_items = self._build_header_items(
                fingerprint, cookies, rq_token, captcha_key, captcha_session_id
            )
            header_items = self._rotate_header_order(header_items)
            return {name: value for name, value in header_items if value is not None}

    def _build_header_items(
        self,
        fingerprint: str,
        cookies: str,
        rq_token: Optional[str] = None,
        captcha_key: Optional[str] = None,
        captcha_session_id: Optional[str] = None,
    ) -> list:
        """Assemble the full header list from the ACTIVE profile snapshot.

        Split out of ``get_protected_headers`` so the header contract (which
        names/values are sent) can be tested without network access.
        """
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

        # NOTE: proxy-style IP headers (X-Forwarded-For / X-Real-IP /
        # CF-Connecting-IP / True-Client-IP) are deliberately NOT sent: the
        # profile still mints them, but emitting them on normal user requests
        # triggers Discord 403s. Egress identity comes from the transport
        # proxy (see get_active_proxy / set_proxy), not header spoofing.

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
        return header_items

    def _rotate_header_order(self, header_items: list) -> list:
        """Rotate header order per call using the private RNG.

        Returns a NEW list; the caller's list is never mutated. Authorization
        stays pinned at the front (Discord clients always send it first)
        while the remaining entries are shuffled, so every request carries an
        identical header SET in a different byte ORDER.
        """
        items = list(header_items)
        pinned = []
        rest = []
        for pair in items:
            if pair and str(pair[0]).casefold() == "authorization":
                pinned.append(pair)
            else:
                rest.append(pair)
        self._rng.shuffle(rest)
        return pinned + rest

    def _rotation_lock(self):
        """Return the rotation lock (created lazily for unpickled spoofers)."""
        lock = getattr(self, "_lock", None)
        if lock is None:
            lock = threading.RLock()
            self._lock = lock
        return lock

    def wait_for_slot(self) -> float:
        """Sleep until the next humanized request slot; returns seconds slept.

        Enforces a jittered minimum gap between outbound requests so traffic
        never leaves at machine-regular intervals. Thread-safe.
        """
        with self._rotation_lock():
            now = time.time()
            earliest = self._last_request_at + self._rng.uniform(
                self._min_request_gap, self._max_request_gap
            )
            delay = max(0.0, earliest - now)
        if delay > 0:
            time.sleep(delay)
        with self._rotation_lock():
            self._last_request_at = time.time()
        return delay

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
        """Handle response; humanized 429 backoff using the private RNG."""
        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", "1.0"))
            rng = getattr(self, "_rng", None) or random
            return retry_after + rng.uniform(0.5, 2.0)
        return None

    def rotate_profile(self):
        """Rotate browser profile and reset all per-session cached values.

        Picks a new random Chrome version from the supported list (private
        RNG), tears down the old TLS session (preventing keep-alive bleed
        across fingerprints), and rebuilds a fresh session + headers. Runs
        under the rotation lock so concurrent header builds never mix fields
        from the old and new profiles. Call this before each new request
        batch to rotate headers, fingerprint, and transport.
        """
        with self._rotation_lock():
            rng = getattr(self, "_rng", None) or random
            self.profile = BrowserProfile(rng.choice(BrowserProfile._CHROME_VERSIONS))
            self._browser_version = self.profile.browser_version
            self.build_number = get_latest_build()
            self.cache_time = 0
            self.fingerprint = ""
            self._cached_super_properties = None  # Force rebuild with new profile
            self._cached_super_properties_hash = None

            # Full transport teardown: this prevents session bleed when a keep-alive
            # connection is reused across a user-agent / fingerprint change.
            # (Inner variant: rotate_profile already holds the rotation lock,
            # so this must NOT re-acquire it — RLock would allow it, but the
            # explicit inner keeps the locking contract obvious.)
            try:
                self._rebuild_session_inner()
            except Exception:
                self.session = None

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
        """Alias for rotate_profile used by captcha retry flows.

        Rotates the TLS impersonation + browser profile so a captcha-triggered
        fingerprint is never reused on the next attempt. The new session's TLS
        handshake is matched to the new User-Agent before any request is sent.
        """
        self.rotate_profile()


__all__ = ['HeaderSpoofer', 'RateLimiter', 'BrowserProfile']