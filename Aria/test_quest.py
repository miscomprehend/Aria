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
        self.assertEqual(quests.get_quest_state(quests.quests["quest-active"]), "In progress")
        self.assertEqual(quests._get_progress(quests.quests["quest-active"]), ("WATCH_VIDEO", 25, 100))
        self.assertEqual(api.calls, [("GET", "/quests/@me", None)])

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
