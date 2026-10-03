import threading
import unittest
from unittest.mock import Mock, patch

from host import HostManager, _keepalive_restart_delay
from instance_access import instance_owner_ids


class InstanceAccessTests(unittest.TestCase):
    def test_hosted_owner_scope_excludes_global_owners_and_other_clients(self):
        master_owners = {"main-owner", "secondary-owner"}

        first_client = instance_owner_ids(
            True,
            "first-requester",
            "first-token-user",
            master_owners,
        )
        second_client = instance_owner_ids(
            True,
            "second-requester",
            "second-token-user",
            master_owners,
        )

        self.assertEqual(first_client, {"first-requester", "first-token-user"})
        self.assertNotIn("main-owner", first_client)
        self.assertTrue(first_client.isdisjoint(second_client))

    def test_main_instance_keeps_master_and_token_owner_access(self):
        self.assertEqual(
            instance_owner_ids(
                False,
                "main-owner",
                "main-token-user",
                {"main-owner", "secondary-owner"},
            ),
            {"main-owner", "secondary-owner", "main-token-user"},
        )

    def test_empty_owner_ids_are_ignored(self):
        self.assertEqual(
            instance_owner_ids(True, None, "token-user", {"main-owner"}),
            {"token-user"},
        )

    def test_keepalive_retries_forever_with_a_capped_backoff(self):
        self.assertEqual(_keepalive_restart_delay(1), 5)
        self.assertEqual(_keepalive_restart_delay(2), 10)
        self.assertEqual(_keepalive_restart_delay(20), 300)

    def test_active_hosted_owner_is_routed_to_one_client(self):
        manager = HostManager.__new__(HostManager)
        manager.lock = threading.RLock()
        manager.active_tokens = {
            "client-1": {"owner": "hosted-owner"},
            "client-2": {"owner": "another-owner"},
        }

        self.assertTrue(manager.has_active_hosted_instance("hosted-owner"))
        self.assertFalse(manager.has_active_hosted_instance("unknown-owner"))

    def test_restore_keeps_only_one_saved_instance_per_owner(self):
        manager = HostManager.__new__(HostManager)
        manager._restore_lock = threading.Lock()
        manager._restore_in_progress = False
        manager.lock = threading.RLock()
        manager.saved_users = {
            "older-client": {
                "owner": "hosted-owner",
                "token": "old.token",
                "connected_at": 100,
            },
            "newer-client": {
                "owner": "hosted-owner",
                "token": "new.token",
                "connected_at": 200,
            },
        }
        manager.active_tokens = {}
        manager.processes = {}
        manager._save_users = Mock()
        manager._restore_hosted_instance = Mock(return_value=True)
        manager._attach_existing_process = Mock(return_value=None)
        manager._cleanup_hosted_instance_files = Mock()

        self.assertEqual(manager.restore_hosted_users(), 1)
        self.assertEqual(set(manager.saved_users), {"newer-client"})
        manager._restore_hosted_instance.assert_called_once_with(
            "newer-client",
            manager.saved_users["newer-client"],
        )
        manager._cleanup_hosted_instance_files.assert_called_once_with("older-client")

    def test_hosted_output_is_forwarded_to_parent_and_client_log(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory, "hosted.log")
            log_path.write_bytes(b"connected\ncommand received\n")
            with patch("builtins.print") as print_line:
                HostManager._forward_hosted_output(
                    str(log_path),
                    0,
                    type("ExitedProcess", (), {"poll": lambda self: 0})(),
                    "client-1",
                )
            logged_lines = log_path.read_bytes().decode("utf-8").splitlines()

        self.assertEqual(
            [call.args[0] for call in print_line.call_args_list],
            ["[HOSTED client-1] connected", "[HOSTED client-1] command received"],
        )
        self.assertEqual(
            logged_lines,
            ["connected", "command received"],
        )


if __name__ == "__main__":
    unittest.main()
