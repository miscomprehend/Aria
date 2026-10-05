import base64
import unittest
from unittest.mock import patch

import profile_editor
from profile_editor import ProfileError, apply_update, fetch_profile, parse_update

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PNG_B64 = base64.b64encode(PNG).decode()


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body if body is not None else {}

    def json(self):
        return self._body


class FakeApi:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def request(self, method, endpoint, data=None):
        self.calls.append((method, endpoint, data))
        reply = self.responses.get((method, endpoint), FakeResponse(200))
        if isinstance(reply, list):
            return reply.pop(0)
        return reply


class ParseUpdateTests(unittest.TestCase):
    def test_only_submitted_fields_are_patched_and_split_by_endpoint(self):
        account, profile = parse_update({
            "global_name": "  Aria  ", "bio": "hello", "pronouns": "they/them", "accent_color": "#5B8CFF",
        })
        self.assertEqual(account, {"global_name": "Aria", "accent_color": 0x5B8CFF})
        self.assertEqual(profile, {"bio": "hello", "pronouns": "they/them"})

    def test_blank_values_clear_the_field(self):
        account, profile = parse_update({"global_name": "", "accent_color": "", "bio": "", "pronouns": ""})
        self.assertEqual(account, {"global_name": None, "accent_color": None})
        self.assertEqual(profile, {"bio": "", "pronouns": ""})

    def test_limits_match_the_profile_commands(self):
        for payload in ({"bio": "x" * 191}, {"pronouns": "x" * 41}, {"global_name": "x" * 33}):
            with self.assertRaises(ProfileError):
                parse_update(payload)
        parse_update({"bio": "x" * 190, "pronouns": "x" * 40, "global_name": "x" * 32})

    def test_rejects_bad_accent_empty_and_non_object_requests(self):
        for payload in ({"accent_color": "blue"}, {"accent_color": "#12345"}, {}, {"bio": 5}):
            with self.assertRaises(ProfileError):
                parse_update(payload)
        with self.assertRaises(ProfileError):
            parse_update(["bio"])

    def test_uploaded_image_becomes_a_validated_data_uri(self):
        account, _ = parse_update({"avatar": {"data": f"data:image/png;base64,{PNG_B64}"}})
        self.assertEqual(account["avatar"], f"data:image/png;base64,{PNG_B64}")
        account, _ = parse_update({"banner": {"data": PNG_B64}})
        self.assertTrue(account["banner"].startswith("data:image/png;base64,"))

    def test_remove_clears_the_image(self):
        account, _ = parse_update({"avatar": {"remove": True}, "banner": None})
        self.assertEqual(account, {"avatar": None, "banner": None})

    def test_invalid_images_are_rejected(self):
        bad = base64.b64encode(b"not an image at all").decode()
        for spec in ({"data": bad}, {"data": "%%%not-base64%%%"}, {"data": ""}, {}, "nope"):
            with self.assertRaises(ProfileError):
                parse_update({"avatar": spec})

    def test_image_url_is_downloaded_without_the_discord_session(self):
        with patch.object(profile_editor, "download_avatar_data_uri", return_value="data:image/png;base64,AA") as dl:
            account, _ = parse_update({"avatar": {"url": "https://images.example/a.png"}})
        dl.assert_called_once_with("https://images.example/a.png")
        self.assertEqual(account["avatar"], "data:image/png;base64,AA")

    def test_bad_image_url_reports_a_friendly_error(self):
        with patch.object(profile_editor, "download_avatar_data_uri", side_effect=ValueError("Provide a public HTTPS image URL")):
            with self.assertRaisesRegex(ProfileError, "public HTTPS"):
                parse_update({"banner": {"url": "http://127.0.0.1/x.png"}})


class ApplyUpdateTests(unittest.TestCase):
    def test_account_and_profile_fields_use_their_own_endpoints(self):
        api = FakeApi()
        result = apply_update(api, {"global_name": "Aria", "bio": "hi"})
        self.assertEqual(result, {"updated": ["global_name", "bio"], "failed": []})
        self.assertEqual(
            [(m, e, d) for m, e, d in api.calls],
            [("PATCH", "/users/@me", {"global_name": "Aria"}), ("PATCH", "/users/@me/profile", {"bio": "hi"})],
        )

    def test_one_failing_group_does_not_block_the_other(self):
        api = FakeApi({("PATCH", "/users/@me"): FakeResponse(400, {
            "message": "Invalid Form Body",
            "errors": {"banner": {"_errors": [{"message": "Banner requires Nitro"}]}},
        })})
        result = apply_update(api, {"banner": {"remove": True}, "pronouns": "she/her"})
        self.assertEqual(result["updated"], ["pronouns"])
        self.assertEqual(result["failed"], [{"fields": ["banner"], "error": "Banner requires Nitro"}])
        self.assertEqual(len([c for c in api.calls if c[1] == "/users/@me"]), 1)  # 400 is not retried

    def test_rate_limit_is_retried(self):
        api = FakeApi({("PATCH", "/users/@me"): [FakeResponse(429, {"retry_after": 0.01}), FakeResponse(200)]})
        with patch("profile_editor.time.sleep") as sleep:
            result = apply_update(api, {"global_name": "Aria"})
        self.assertEqual(result["updated"], ["global_name"])
        sleep.assert_called_once()

    def test_validation_happens_before_any_request(self):
        api = FakeApi()
        with self.assertRaises(ProfileError):
            apply_update(api, {"bio": "x" * 500, "global_name": "ok"})
        self.assertEqual(api.calls, [])


class FetchProfileTests(unittest.TestCase):
    def test_maps_account_and_profile(self):
        api = FakeApi({
            ("GET", "/users/@me"): FakeResponse(200, {
                "id": "42", "username": "aria", "global_name": "Aria", "avatar": "a_hash",
                "banner": "bhash", "accent_color": 0x5B8CFF, "premium_type": 2,
            }),
            ("GET", "/users/@me/profile"): FakeResponse(200, {"user_profile": {"bio": "hi", "pronouns": "they"}}),
        })
        profile = fetch_profile(api)
        self.assertEqual(profile["avatar_url"], "https://cdn.discordapp.com/avatars/42/a_hash.gif?size=256")
        self.assertEqual(profile["banner_url"], "https://cdn.discordapp.com/banners/42/bhash.png?size=600")
        self.assertEqual((profile["accent_color"], profile["bio"], profile["pronouns"]), ("#5b8cff", "hi", "they"))
        self.assertEqual(profile["premium_type"], 2)

    def test_profile_lookup_failure_still_returns_the_account(self):
        api = FakeApi({
            ("GET", "/users/@me"): FakeResponse(200, {"id": "42", "username": "aria"}),
            ("GET", "/users/@me/profile"): FakeResponse(500),
        })
        profile = fetch_profile(api)
        self.assertEqual((profile["bio"], profile["avatar_url"], profile["accent_color"]), ("", "", ""))

    def test_account_failure_raises(self):
        with self.assertRaises(ProfileError):
            fetch_profile(FakeApi({("GET", "/users/@me"): FakeResponse(401)}))


if __name__ == "__main__":
    unittest.main()
