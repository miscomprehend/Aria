import json
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import config
from token_encrypter import TokenEncrypter
from token_config import configure_token, identify_token_owner


class TokenConfigTests(unittest.TestCase):
    def test_identifies_token_owner_from_verified_account_profile(self):
        profile = {"id": "123456789012345678", "username": "aria-owner"}
        with patch("api_client.DiscordAPIClient") as client_class:
            client_class.return_value.get_user_info.return_value = profile

            identity = identify_token_owner("test-token")

        self.assertEqual(identity, {"id": profile["id"], "username": profile["username"]})
        client_class.return_value.get_user_info.assert_called_once_with(force=True)

    def test_rejects_token_without_a_verified_account_id(self):
        with patch("api_client.DiscordAPIClient") as client_class:
            client_class.return_value.get_user_info.return_value = None

            with self.assertRaisesRegex(ValueError, "Could not verify"):
                identify_token_owner("invalid-token")

    def test_saved_token_refresh_updates_owner_identity(self):
        from token_config import identify_saved_token_owner

        owner = {"id": "123456789012345678", "username": "aria-owner"}
        with tempfile.TemporaryDirectory() as directory:
            config_path = os.path.join(directory, "config.json")
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump({"token": "saved-token", "owner_id": "old-owner"}, handle)

            with patch("token_config.identify_token_owner", return_value=owner) as identify:
                result = identify_saved_token_owner(config_path)

            with open(config_path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)

        self.assertEqual(result, owner)
        identify.assert_called_once_with("saved-token")
        self.assertEqual(saved["owner_id"], owner["id"])
        self.assertEqual(saved["owner_username"], owner["username"])

    def test_detected_owner_identity_is_saved_with_token_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = os.path.join(directory, "config.json")
            owner = {"id": "123456789012345678", "username": "aria-owner"}
            output = io.StringIO()

            with redirect_stdout(output):
                configure_token("test-token", remember=False, config_path=config_path, owner_identity=owner)

            with open(config_path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(saved["token"], "")
        self.assertEqual(saved["owner_id"], owner["id"])
        self.assertEqual(saved["owner_username"], owner["username"])

    def test_token_helper_prints_only_machine_readable_owner_identity(self):
        from token_config import main

        owner = {"id": "123456789012345678", "username": "aria-owner"}
        output = io.StringIO()
        with patch("token_config.sys.argv", ["token_config.py", "save"]), \
                patch("token_config.sys.stdin", io.StringIO("test-token\n")), \
                patch("token_config.identify_token_owner", return_value=owner), \
                patch("token_config.configure_token") as configure, \
                redirect_stdout(output):
            main()

        self.assertEqual(json.loads(output.getvalue()), {"owner": owner})
        configure.assert_called_once_with("test-token", remember=True, owner_identity=owner)

    def test_identify_action_prints_saved_account_identity(self):
        from token_config import main

        owner = {"id": "123456789012345678", "username": "aria-owner"}
        output = io.StringIO()
        with patch("token_config.sys.argv", ["token_config.py", "identify"]), \
                patch("token_config.identify_saved_token_owner", return_value=owner), \
                redirect_stdout(output):
            main()

        self.assertEqual(json.loads(output.getvalue()), {"owner": owner})

    def test_remembered_token_is_encrypted_and_can_be_cleared(self):
        previous_encrypter = config._encrypter
        try:
            with tempfile.TemporaryDirectory() as directory:
                config._encrypter = TokenEncrypter(os.path.join(directory, ".aria_key"))
                config_path = os.path.join(directory, "config.json")

                configure_token("test-token", remember=True, config_path=config_path)

                with open(config_path, "r", encoding="utf-8") as handle:
                    saved = json.load(handle)["token"]
                self.assertTrue(saved.startswith("enc:"))
                self.assertEqual(config.Config(config_path).get("token"), "test-token")

                configure_token("test-token", remember=False, config_path=config_path)
                with open(config_path, "r", encoding="utf-8") as handle:
                    self.assertEqual(json.load(handle)["token"], "")
        finally:
            config._encrypter = previous_encrypter


if __name__ == "__main__":
    unittest.main()
