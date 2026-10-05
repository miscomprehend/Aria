import unittest

from quest import QuestSystem


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeApi:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def request(self, method, endpoint, data=None):
        self.calls.append((method, endpoint, data))
        return FakeResponse(self.payload)


class QuestSystemTests(unittest.TestCase):
    def test_fetch_lists_server_quests_without_mutating_them(self):
        payload = {
            "quests": [
                {
                    "id": "quest-active",
                    "config": {
                        "messages": {"quest_name": "Active quest"},
                        "task_config_v2": {
                            "tasks": {
                                "WATCH_VIDEO": {
                                    "event_name": "WATCH_VIDEO",
                                    "target": 100,
                                }
                            }
                        },
                    },
                    "user_status": {
                        "enrolled_at": "2026-10-01T00:00:00+00:00",
                        "progress": {
                            "WATCH_VIDEO": {
                                "event_name": "WATCH_VIDEO",
                                "value": 25,
                            }
                        },
                    },
                },
                {
                    "id": "quest-user-made",
                    "config": {"grant_type": "USER_MADE"},
                },
            ]
        }
        api = FakeApi(payload)
        quests = QuestSystem(api)

        success, _ = quests.fetch_quests()

        self.assertTrue(success)
        self.assertEqual(list(quests.quests), ["quest-active"])
        self.assertEqual(len(quests.quest_manager), 1)
        self.assertEqual(quests.get_quest_state(quests.quests["quest-active"]), "In progress")
        self.assertEqual(quests._get_progress(quests.quests["quest-active"]), ("WATCH_VIDEO", 25, 100))
        self.assertEqual(api.calls, [("GET", "/quests/@me", None)])

    def test_enrollment_block_still_lists_account_quests(self):
        payload = {
            "quest_enrollment_blocked_until": "2026-10-20T00:00:00+00:00",
            "quests": [{"id": "quest-a", "config": {"messages": {"quest_name": "A"}}}],
        }
        quests = QuestSystem(FakeApi(payload))

        success, message = quests.fetch_quests()

        self.assertTrue(success)
        self.assertEqual(list(quests.quests), ["quest-a"])
        self.assertIn("blocked until", message)

    def test_one_unparseable_quest_does_not_hide_the_others(self):
        from unittest.mock import patch
        from quest_system.interface import Quest as QuestData

        payload = {
            "quests": [
                {"id": "quest-bad", "config": {"messages": {"quest_name": "Bad"}}},
                {"id": "quest-good", "config": {"messages": {"quest_name": "Good"}}},
            ]
        }
        real_from_dict = QuestData.from_dict.__func__

        def flaky(cls, data, user_id=""):
            if data.get("id") == "quest-bad":
                raise TypeError("unexpected shape")
            return real_from_dict(cls, data, user_id)

        quests = QuestSystem(FakeApi(payload))
        with patch.object(QuestData, "from_dict", classmethod(flaky)):
            success, _ = quests.fetch_quests()

        self.assertTrue(success)
        self.assertEqual(set(quests.quests), {"quest-bad", "quest-good"})
        self.assertEqual([q.id for q in quests.quest_manager], ["quest-good"])

    def test_state_reflects_completion_and_claim_markers(self):
        quests = QuestSystem(FakeApi({}))

        self.assertEqual(quests.get_quest_state({"config": {}, "user_status": {"completed_at": "now"}}), "Completed")
        self.assertEqual(
            quests.get_quest_state({
                "config": {},
                "user_status": {"completed_at": "now", "claimed_at": "now"},
            }),
            "Reward claimed",
        )
        self.assertEqual(quests.get_quest_state({"config": {}, "user_status": None}), "Available")

    def test_malformed_progress_values_do_not_break_status_display(self):
        quests = QuestSystem(FakeApi({}))
        quest = {
            "config": {
                "task_config_v2": {
                    "tasks": {
                        "PLAY_ON_DESKTOP": {
                            "event_name": "PLAY_ON_DESKTOP",
                            "target": "invalid",
                        }
                    }
                }
            },
            "user_status": {"progress": {"PLAY_ON_DESKTOP": {"value": "invalid"}}},
        }

        self.assertEqual(quests._get_progress(quest), ("Unknown", 0, 100))

    def test_fetch_failure_does_not_clear_cached_quests(self):
        api = FakeApi({})
        api.request = lambda method, endpoint, data=None: type("FailedResponse", (), {"status_code": 503})()
        quests = QuestSystem(api)
        quests.quests = {"cached": {"id": "cached"}}

        success, message = quests.fetch_quests()

        self.assertFalse(success)
        self.assertIn("503", message)
        self.assertIn("cached", quests.quests)


if __name__ == "__main__":
    unittest.main()
