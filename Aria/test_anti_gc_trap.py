import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from anti_gc_trap import AntiGCTrap


class AntiGCTrapTests(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.api.user_id = "self"
        self.trap = AntiGCTrap(self.api)
        self.trap.enabled = True

    def test_channel_create_accepts_gateway_id_and_preserves_channel_fields(self):
        event = {
            "id": "group-1",
            "type": 3,
            "owner_id": "other",
            "recipients": [{"id": "self"}, {"id": "other"}],
        }
        thread = Mock()

        with patch("anti_gc_trap.threading.Thread", return_value=thread) as thread_class:
            self.assertTrue(self.trap.check_gc_creation(event))

        passed_event = thread_class.call_args.kwargs["args"][0]
        self.assertEqual(passed_event["channel_id"], "group-1")
        self.assertEqual(passed_event["recipients"], event["recipients"])
        thread.start.assert_called_once()

    def test_rejects_non_group_channels(self):
        self.assertFalse(self.trap.check_gc_creation({"id": "dm-1", "type": 1}))

    def test_recipient_add_event_is_accepted_for_channel_lookup(self):
        thread = Mock()
        with patch("anti_gc_trap.threading.Thread", return_value=thread) as thread_class:
            self.assertTrue(self.trap.check_gc_creation({
                "channel_id": "group-3",
                "user_id": "self",
            }))

        thread_class.assert_called_once()
        self.assertEqual(
            thread_class.call_args.kwargs["args"][0]["channel_id"],
            "group-3",
        )
        thread.start.assert_called_once()

    def test_recipient_event_resolves_group_channel_and_handles_small_group(self):
        channel = {
            "id": "group-2",
            "type": 3,
            "owner_id": "other",
            "recipients": [{"id": "self"}],
        }
        self.api.request.return_value = SimpleNamespace(
            status_code=200,
            json=lambda: channel,
        )

        with (
            patch("anti_gc_trap.time.sleep"),
            patch.object(self.trap, "_rename_gc") as rename,
            patch.object(self.trap, "_change_gc_icon") as change_icon,
            patch.object(self.trap, "_send_leave_message") as leave_message,
            patch.object(self.trap, "_leave_gc") as leave,
            patch.object(self.trap, "_send_webhook_alert") as alert,
        ):
            self.trap._handle_gc_trap({"channel_id": "group-2", "user_id": "self"})

        self.api.request.assert_called_once_with("GET", "/channels/group-2")
        rename.assert_called_once_with("group-2")
        change_icon.assert_called_once_with("group-2")
        leave_message.assert_called_once_with("group-2")
        leave.assert_called_once_with("group-2")
        alert.assert_called_once()

    def test_ignores_group_owned_by_self(self):
        with (
            patch("anti_gc_trap.time.sleep"),
            patch.object(self.trap, "_leave_gc") as leave,
        ):
            self.trap._handle_gc_trap({
                "id": "own-group",
                "type": 3,
                "owner_id": "self",
                "recipients": [{"id": "other"}],
            })

        leave.assert_not_called()


if __name__ == "__main__":
    unittest.main()
