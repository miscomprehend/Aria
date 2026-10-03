import unittest

from host import _keepalive_restart_delay
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


if __name__ == "__main__":
    unittest.main()
