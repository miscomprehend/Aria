def _rotate_transport(self):
        """Rotate the TLS session + browser profile before a captcha attempt.

        Wraps HeaderSpoofer.rotate_tls() so the captcha flow always gets a
        fresh transport (new TLS impersonation, user agent, fingerprint, and
        headers) before talking to the solver or retrying Discord. A stale
        keep-alive connection is torn down so the new fingerprint is not
        leaked across the old socket.
        """
        try:
            if hasattr(self.header_spoofer, "rotate_tls"):
                self.header_spoofer.rotate_tls()
            elif hasattr(self.header_spoofer, "rotate_profile"):
                self.header_spoofer.rotate_profile()
        except Exception as exc:
            print(f"[CAPTCHA] Transport rotation failed: {exc}")

    def _solve_captcha_challenge(self, challenge: Dict[str, str]) -> Optional[str]:
        if challenge.get("service") not in {"hcaptcha", ""}:
            print(f'[CAPTCHA] Unsupported captcha service: {challenge.get("service")}')
            return None

        providers = self._get_captcha_provider_candidates()
        if not providers:
            print('[CAPTCHA] No captcha API key configured. Set NOCAPTCHAAI_API_KEY (or YES_CAPTCHA_API_KEY), or captcha_api_key in the Aria config.')
            return None

        for provider in providers:
            self._captcha_provider_name = provider["name"]

            # Fresh transport before each provider attempt so a captcha-triggered
            # fingerprint is never reused on the next try.
            self._rotate_transport()

            task_id = self._create_captcha_task(provider, challenge)
            if not task_id:
                continue
            token = self._poll_captcha_result(provider, task_id)
            if token:
                return token

            # Poll failed (timeout / error / no token). Rotate the transport so
            # the next provider attempt starts from a clean fingerprint.
            self._rotate_transport()
        return None