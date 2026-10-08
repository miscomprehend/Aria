from pathlib import Path
import random
import requests
import time
from urllib.parse import urlparse

class ProxyManager:
    _github_load_logged = False

    def __init__(self, proxy_list=None):
        self.proxies = []
        self.last_fetch = 0
        self.fetch_interval = 3600  # Refresh every hour
        self.local_proxy_file = Path(__file__).with_name("proxies.txt")
        self.state_file = Path(__file__).with_name("proxy_state.txt")
        self.current_proxy = None
        self._load_rotation_state()

    def _load_rotation_state(self):
        self.proxies = self._load_local_proxies()
        if not self.proxies:
            self.current_proxy = None
            return
        if self.state_file.exists():
            idx = 0
            try:
                idx = int(self.state_file.read_text().strip())
            except Exception:
                idx = 0
            if idx < 0 or idx >= len(self.proxies):
                idx = 0
                self._save_rotation_state(0)  # repair a stale/out-of-range file
            self.current_proxy = self.proxies[idx]
        else:
            self.current_proxy = self.proxies[0]
            self._save_rotation_state(0)

    def _save_rotation_state(self, idx):
        try:
            self.state_file.write_text(str(idx))
        except Exception:
            pass

    def _normalize_proxy(self, proxy):
        entry = str(proxy or "").strip()
        if not entry or entry.startswith('#'):
            return None

        if entry.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            parsed = urlparse(entry)
            if not parsed.hostname or not parsed.port:
                return None

            scheme = (parsed.scheme or 'http').lower()
            # websocket-client only supports http, socks4, and socks5 proxy types.
            if scheme == 'https':
                scheme = 'http'
            if scheme not in {'http', 'socks4', 'socks5'}:
                return None

            auth = ""
            if parsed.username:
                auth = parsed.username
                if parsed.password:
                    auth += f":{parsed.password}"
                auth += "@"
            return f"{scheme}://{auth}{parsed.hostname}:{parsed.port}"

        parts = entry.split(':')
        if len(parts) == 2:
            host, port = parts
            return f"http://{host}:{port}"

        if len(parts) == 4:
            host, port, username, password = parts
            return f"http://{username}:{password}@{host}:{port}"

        return None

    def _normalize_proxies(self, proxy_list):
        normalized = []
        seen = set()
        for proxy in proxy_list:
            parsed = self._normalize_proxy(proxy)
            if parsed and parsed not in seen:
                normalized.append(parsed)
                seen.add(parsed)
        return normalized

    def _load_local_proxies(self):
        try:
            if not self.local_proxy_file.exists():
                return []
            lines = self.local_proxy_file.read_text(encoding="utf-8").splitlines()
            proxies = self._normalize_proxies(lines)
            return proxies
        except Exception as e:
            print(f"[PROXY] Failed to load local proxies: {e}")
            return []
    
    # REMOVED: _fetch_from_github and refresh. Only proxies.txt is used.
    
    def get_random_proxy(self, max_attempts=5):
        """Return the current working proxy, rotate to next on failure, persist across restarts."""
        if not self.proxies:
            self.proxies = self._load_local_proxies()
        if not self.proxies:
            self.current_proxy = None
            return {}
        idx = self.proxies.index(self.current_proxy) if self.current_proxy in self.proxies else 0
        attempts = 0
        while attempts < min(max_attempts, len(self.proxies)):
            proxy = self.proxies[idx]
            proxy_dict = {"http": proxy, "https": proxy}
            if self.test_proxy(proxy_dict):
                self.current_proxy = proxy
                self._save_rotation_state(idx)
                return proxy_dict
            # Move to next proxy
            idx = (idx + 1) % len(self.proxies)
            attempts += 1
        # If none work, clear state
        self.current_proxy = None
        self._save_rotation_state(0)
        return {}
    
    def get_active_proxy(self):
        """Return the current proxy string ('http://user:pass@host:port') or ''."""
        if not self.current_proxy and self.proxies:
            self.current_proxy = self.proxies[0]
        return str(self.current_proxy or "")

    def set_active_proxy(self, proxy: str) -> str:
        """Pin the egress proxy; the normalizer validates the value first.

        The pinned proxy becomes the single egress IP for the live session
        AND the captcha solver, so IP-bound hCaptcha tokens are solved and
        submitted from the same address. Raises ValueError on invalid input.
        """
        normalized = self._normalize_proxy(proxy)
        if not normalized:
            raise ValueError(f"Invalid proxy value: {proxy!r}")
        if normalized not in self.proxies:
            self.proxies.append(normalized)
        self.current_proxy = normalized
        try:
            self._save_rotation_state(self.proxies.index(normalized))
        except Exception:
            pass
        return normalized

    def clear_proxy(self) -> None:
        """Drop the pinned proxy; the transport goes explicitly proxyless."""
        self.current_proxy = None
        try:
            self._save_rotation_state(0)
        except Exception:
            pass

    def get_2captcha_proxy(self):
        """Return the active proxy as a 2Captcha (proxy, proxytype) pair.

        2Captcha expects ``proxy`` as ``user:pass@host:port`` and ``proxytype``
        as one of HTTP / SOCKS4 / SOCKS5. Returns ('', '') when no proxy is set.
        """
        raw = self.get_active_proxy()
        if not raw:
            return "", ""
        parsed = urlparse(raw)
        if not parsed.hostname or not parsed.port:
            return "", ""
        scheme = (parsed.scheme or 'http').lower()
        if scheme == 'https':
            scheme = 'http'
        proxytype = {'http': 'HTTP', 'socks4': 'SOCKS4', 'socks5': 'SOCKS5'}.get(scheme, 'HTTP')
        credentials = ""
        if parsed.username:
            credentials = f"{parsed.username}:{parsed.password or ''}@"
        return f"{credentials}{parsed.hostname}:{parsed.port}", proxytype

    def get_yescaptcha_proxy(self):
        """Return the active proxy in YesCaptcha 'type:host:port:user:pass' form."""
        raw = self.get_active_proxy()
        if not raw:
            return ""
        parsed = urlparse(raw)
        if not parsed.hostname or not parsed.port:
            return ""
        scheme = (parsed.scheme or 'http').lower()
        if scheme == 'https':
            scheme = 'http'
        username = parsed.username or ""
        password = parsed.password or ""
        return f"{scheme}:{parsed.hostname}:{parsed.port}:{username}:{password}"

    def test_proxy(self, proxy):
        """Test if a proxy is working."""
        try:
            response = requests.get("https://httpbin.org/ip", proxies=proxy, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_all_proxies(self):
        """Return all loaded proxies."""
        if not self.proxies:
            self.proxies = self._load_local_proxies()
        return list(self.proxies)