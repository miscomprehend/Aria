import unittest
from unittest.mock import patch

from rate_limit import RateLimiter


class RateLimitSafetyTests(unittest.TestCase):
    def test_endpoint_limit_preserves_full_retry_after(self):
        limiter = RateLimiter()
        with patch("rate_limit.time.time", return_value=100.0):
            retry_after = limiter.handle_429({"Retry-After": "17"}, "/channels/1/messages")

        self.assertEqual(retry_after, 17.0)
        with patch("rate_limit.time.time", return_value=100.0):
            self.assertEqual(limiter.get_wait_time("/channels/1/messages"), 17.0)
            self.assertIsNone(limiter.get_wait_time("/channels/2/messages"))

    def test_global_limit_applies_to_all_endpoints(self):
        limiter = RateLimiter()
        with patch("rate_limit.time.time", return_value=100.0):
            limiter.handle_429({}, "/channels/1/messages", global_rate_limit=True, retry_after=23)

        with patch("rate_limit.time.time", return_value=100.0):
            self.assertEqual(limiter.get_wait_time("/users/@me"), 23.0)
            self.assertEqual(limiter.get_wait_time("/channels/2/messages"), 23.0)

    def test_expired_rate_limit_does_not_delay_requests(self):
        limiter = RateLimiter()
        with patch("rate_limit.time.time", return_value=100.0):
            limiter.handle_429({"retry-after": "5"}, "/channels/1/messages")
        with patch("rate_limit.time.time", return_value=105.0):
            self.assertIsNone(limiter.get_wait_time("/channels/1/messages"))


if __name__ == "__main__":
    unittest.main()